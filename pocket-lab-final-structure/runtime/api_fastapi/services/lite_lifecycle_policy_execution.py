"""One-shot, exact signed note-evolution activation via the existing supervisor.

No general Rego mutation, user-provided code/path, standing execution grant,
human impersonation or cross-domain delegation. Production remains off until
separately qualified; the isolated local qualification opt-in is also off.
"""
from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from urllib.parse import urlsplit

from ..db.connection import connection, read_connection, begin_immediate
from . import lite_lifecycle_authority as authority
from . import lite_infrastructure_automation as automation
from . import lite_policy_lifecycle as lifecycle
from . import lite_policy_opa as opa
from . import lite_release_trust_configuration as trust_config
from .lite_lifecycle_contract import canonical_bytes, digest, registry_revision
from .lite_policy_candidate_differential import locally_supported_evolution
from .lite_policy_compatibility import REGISTERED_MODULES

ACTION = "lifecycle.policy.activate"
CLAIM = "lifecycle.policy.claim"
EXECUTOR = "policy-reconciler"


class PolicyExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal[True]


class PolicyExecutionRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    grant_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirm: Literal[True]


def gate():
    # Separate qualification is required before authoring a production gate.
    if os.environ.get("POCKETLAB_RELEASE_POLICY_EXECUTION") != "1":
        return False
    try:
        from . import qualification_context as qualification
        from ..db.connection import database_path
        if not qualification.enabled() or not os.environ.get("PM2_HOME"):
            return False
        root = qualification.root()
        state = qualification._resolved_without_symlink_escape(lifecycle._state_root(), root)
        paths = (state, database_path(), Path(os.environ["PM2_HOME"]))
        if not all(qualification._resolved_without_symlink_escape(path, root) != root
                   for path in paths):
            return False
        # Active is a governed symlink: validate its parent and resolved target,
        # not just the state DB. Never probe the production default listener.
        active = opa._policy_root()
        if active.absolute() != state / "opa" / "active":
            return False
        if active.exists():
            active.resolve(strict=True).relative_to(state / "opa" / "stage")
        endpoint = urlsplit(opa.OPA_BASE_URL)
        return (os.environ.get("POCKETLAB_OPA_URL", "").rstrip("/") == opa.OPA_BASE_URL
                and opa._opa_endpoint_is_loopback() and endpoint.scheme == "http"
                and endpoint.hostname == "127.0.0.1" and endpoint.port is not None
                and 1024 <= endpoint.port <= 65535 and endpoint.port != 8181
                and not endpoint.path and not endpoint.query and not endpoint.fragment)
    except Exception:
        return False


def _receipt(conn):
    row = conn.execute("SELECT review_json FROM lite_release_trust_observation WHERE singleton_id=1 AND state='historical_evidence'").fetchone()
    return json.loads(row["review_json"]) if row else {}


