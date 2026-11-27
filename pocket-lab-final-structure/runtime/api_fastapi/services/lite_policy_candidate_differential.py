"""Bounded offline differential assessment of authenticated policy candidates.

Runs only in the existing release child, using local OPA and a restricted
builtin capability document. Synthetic input never becomes a session or a
policy decision record. A finite corpus is evidence, not general equivalence.
"""
from __future__ import annotations

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
MAX_CASES = 512
# The existing repository modules require these builtins. No HTTP, DNS,
# environment, filesystem, runtime inspection, graph or custom builtins.
ALLOWED_BUILTINS = frozenset({"object.get", "object.union", "concat", "lower",
                              "time.parse_rfc3339_ns", "time.now_ns"})
NOTE = re.compile(rb"# pocketlab-release-note: [ -~]{1,160}\n")


def locally_supported_evolution(before: dict[str, bytes], after: dict[str, bytes]):
    """Exact identity or a deliberately narrow local lexical transformation.

    Only complete ASCII note-comment lines appended after an existing newline
    are understood. Neither a publisher compatibility flag nor sampled
    equality can approve arbitrary policy code.
    """
    if set(before) != REGISTERED_MODULES or set(after) != REGISTERED_MODULES:
        return "unsupported_inventory"
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
        return "system_health_projection", target_id, revision, {"operation_id": "projection.reconcile",
            "risk_class": "A", "adapter_enabled": True, "owner_policy_current": True}
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
            context = {"actor": {"type": kind, "identity_id": "synthetic"},
                       "authorization": {"role": role, "owner_authority": role == "Owner",
                           "enterprise_enabled": enterprise, "membership_active": bool(role and enterprise)},
                       "session": {"authenticated": kind != "anonymous", "assurance": [
                           {"purpose": purpose, "credential_id": "synthetic", "satisfied_at": "2020-01-01T00:00:00Z",
                            "expires_at": "2099-01-01T00:00:00Z"}
                           for purpose in (action, "lifecycle:" + revision)]}}
            doc = build_authorization_input(auth_context=context, action_id=action, target_type=target_type,
                target_id=target_id, target_revision=revision, target=state,
                request_context={"confirmation_present": True})
            doc["continuation"] = {"matching_independent_approval": False, "matching_temporary_exception": False}
            cases[f"{action}:{i}:valid"] = doc
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
        if evolution not in ("source_unchanged", "locally_supported_note_evolution"):
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
        changed = [key for key in cases if differential_evidence(a[key], b[key])["state"] != "sample_equal"]
        return {**result, "state": "differences_observed" if changed else "sample_equal",
                "case_count": len(cases), "changed_count": len(changed), "corpus_sha256": digest(cases),
                "before_sha256": digest(a), "after_sha256": digest(b), "baseline_revision": revision,
                "semantic_equivalence_proved": False}
    except Exception:
        return {"state": "unavailable", "execution_eligible": False}
