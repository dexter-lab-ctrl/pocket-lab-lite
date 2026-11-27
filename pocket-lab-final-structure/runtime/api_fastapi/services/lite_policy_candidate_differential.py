"""Bounded offline differential assessment of authenticated policy candidates.

Runs only in the existing release child, using local OPA and a restricted
builtin capability document. Synthetic input never becomes a session or a
policy decision record. A finite corpus is evidence, not general equivalence.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile

from .lite_lifecycle_contract import canonical_bytes, digest
from .lite_policy_compatibility import REGISTERED_MODULES, differential_evidence
from .lite_release_package import POLICY_PREFIX, _inventory

MAX_MEMBER = 256 * 1024
MAX_RESULT = 2 * 1024 * 1024
MAX_CASES = 768
# The existing repository modules require these builtins. No HTTP, DNS,
# environment, filesystem, runtime inspection, graph or custom builtins.
ALLOWED_BUILTINS = frozenset({"object.get", "object.union", "concat", "lower",
                              "time.parse_rfc3339_ns", "time.now_ns"})
NOTE = re.compile(rb"# pocketlab-release-note: [ -~]{1,160}\n")

# A local, versioned tightening of an existing rule, not arbitrary code or
# publisher-defined semantics. All other bytes, including tests, must match.
RESTRICTIVE_EDIT = "backup-location-human-owner-v1"
RESTRICTIVE_SYSTEM_EDIT = "system-health-fresh-evidence-v1"
MAIN_MODULE = POLICY_PREFIX + "pocketlab/pocketlab.rego"
RESTRICTIVE_ACTION = "backup.location.manage"
RESTRICTIVE_SYSTEM_ACTION = "system_health.automatic"
_RESTRICT_BEFORE = b'backup_location_action if {\n\tinput.action.id == "backup.location.manage"\n'
_RESTRICT_AFTER = _RESTRICT_BEFORE + (b'\tinput.actor.type == "human"\n'
    b'\tinput.actor.role == "Owner"\n\tinput.actor.owner_authority == true\n'
    b'\tnot synthetic_actor\n')
_SYSTEM_EVIDENCE_BEFORE = b'    input.target.state.owner_policy_current == true\n'
_SYSTEM_EVIDENCE_AFTER = _SYSTEM_EVIDENCE_BEFORE + b'    input.target.state.evidence_fresh == true\n'


def restrictive_candidate(before, edit_id):
    if set(before) != REGISTERED_MODULES:
        raise ValueError("policy_restrictive_contract_mismatch")
    result = dict(before)
    if edit_id == RESTRICTIVE_EDIT:
        if (before[MAIN_MODULE].count(_RESTRICT_BEFORE) != 1
                or _RESTRICT_AFTER in before[MAIN_MODULE]):
            raise ValueError("policy_restrictive_contract_mismatch")
        result[MAIN_MODULE] = result[MAIN_MODULE].replace(_RESTRICT_BEFORE, _RESTRICT_AFTER, 1)
    elif edit_id == RESTRICTIVE_SYSTEM_EDIT:
        if (before[MAIN_MODULE].count(_SYSTEM_EVIDENCE_BEFORE) != 1
                or _SYSTEM_EVIDENCE_AFTER in before[MAIN_MODULE]):
            raise ValueError("policy_restrictive_contract_mismatch")
        result[MAIN_MODULE] = result[MAIN_MODULE].replace(_SYSTEM_EVIDENCE_BEFORE, _SYSTEM_EVIDENCE_AFTER, 1)
    else:
        raise ValueError("policy_restrictive_contract_mismatch")
    return result


def restrictive_edit_for(before, after):
    for edit_id in (RESTRICTIVE_EDIT, RESTRICTIVE_SYSTEM_EDIT):
        try:
            if restrictive_candidate(before, edit_id) == after:
                return edit_id
        except ValueError:
            continue
    return None


def supported_differential(evidence):
    return ((evidence.get("local_contract") == "locally_supported_note_evolution"
             and evidence.get("state") == "sample_equal")
            or (evidence.get("local_contract") == "locally_supported_restrictive_evolution"
                and evidence.get("state") == "sample_restrictive"
                and evidence.get("restrictive_edit") in {RESTRICTIVE_EDIT, RESTRICTIVE_SYSTEM_EDIT}))


def _eligible_backup_location_owner(case):
    actor = case["actor"]
    return (actor.get("type") == "human" and actor.get("role") == "Owner"
            and actor.get("owner_authority") is True
            and not case.get("harness", {}).get("enabled"))


def compare_corpus(cases, before, after, evolution, restrictive_edit=None):
    """Full envelopes must match except an explicitly registered allow->deny.

    Never accept a changed allowed decision, changed existing deny, or a
    changed action outside the locally understood tightening.
    """
    if not cases or set(cases) != set(before) or set(cases) != set(after):
        raise ValueError("policy_differential_incomplete")
    # Preserve the original helper contract for local fixtures that model the
    # first registered transformation without carrying its identifier.
    if restrictive_edit is None and any(
            item.get("action", {}).get("id") == RESTRICTIVE_ACTION for item in cases.values()):
        restrictive_edit = RESTRICTIVE_EDIT
    changed = [key for key in cases if differential_evidence(before[key], after[key])["state"] != "sample_equal"]
    if not changed:
        return "sample_equal", changed
    if (evolution == "locally_supported_restrictive_evolution"
            and restrictive_edit == RESTRICTIVE_EDIT):
        if all(cases[key]["action"]["id"] == RESTRICTIVE_ACTION
               and not _eligible_backup_location_owner(cases[key])
               and before[key]["allow"] is True
               and after[key] == {"allow": False, "constraints": [],
                                  "reason_code": "actor_not_authenticated"}
               for key in changed):
            # Positive and negative cases must both be exercised.
            owner_survives = any(cases[key]["action"]["id"] == RESTRICTIVE_ACTION
                and _eligible_backup_location_owner(cases[key])
                and before[key]["allow"] is True and after[key]["allow"] is True
                for key in cases)
            if owner_survives:
                return "sample_restrictive", changed
    if (evolution == "locally_supported_restrictive_evolution"
            and restrictive_edit == RESTRICTIVE_SYSTEM_EDIT):
        if all(cases[key]["action"]["id"] == RESTRICTIVE_SYSTEM_ACTION
               and cases[key]["actor"]["type"] == "service"
               and cases[key]["actor"]["id"] == "system-health-scheduler"
               and cases[key]["target"]["state"].get("evidence_fresh") is False
               and before[key]["allow"] is True
               and after[key] == {"allow": False, "constraints": [],
                                  "reason_code": "actor_not_authenticated"}
               for key in changed):
            fresh_survives = any(cases[key]["action"]["id"] == RESTRICTIVE_SYSTEM_ACTION
                and cases[key]["target"]["state"].get("evidence_fresh") is True
                and before[key]["allow"] is True and after[key]["allow"] is True
                for key in cases)
            if fresh_survives:
                return "sample_restrictive", changed
    return "differences_observed", changed


def locally_supported_evolution(before: dict[str, bytes], after: dict[str, bytes]):
    """Exact identity or a deliberately narrow local lexical transformation.

    Only complete ASCII note-comment lines appended after an existing newline
    are understood. Neither a publisher compatibility flag nor sampled
    equality can approve arbitrary policy code.
    """
    if set(before) != REGISTERED_MODULES or set(after) != REGISTERED_MODULES:
        return "unsupported_inventory"
    try:
        if restrictive_edit_for(before, after):
            return "locally_supported_restrictive_evolution"
    except ValueError:
        pass
    changed = False
    for name, old in before.items():
        new = after[name]
        if old == new:
            continue
        changed = True
        if not old.endswith(b"\n") or not new.startswith(old):
            return "unknown_semantic_impact"
        suffix = new[len(old):]
        lines = suffix.splitlines(keepends=True)
        if not 1 <= len(lines) <= 8 or any(not NOTE.fullmatch(line) for line in lines):
            return "unknown_semantic_impact"
    return "locally_supported_note_evolution" if changed else "source_unchanged"


def _modules(stream, policy_document):
    expected = _inventory(policy_document, prefix=POLICY_PREFIX, suffix=".rego")
    if set(expected) != REGISTERED_MODULES:
        raise ValueError("policy_inventory_unsupported")
    result = {}
    with zipfile.ZipFile(stream) as archive:
        for name, sha in expected.items():
            item = archive.getinfo(name)
            if item.file_size > MAX_MEMBER:
                raise ValueError("policy_member_limit")
            with archive.open(item) as handle:
                data = handle.read(MAX_MEMBER + 1)
            if len(data) != item.file_size or hashlib.sha256(data).hexdigest() != sha:
                raise ValueError("policy_member_changed")
            data.decode("utf-8")
            result[name] = data
    return result


def _local_modules(policy_document):
    expected = _inventory(policy_document, prefix=POLICY_PREFIX, suffix=".rego")
    root = Path(__file__).resolve().parents[4]
    if set(expected) != REGISTERED_MODULES:
        raise ValueError("policy_inventory_unsupported")
    result = {}
    for name, sha in expected.items():
        with (root / name).open("rb") as handle:
            data = handle.read(MAX_MEMBER + 1)
        if len(data) > MAX_MEMBER or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError("local_policy_source_changed")
        data.decode("utf-8")
        result[name] = data
    return result


def _target(action):
    target_id, revision = "synthetic-target", "synthetic-revision"
    if action.startswith("app.") or action == "catalog.install":
        return "app", target_id, revision, {"resource_type": "app", "app_id": target_id,
            "semantic_action": action, "required_capability": "synthetic-capability",
            "capability_supported": True, "platform_supported": True, "placement_required": True,
            "placement_ready": True, "contract_revision": revision, "request_fingerprint": revision}
    if action.startswith("device."):
        return "device", target_id, revision, {"confirmed": True, "revision_validated": True,
            "protected_server_host": False, "storage_role_change": True}
    if action == "identity.passkey.revoke":
        return "passkey", target_id, revision, {}
    if action == "backup.location.manage":
        return "recovery_location", target_id, revision, {"protected_server_host": True}
    if action.startswith(("backup.", "restore.")):
        return "recovery", target_id, revision, {"confirmed": True, "preview_bound": True, "restorable": True}
    if action == "owner.operations.approve":
        return "owner_operation", target_id, revision, {"contract_version": 1,
            "operation": "photo_backup.bounded_acceptance.v1", "status": "pending_approval",
            "target_node_id": "synthetic-node", "target_binding_digest": revision,
            "destination_id": "server-photoprism-originals", "destination_contract_version": 2,
            "scope_digest": revision, "approval_deadline": "2099-01-01T00:00:00Z"}
    if action == "owner.operations.client.register":
        return "owner_operation_client_pairing", target_id, revision, {"registration_mode": "pairing",
            "client_id": "synthetic-client", "public_key_fingerprint": revision,
            "capabilities": ["photo_backup.bounded_acceptance.v1"], "status": "pending",
            "pairing_binding_digest": revision, "expires_at": "2099-01-01T00:00:00Z"}
    if action == "system_health.recovery":
        return "system_health_incident", target_id, revision, {"operation_id": "runtime.consumer.reconnect",
            "adapter_enabled": True, "preflight_valid": True, "incident_generation": 1, "enrollment_generation": 0}
    if action == "system_health.maintenance":
        return "system_health_maintenance", target_id, revision, {"operation_id": "sqlite.checkpoint.passive",
            "adapter_enabled": True, "confirmed": True}
    if action == "system_health.automatic":
        return "system_health_projection", "system.activity_history", revision, {"operation_id": "projection.reconcile",
            "risk_class": "A", "adapter_enabled": True, "owner_policy_current": True,
            "evidence_fresh": True}
    if action in {"lifecycle.policy.activate", "lifecycle.policy.claim"}:
        revision = "a" * 64
        return "lifecycle_policy_execution", ("local_workspace" if action.endswith("activate") else "synthetic-operation"), revision, {
            "change_digest": revision, "contract_version": 1, "purpose": "policy-reconciler",
            "execution_enabled": True, "grant_current": True}
    if action in {"lifecycle.capability.activate", "lifecycle.capability.claim"}:
        revision = "a" * 64
        return "lifecycle_capability_activation", ("local_workspace" if action.endswith("activate") else "synthetic-operation"), revision, {
            "change_digest": revision, "contract_version": 1,
            "purpose": "system-health-scheduler", "capability_id": "system.activity_history.reconcile.activate",
            "execution_enabled": True, "grant_current": True}
    if action in {"lifecycle.release.prepare", "lifecycle.release.claim"}:
        revision = "a" * 64
        return "lifecycle_release_preparation", ("local_workspace" if action.endswith("prepare") else "synthetic-operation"), revision, {
            "change_digest": revision, "contract_version": 1, "purpose": "release-reconciler",
            "execution_enabled": True, "grant_current": True}
    if action.startswith("lifecycle."):
        revision = "a" * 64
        return "lifecycle_consent", "local_workspace", revision, {"change_digest": revision,
            "contract_version": 1, "execution_enabled": False}
    return "unknown", target_id, revision, {}


def corpus():
    from .lite_policy_opa import PROTECTED_ACTIONS, build_authorization_input
    cases = {}
    actors = [("human", "Owner", False), ("human", "Owner", True),
              ("human", "Admin", True), ("human", "Operator", True),
              ("human", "Viewer", True), ("human", "Auditor", True),
              ("human", None, False), ("service", None, False),
              ("qualification", None, False), ("test", None, False),
              ("anonymous", None, False)]
    for action in sorted(PROTECTED_ACTIONS | {"rules.activate", "rules.rollback", "unknown.action"}):
        target_type, target_id, revision, state = _target(action)
        for i, (kind, role, enterprise) in enumerate(actors):
            actor_id = ("policy-reconciler" if action == "lifecycle.policy.claim" and kind == "service"
                        else "release-reconciler" if action == "lifecycle.release.claim" and kind == "service"
                        else "system-health-scheduler" if action == "system_health.automatic" and kind == "service"
                        else "synthetic")
            method = ("local_supervisor" if actor_id == "policy-reconciler" else
                      "internal_worker" if actor_id in {"system-health-scheduler", "release-reconciler"} else "passkey")
            context = {"actor": {"type": kind, "identity_id": actor_id},
                       "authorization": {"role": role, "owner_authority": role == "Owner",
                           "enterprise_enabled": enterprise, "membership_active": bool(role and enterprise)},
                       "session": {"authenticated": kind != "anonymous", "auth_method": method, "assurance": [
                           {"purpose": purpose, "credential_id": "synthetic", "satisfied_at": "2020-01-01T00:00:00Z",
                            "expires_at": "2099-01-01T00:00:00Z"}
                           for purpose in (action, "lifecycle:" + revision)]}}
            doc = build_authorization_input(auth_context=context, action_id=action, target_type=target_type,
                target_id=target_id, target_revision=revision, target=state,
                request_context={"confirmation_present": True})
            doc["continuation"] = {"matching_independent_approval": False, "matching_temporary_exception": False}
            cases[f"{action}:{i}:valid"] = doc
            if action == RESTRICTIVE_ACTION and i == 0:
                no_authority = copy.deepcopy(doc)
                no_authority["actor"]["owner_authority"] = False
                cases[f"{action}:{i}:no_owner_authority"] = no_authority
                synthetic = copy.deepcopy(doc)
                synthetic["harness"] = {
                    "enabled": True, "qualification_environment": True,
                    "target_scope": "synthetic-recovery", "capabilities": [action],
                    "destructive_allowed": True,
                }
                synthetic["target"]["scope"] = "synthetic-recovery"
                cases[f"{action}:{i}:synthetic_owner"] = synthetic
            if action == RESTRICTIVE_SYSTEM_ACTION and kind == "service":
                stale = copy.deepcopy(doc)
                stale["target"]["state"]["evidence_fresh"] = False
                cases[f"{action}:{i}:stale_evidence"] = stale
            if i in (0, 2, 3):
                blocked = copy.deepcopy(doc)
                blocked["session"]["assurance"] = []
                blocked["target"]["state"] = {}
                blocked["request"]["confirmation_present"] = False
                cases[f"{action}:{i}:invalid"] = blocked
                if i == 3:
                    continued = copy.deepcopy(doc)
                    continued["continuation"] = {"matching_independent_approval": True, "matching_temporary_exception": True}
                    cases[f"{action}:{i}:continuation"] = continued
    if len(cases) > MAX_CASES:
        raise ValueError("policy_corpus_limit")
    return cases


def _opa(root, args, deadline):
    remaining = min(8, (deadline - time.monotonic_ns()) / 1e9)
    if remaining <= 0:
        raise TimeoutError("policy_review_deadline")
    # Trusted locally installed tool; no executable or path from the release.
    binary = os.environ.get("POCKETLAB_OPA_BIN", "opa")
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "HOME", "PREFIX", "TMPDIR", "LD_LIBRARY_PATH", "LANG"}}
    env["GOMAXPROCS"] = "1"
    env["GOMEMLIMIT"] = "96MiB"
    output = root / "output.json"
    with output.open("wb") as out:
        result = subprocess.run([binary, *args], cwd=root, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=subprocess.DEVNULL, timeout=remaining, check=False)
    if result.returncode != 0 or output.stat().st_size > MAX_RESULT:
        raise ValueError("policy_differential_unavailable")
    with output.open("rb") as handle:
        return json.loads(handle.read(MAX_RESULT + 1))


def _evaluate(root, modules, template, cases, capabilities, deadline):
    policies = root / "policy"
    policies.mkdir()
    for name, raw in modules.items():
        (policies / name.rsplit("/", 1)[-1]).write_bytes(raw)
    (policies / "template.json").write_bytes(canonical_bytes(template))
    input_path = root / "input.json"
    input_path.write_bytes(canonical_bytes({"cases": cases}))
    caps_path = root / "capabilities.json"
    caps_path.write_bytes(canonical_bytes(capabilities))
    result = _opa(root, ["eval", "--format=json", "--strict-builtin-errors", "--capabilities", str(caps_path),
                         "--data", str(policies), "--input", str(input_path),
                         "{key: d | some key, item in input.cases; d := data.pocketlab.authz.decision with input as item}"], deadline)
    values = result["result"][0]["expressions"][0]["value"]
    if not isinstance(values, dict) or set(values) != set(cases):
        raise ValueError("policy_differential_incomplete")
    return values


def assess(stream, local_document, candidate_document, *, parent: Path, deadline: int):
    from .lite_policy_runtime_evidence import _snapshot
    try:
        before, after = _local_modules(local_document), _modules(stream, candidate_document)
        evolution = locally_supported_evolution(before, after)
        result = {"state": "not_executed", "local_contract": evolution, "execution_eligible": False}
        # Arbitrary new policy source is not run even in the offline tool.
        if evolution not in ("source_unchanged", "locally_supported_note_evolution", "locally_supported_restrictive_evolution"):
            return result
        snapshot = _snapshot()
        if snapshot is None:
            return {**result, "state": "baseline_unconfirmed"}
        revision, content_hash, manifest_json, template_id, template_version, parameters = snapshot
        manifest = json.loads(manifest_json)
        rows = manifest if isinstance(manifest, list) else manifest["files"]
        expected = {row["path"]: row["sha256"] for row in rows}
        if any(expected.get(name.rsplit("/", 1)[-1]) != hashlib.sha256(raw).hexdigest()
               for name, raw in before.items()):
            return {**result, "state": "baseline_unconfirmed"}
        template = {"template_id": template_id, "template_version": template_version, "parameters": json.loads(parameters)}
        if expected.get("template.json") != hashlib.sha256(canonical_bytes(template) + b"\n").hexdigest():
            return {**result, "state": "baseline_unconfirmed"}
        cases = corpus()
        with tempfile.TemporaryDirectory(prefix="policy-differential-", dir=parent) as raw:
            root = Path(raw)
            capabilities = _opa(root, ["capabilities", "--current"], deadline)
            capabilities["builtins"] = [item for item in capabilities["builtins"] if item["name"] in ALLOWED_BUILTINS]
            capabilities["allow_net"] = []
            left, right = root / "before", root / "after"
            left.mkdir(); right.mkdir()
            a = _evaluate(left, before, template, cases, capabilities, deadline)
            b = _evaluate(right, after, template, cases, capabilities, deadline)
        if _snapshot() != snapshot:
            return {**result, "state": "baseline_changed"}
        restrictive_edit = restrictive_edit_for(before, after)
        comparison, changed = compare_corpus(cases, a, b, evolution, restrictive_edit)
        return {**result, "state": comparison,
                "restrictive_edit": restrictive_edit if comparison == "sample_restrictive" else None,
                "case_count": len(cases), "changed_count": len(changed), "corpus_sha256": digest(cases),
                "before_sha256": digest(a), "after_sha256": digest(b), "baseline_revision": revision,
                "semantic_equivalence_proved": False,
                "note_suffixes": {name.rsplit("/", 1)[-1]: base64.b64encode(after[name][len(before[name]):]).decode("ascii")
                                  for name in before if after[name] != before[name]}
                                  if comparison == "sample_equal" and evolution == "locally_supported_note_evolution" else {}}
    except Exception:
        return {"state": "unavailable", "execution_eligible": False}