def _render(template, suffixes, expected_policy):
    local_revision, local_tree = lifecycle.policy_source_tree(
        template["template_id"], template["template_version"], template["parameters"])
    by_name = {name.rsplit("/", 1)[-1]: name for name in REGISTERED_MODULES}
    before = {full: local_tree[name].encode("utf-8") for name, full in by_name.items()}
    if set(local_tree) != set(by_name) | {"template.json", "revision.rego"}:
        raise ValueError("policy_inventory_changed")
    if not isinstance(suffixes, dict) or not suffixes or set(suffixes) - set(by_name):
        raise ValueError("policy_note_scope_invalid")
    after = dict(before)
    for name, value in suffixes.items():
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError("policy_note_scope_invalid")
        after[by_name[name]] += base64.b64decode(value, validate=True)
    if locally_supported_evolution(before, after) != "locally_supported_note_evolution":
        raise ValueError("policy_evolution_not_supported")
    inventory = [{"path": name, "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in sorted(after.items())]
    if digest(inventory) != expected_policy:
        raise ValueError("policy_signed_inventory_mismatch")
    tree = {name: after[full].decode("utf-8") for name, full in by_name.items()}
    tree["template.json"] = local_tree["template.json"]
    _, seed = lifecycle.manifest_for_tree(tree)
    revision = "plr-" + seed[:32]
    tree["revision.rego"] = f'package pocketlab.meta\n\nrevision := "{revision}"\n'
    manifest, content_hash = lifecycle.manifest_for_tree(tree)
    return local_revision, revision, tree, manifest, content_hash


def binding_fields(conn, payload):
    if not gate():
        raise PermissionError("policy_execution_qualification_required")
    ws = authority._workspace(conn)
    if ws["boundary_revision"] != payload.expected_revision:
        raise ValueError("boundary_revision_changed")
    if authority._prefs(conn)["profile"] != "recommended" or not authority._trust(conn):
        raise PermissionError("policy_execution_trust_required")
    receipt = _receipt(conn)
    differential = (receipt.get("policy_review") or {}).get("differential") or {}
    observation = receipt.get("policy_runtime_observation") or {}
    if (receipt.get("metadata_sha256") != payload.metadata_sha256
            or receipt.get("registry_revision") != registry_revision()
            or (receipt.get("source_package") or {}).get("state") != "verified_for_review"
            or differential.get("state") != "sample_equal"
            or differential.get("local_contract") != "locally_supported_note_evolution"
            or differential.get("baseline_revision") != authority._policy(conn)
            or observation.get("state") != "modules_match"
            or observation.get("data_identity") != "registered_template_matches"
            or observation.get("observed_revision") != authority._policy(conn)
            or (receipt.get("capability_review") or {}).get("total") != 0
            or (receipt.get("migration_review") or {}).get("state") != "unchanged"
            or ((receipt.get("migration_review") or {}).get("applied_ledger") or {}).get("state") != "ledger_matches"):
        raise PermissionError("policy_execution_candidate_unproved")
    current = conn.execute("SELECT * FROM policy_revisions WHERE revision_id=?", (authority._policy(conn),)).fetchone()
    template = {"template_id": current["template_id"], "template_version": current["template_version"],
                "parameters": json.loads(current["canonical_parameters_json"])}
    suffixes = differential.get("note_suffixes")
    local, revision, _, _, content_hash = _render(template, suffixes, receipt["policy_sha256"])
    if local != current["revision_id"] or revision == local:
        raise ValueError("policy_baseline_changed")
    return {"purpose": EXECUTOR, "metadata_sha256": payload.metadata_sha256,
            "policy_sha256": receipt["policy_sha256"], "baseline_revision": local,
            "candidate_revision": revision, "content_hash": content_hash,
            "corpus_sha256": differential["corpus_sha256"], "template": template,
            "suffixes": suffixes}


def preview(context, payload):
    with read_connection() as conn:
        _, binding, fingerprint = authority._change(conn, context, ACTION, payload)
        scope = binding["policy_execution"]
    return {"purpose": "lifecycle:" + fingerprint, "confirmation_required": True,
            "scope": {k: scope[k] for k in ("purpose", "metadata_sha256", "policy_sha256",
                "baseline_revision", "candidate_revision", "content_hash", "corpus_sha256")},
            "execution_eligible": True, "qualification_only": True}


def admit(context, payload):
    authorized = authority._authorize(context, ACTION, payload)
    if authorized[3].get("reason_code") != "lifecycle_policy_activation_allowed":
        raise PermissionError("policy_execution_admission_denied")
    if not prove_loaded(authorized[1]["policy_revision"]):
        raise PermissionError("loaded_policy_identity_unproved")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, binding, decision = authority._consume(tx, context, ACTION, payload, authorized)
            scope = binding["policy_execution"]
            now = authority._trusted_now(tx)
            if now is None:
                raise PermissionError("trusted_time_unavailable")
            local, revision, _, manifest, content_hash = _render(scope["template"], scope["suffixes"], scope["policy_sha256"])
            operation = "plo-" + uuid.uuid4().hex
            grant = uuid.uuid4().hex
            stamp = now.isoformat()
            tx.execute("""INSERT OR IGNORE INTO policy_revisions(revision_id,parent_revision_id,template_id,template_version,
                canonical_parameters_json,manifest_json,content_hash,created_by_human_id,created_by_principal_type,
                created_by_principal_id,created_at,validation_status,lifecycle_status,change_summary)
                VALUES(?,?,?,?,?,?,?,?, 'human',?,?,'pending','draft','Exact signed policy note evolution')""",
                (revision, local, scope["template"]["template_id"], scope["template"]["template_version"],
                 canonical_bytes(scope["template"]["parameters"]).decode("ascii"),
                 canonical_bytes({"revision": revision, "files": manifest, "candidate_hash": content_hash}).decode("ascii"),
                 content_hash, owner, owner, stamp))
            row = tx.execute("SELECT content_hash FROM policy_revisions WHERE revision_id=?", (revision,)).fetchone()
            if not row or row["content_hash"] != content_hash:
                raise ValueError("policy_revision_conflict")
            tx.execute("""INSERT INTO policy_activation_operations(operation_id,requested_by_human_id,requested_by_principal_type,
                requested_by_principal_id,correlation_id,candidate_revision_id,prior_known_good_revision_id,state,created_at,updated_at)
                VALUES(?,?,'human',?,?,?,?,'pending',?,?)""",
                (operation, owner, owner, grant, revision, local, stamp, stamp))
            tx.execute("""INSERT INTO lite_lifecycle_policy_execution(operation_id,grant_id,owner_id,executor_principal,
                binding_json,binding_sha256,decision_id,issued_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (operation, grant, owner, EXECUTOR, canonical_bytes(binding).decode("ascii"), digest(binding),
                 decision["decision_id"], stamp, (now + timedelta(minutes=10)).isoformat()))
            rev = authority._advance(tx, authority._workspace(tx))
            authority._audit(tx, owner, "policy_execution_admitted", rev, decision_id=decision["decision_id"], grant_id=grant)
            return {"operation_id": operation, "grant_id": grant, "state": "pending", "revision": rev}


def revoke(context, payload):
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = authority._owner(tx, context)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            row = tx.execute("SELECT operation_id FROM lite_lifecycle_policy_execution WHERE grant_id=? AND revoked_at IS NULL", (payload.grant_id,)).fetchone()
            if not row:
                raise ValueError("grant_not_current")
            tx.execute("UPDATE lite_lifecycle_policy_execution SET revoked_at=? WHERE grant_id=?", (authority._iso(), payload.grant_id))
            rev = authority._advance(tx, ws)
            authority._audit(tx, owner, "policy_execution_revoked", rev, grant_id=payload.grant_id)
            return {"revision": rev, "state": "revoked"}


def get(conn, operation_id):
    row = conn.execute("SELECT * FROM lite_lifecycle_policy_execution WHERE operation_id=?", (operation_id,)).fetchone()
    return dict(row) if row else None


def current(conn, operation, *, require_claim=False):
    row = get(conn, operation["operation_id"])
    if not row or row["revoked_at"] or not gate():
        raise PermissionError("policy_execution_revoked_or_disabled")
    binding = json.loads(row["binding_json"])
    scope = binding["policy_execution"]
    ws = authority._workspace(conn)
    prefs = authority._prefs(conn)
    receipt = _receipt(conn)
    now = authority._trusted_now(conn)
    runtime = conn.execute("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    versions = automation._owner_versions(conn, row["owner_id"])
    managed = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    if (digest(binding) != row["binding_sha256"] or row["executor_principal"] != EXECUTOR
            or not versions or list(versions) != binding["versions"] or bool(managed and managed["enabled"])
            or ws["workspace_id"] != binding["workspace"] or ws["authority_epoch"] != binding["authority_epoch"]
            or prefs["profile"] != "recommended" or prefs["revision"] != binding["profile_revision"]
            or registry_revision() != binding["registry_revision"] or authority._trust(conn) != binding["trust"]
            or receipt.get("metadata_sha256") != scope["metadata_sha256"]
            or not trust_config.future(row["expires_at"], now)
            or not runtime or runtime["active_revision_id"] != scope["baseline_revision"]
            or runtime["known_good_revision_id"] != scope["baseline_revision"]
            or operation["candidate_revision_id"] != scope["candidate_revision"]
            or operation["prior_known_good_revision_id"] != scope["baseline_revision"]
            or (require_claim and (not row["claimed_at"] or not row["claim_decision_id"]))):
        raise PermissionError("policy_execution_binding_changed")
    local, candidate, _, _, content_hash = _render(scope["template"], scope["suffixes"], scope["policy_sha256"])
    if (local, candidate, content_hash) != (scope["baseline_revision"], scope["candidate_revision"], scope["content_hash"]):
        raise PermissionError("policy_execution_source_changed")
    return row, scope


def prove_loaded(revision):
    from .lite_policy_runtime_evidence import _get, compare_loaded_modules
    try:
        with read_connection() as conn:
            row = conn.execute("SELECT * FROM policy_revisions WHERE revision_id=?", (revision,)).fetchone()
        if not row:
            return False
        manifest = json.loads(row["manifest_json"])
        if isinstance(manifest, list):
            manifest = {"files": manifest}
        if (digest(manifest["files"]) != row["content_hash"]
                or _get("/v1/data/pocketlab/meta/revision") != revision
                or not compare_loaded_modules(manifest, _get("/v1/policies"))):
            return False
        values = {"template_id": row["template_id"], "template_version": row["template_version"],
                  "parameters": json.loads(row["canonical_parameters_json"])}
        return (all(canonical_bytes(_get("/v1/data/" + key)) == canonical_bytes(value) for key, value in values.items())
                and _get("/v1/data/pocketlab/meta/revision") == revision)
    except Exception:
        return False


def claim(operation):
    """Called only by the local core supervisor under its activation lock."""
    with read_connection() as conn:
        row, scope = current(conn, operation)
        if row["claimed_at"] or operation["state"] != "pending":
            raise PermissionError("policy_execution_replay")
    if (lifecycle._pointer_revision("active") != scope["baseline_revision"]
            or lifecycle._pointer_revision("known-good") != scope["baseline_revision"]
            or not prove_loaded(scope["baseline_revision"])):
        raise PermissionError("policy_baseline_identity_unproved")
    # Dedicated decision on the existing loaded baseline while the native
    # pending-operation fence blocks every ordinary protected action. No
    # caller-supplied context or service session is used.
    context = {"actor": {"type": "service", "identity_id": EXECUTOR},
               "session": {"authenticated": True, "auth_method": "local_supervisor"}}
    doc = opa.build_authorization_input(auth_context=context, action_id=CLAIM,
        target_type="lifecycle_policy_execution", target_id=operation["operation_id"],
        target_revision=row["binding_sha256"], target={"change_digest": row["binding_sha256"],
            "contract_version": 1, "purpose": EXECUTOR, "grant_current": True,
            "execution_enabled": True}, request_context={"confirmation_present": True})
    started = time.monotonic()
    opa._require_loopback_opa()
    code, response = opa._http_json("POST", opa.OPA_DECISION_PATH, {"input": doc})
    decision = opa._validate_result(response.get("result")) if code == 200 else {
        "allow": False, "reason_code": "policy_unavailable", "constraints": []}
    decision["policy_revision"] = scope["baseline_revision"]
    recorded = opa._record_decision(input_doc=doc, decision=decision,
        evaluation_ms=(time.monotonic()-started)*1000, correlation_id=operation["operation_id"])
    if not recorded["allow"] or recorded["reason_code"] != "lifecycle_policy_claim_allowed":
        raise PermissionError("policy_execution_claim_denied")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            again, current_scope = current(tx, operation)
            if again["claimed_at"] or again["binding_sha256"] != row["binding_sha256"] or current_scope != scope:
                raise PermissionError("policy_execution_replay")
            updated = tx.execute("UPDATE lite_lifecycle_policy_execution SET claimed_at=?,claim_decision_id=? WHERE operation_id=? AND claimed_at IS NULL",
                (authority._iso(), recorded["decision_id"], operation["operation_id"]))
            if updated.rowcount != 1:
                raise PermissionError("policy_execution_replay")
            authority._audit(tx, row["owner_id"], "policy_execution_claimed", authority._workspace(tx)["boundary_revision"],
                             decision_id=recorded["decision_id"], grant_id=row["grant_id"])
    return scope


def recheck(operation):
    with read_connection() as conn:
        return current(conn, operation, require_claim=True)[1]


def stage_matches(scope, stage):
    try:
        _, revision, tree, manifest, content_hash = _render(scope["template"], scope["suffixes"], scope["policy_sha256"])
        expected = set(tree) | {"manifest.json", "revision.txt"}
        entries = list(stage.iterdir())
        return (not stage.is_symlink() and set(p.name for p in entries) == expected
                and all(p.is_file() and not p.is_symlink() for p in entries)
                and all((stage / name).read_bytes() == raw.encode("utf-8") for name, raw in tree.items())
                and (stage / "revision.txt").read_text().strip() == revision
                and json.loads((stage / "manifest.json").read_text()) == {"revision": revision, "files": manifest, "candidate_hash": content_hash})
    except Exception:
        return False


def finalize(operation, stage):
    scope = recheck(operation)
    expected = scope["candidate_revision"]
    if (not stage_matches(scope, stage) or not prove_loaded(expected)
            or lifecycle._pointer_revision("active") != expected or lifecycle._pointer_revision("known-good") != expected):
        raise PermissionError("policy_execution_final_proof_failed")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row, latest = current(tx, operation, require_claim=True)
            if latest != scope:
                raise PermissionError("policy_execution_binding_changed")
            stamp = authority._iso()
            tx.execute("UPDATE policy_runtime_state SET active_revision_id=?,known_good_revision_id=?,updated_at=?,updated_by_operation_id=? WHERE state_id=1",
                       (expected, expected, stamp, operation["operation_id"]))
            tx.execute("UPDATE policy_revisions SET validation_status='valid',validated_at=?,lifecycle_status='active',activated_at=? WHERE revision_id=?",
                       (stamp, stamp, expected))
            tx.execute("UPDATE lite_lifecycle_policy_execution SET proof_sha256=? WHERE operation_id=?",
                       (digest({"revision": expected, "content_hash": scope["content_hash"]}), operation["operation_id"]))
            updated = tx.execute("UPDATE policy_activation_operations SET state='active',updated_at=?,observed_filesystem_revision=?,observed_opa_revision=?,evidence_ref='policy:trusted-note-proved' WHERE operation_id=? AND state='verifying'",
                       (stamp, expected, expected, operation["operation_id"]))
            if updated.rowcount != 1:
                raise ValueError("policy_execution_state_changed")
            authority._audit(tx, row["owner_id"], "policy_execution_completed", authority._workspace(tx)["boundary_revision"],
                             decision_id=row["claim_decision_id"], grant_id=row["grant_id"])


def stage_source(scope, directory):
    local, revision, tree, _, content_hash = _render(scope["template"], scope["suffixes"], scope["policy_sha256"])
    if (local, revision, content_hash) != (scope["baseline_revision"], scope["candidate_revision"], scope["content_hash"]):
        raise ValueError("policy_stage_contract_changed")
    for name, contents in tree.items():
        if name.endswith(".rego") and name != "revision.rego":
            path = Path(directory) / name
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(contents)
            path.chmod(0o400)


def active_compatible(conn, state, revision, repository):
    """Narrow source-consistency exception for a proved immutable note revision.

    Expiry/revocation blocks future execution, not a completed semantic-no-op
    installation. A repository change or staged-byte mismatch still fails closed.
    """
    try:
        row = get(conn, state["updated_by_operation_id"])
        if not row or not row["proof_sha256"] or not row["claim_decision_id"]:
            return False
        binding = json.loads(row["binding_json"])
        scope = binding["policy_execution"]
        local, expected, _, manifest, content_hash = _render(scope["template"], scope["suffixes"], scope["policy_sha256"])
        return (digest(binding) == row["binding_sha256"] and local == repository["revision_id"]
                and expected == revision["revision_id"] == state["known_good_revision_id"]
                and content_hash == revision["content_hash"]
                and row["proof_sha256"] == digest({"revision": expected, "content_hash": content_hash})
                and lifecycle._pointer_revision("active") == expected
                and lifecycle._pointer_revision("known-good") == expected
                and stage_matches(scope, lifecycle._state_root() / "opa" / "stage" / expected))
    except Exception:
        return False


def summary(conn):
    return [dict(row) for row in conn.execute("""SELECT e.grant_id,e.operation_id,e.executor_principal,e.expires_at,e.revoked_at,
        o.state,o.reason_code,o.candidate_revision_id,e.claimed_at,e.proof_sha256
        FROM lite_lifecycle_policy_execution e JOIN policy_activation_operations o ON o.operation_id=e.operation_id
        ORDER BY e.issued_at DESC LIMIT 20""")]
