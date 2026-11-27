"""Exact, one-shot release preparation through the existing release worker.

This authority does not permit code execution or cutover. A separately signed
native promotion AND recovery authorization must bind the prepared handoff.
Only the disposable qualification lane can prepare executable candidates.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field
from ..db.connection import connection, read_connection, begin_immediate, database_path
from . import lite_lifecycle_authority as authority, lite_infrastructure_automation as automation
from . import lite_release_trust_configuration as trust_config, lite_policy_opa as opa
from .lite_lifecycle_contract import canonical_bytes, digest, registry_revision

ACTION = "lifecycle.release.prepare"
CLAIM = "lifecycle.release.claim"
EXECUTOR = "release-reconciler"


class ReleasePreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal[True]


class ReleasePreparationRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    grant_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirm: Literal[True]


def gate():
    if os.environ.get("POCKETLAB_RELEASE_COORDINATED_EXECUTION") != "1":
        return False
    try:
        from . import qualification_context as q, release_runtime
        if not q.enabled() or not os.environ.get("POCKETLAB_STATE_DIR"):
            return False
        root = q.root()
        state = Path(os.environ["POCKETLAB_STATE_DIR"])
        paths = release_runtime.release_paths()
        current = paths["current_link"]
        for path in (state, database_path(), paths["staging_root"], paths["releases_dir"], current.parent):
            if q._resolved_without_symlink_escape(path, root) == root:
                return False
        if current.exists():
            current.resolve(strict=True).relative_to(paths["releases_dir"])
        return True
    except Exception:
        return False


def state_root():
    if not gate():
        raise PermissionError("coordinated_qualification_required")
    return Path(os.environ["POCKETLAB_STATE_DIR"]).resolve(strict=True)


def _receipt(conn):
    row = conn.execute("SELECT review_json FROM lite_release_trust_observation WHERE singleton_id=1 AND state='historical_evidence'").fetchone()
    return json.loads(row["review_json"]) if row else {}


def _scope(receipt, baseline):
    from .lite_policy_candidate_differential import supported_differential
    if (receipt.get("source_package", {}).get("state") != "verified_for_review"
            or receipt.get("provenance") != "verified" or receipt.get("authenticity") != "verified"
            or receipt.get("integrity") != "verified" or receipt.get("schema_range_matches") is not True
            or receipt.get("registry_revision") != registry_revision()
            or receipt.get("capability_review", {}).get("total") != 0
            or receipt.get("migration_review", {}).get("state") not in {"unchanged","review_required"}
            or receipt.get("migration_review", {}).get("applied_ledger", {}).get("state") != "ledger_matches"
            or receipt.get("coordinated_preflight", {}).get("state") != "isolated_preflight_checked"
            or receipt.get("coordinated_preflight", {}).get("migration_execution", {}).get("state") != "synthetic_schema_rehearsed"):
        raise PermissionError("coordinated_candidate_unproved")
    policy = receipt.get("policy_review", {})
    observation = receipt.get("policy_runtime_observation", {})
    if (observation.get("state") != "modules_match" or observation.get("manifest_data_identity") != "registered_roots_match"
            or observation.get("data_identity") != "registered_template_matches"
            or not (policy.get("state") == "source_unchanged" or supported_differential(policy.get("differential", {})))):
        raise PermissionError("coordinated_policy_unproved")
    import re
    hashes = {"metadata_sha256": receipt["metadata_sha256"], "source_sha256": receipt["source_package"]["sha256"],
              "frontend_sha256": receipt["artifact_sha256"], "policy_sha256": receipt["policy_sha256"],
              "migration_sha256": receipt["migration_inventory_sha256"]}
    if (any(not isinstance(v,str) or not re.fullmatch(r"[a-f0-9]{64}", v) for v in hashes.values())
            or not isinstance(baseline,str) or not re.fullmatch(r"[a-f0-9]{40}", baseline)
            or not re.fullmatch(r"[a-f0-9]{40}", receipt["source_commit"])):
        raise ValueError("coordinated_identity_unproved")
    return {**hashes, "source_commit": receipt["source_commit"], "baseline_commit": baseline,
            "release_tag": receipt["release_tag"], "current_schema": receipt["current_schema"],
            "target_schema": receipt["migration_review"]["target_schema"],
            "policy_baseline": observation["observed_revision"], "purpose": EXECUTOR}


def binding_fields(conn, payload):
    if not gate() or not authority._trust(conn) or authority._prefs(conn)["profile"] != "recommended":
        raise PermissionError("coordinated_qualification_required")
    ws = authority._workspace(conn)
    if ws["boundary_revision"] != payload.expected_revision:
        raise ValueError("boundary_revision_changed")
    receipt = _receipt(conn)
    if receipt.get("metadata_sha256") != payload.metadata_sha256:
        raise ValueError("candidate_changed")
    row = conn.execute("SELECT installed_source_commit FROM release_runtime_projection WHERE owner='release'").fetchone()
    if not row:
        raise ValueError("coordinated_identity_unproved")
    scope = _scope(receipt, row["installed_source_commit"])
    if scope["policy_baseline"] != authority._policy(conn):
        raise ValueError("policy_revision_changed")
    return scope


def preview(context, payload):
    with read_connection() as conn:
        _, binding, fingerprint = authority._change(conn, context, ACTION, payload)
    return {"purpose":"lifecycle:" + fingerprint, "scope":binding["release_preparation"],
            "confirmation_required":True, "qualification_only":True,
            "cutover_authorized":False}


def admit(context, payload):
    authorized = authority._authorize(context, ACTION, payload)
    if authorized[3].get("reason_code") != "lifecycle_release_preparation_allowed":
        raise PermissionError("release_preparation_denied")
    from .lite_lifecycle_policy_execution import prove_loaded
    if not prove_loaded(authorized[1]["policy_revision"]):
        raise PermissionError("loaded_policy_identity_unproved")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, binding, decision = authority._consume(tx, context, ACTION, payload, authorized)
            now = authority._trusted_now(tx)
            if now is None:
                raise PermissionError("trusted_time_unavailable")
            stamp = now.isoformat()
            # Retire expired pre-cutover records without reviving authority.
            tx.execute("UPDATE lite_lifecycle_release_execution SET state='failed',reason_code='grant_expired',updated_at=? WHERE state IN ('pending','claimed','prepared') AND expires_at<=?", (stamp,stamp))
            if tx.execute("SELECT 1 FROM lite_lifecycle_release_execution WHERE state IN ('pending','claimed','prepared','cutover_claimed') LIMIT 1").fetchone():
                raise ValueError("coordinated_operation_in_progress")
            grant = uuid.uuid4().hex
            tx.execute("""INSERT INTO lite_lifecycle_release_execution(grant_id,owner_id,metadata_sha256,executor_principal,
                binding_json,binding_sha256,decision_id,issued_at,expires_at,state,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'pending',?)""",
                (grant,owner,payload.metadata_sha256,EXECUTOR,canonical_bytes(binding).decode("ascii"),
                 digest(binding),decision["decision_id"],stamp,(now+timedelta(minutes=10)).isoformat(),stamp))
            rev = authority._advance(tx,authority._workspace(tx))
            authority._audit(tx,owner,"release_preparation_admitted",rev,decision_id=decision["decision_id"],grant_id=grant)
            return {"grant_id":grant,"state":"pending","revision":rev,"cutover_authorized":False}


def revoke(context,payload):
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner,_,_ = authority._owner(tx,context)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            row = tx.execute("SELECT state FROM lite_lifecycle_release_execution WHERE grant_id=? AND revoked_at IS NULL", (payload.grant_id,)).fetchone()
            if not row or row["state"] not in {"pending","claimed","prepared","cutover_claimed"}:
                raise ValueError("grant_not_current")
            # Revoking a consumed cutover grant is not cancellation. The
            # controller must reconcile the in-flight transaction.
            tx.execute("""UPDATE lite_lifecycle_release_execution SET revoked_at=?,updated_at=?,
                state=CASE WHEN state='cutover_claimed' THEN state ELSE 'revoked' END WHERE grant_id=?""",
                (authority._iso(),authority._iso(),payload.grant_id))
            rev = authority._advance(tx,ws)
            authority._audit(tx,owner,"release_preparation_revoked",rev,grant_id=payload.grant_id)
            return {"revision":rev,"state":"revoked","cutover_cancellation_guaranteed":False}


def _lease_dict(lease):
    return {"generation":lease.generation,"worker_generation":lease.worker_generation,"command_id":lease.command_id}


def current(conn,grant_id,*,lease=None,states=("pending","claimed","prepared")):
    row = conn.execute("SELECT * FROM lite_lifecycle_release_execution WHERE grant_id=?", (grant_id,)).fetchone()
    if not row or row["state"] not in states or row["revoked_at"] or not gate():
        raise PermissionError("release_preparation_not_current")
    binding = json.loads(row["binding_json"])
    scope = binding["release_preparation"]
    ws = authority._workspace(conn)
    prefs = authority._prefs(conn)
    versions = automation._owner_versions(conn,row["owner_id"])
    enterprise = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    release = conn.execute("SELECT installed_source_commit FROM release_runtime_projection WHERE owner='release'").fetchone()
    if (digest(binding) != row["binding_sha256"] or row["executor_principal"] != EXECUTOR
            or not versions or list(versions) != binding["versions"] or bool(enterprise and enterprise["enabled"])
            or ws["workspace_id"] != binding["workspace"] or ws["authority_epoch"] != binding["authority_epoch"]
            or prefs["profile"] != "recommended" or prefs["revision"] != binding["profile_revision"]
            or authority._trust(conn, release_lease=lease) != binding["trust"]
            or not trust_config.future(row["expires_at"],authority._trusted_now(conn))
            or registry_revision() != binding["registry_revision"] or authority._policy(conn) != binding["policy_revision"]
            or not release or _scope(_receipt(conn),release["installed_source_commit"]) != scope):
        raise PermissionError("release_preparation_binding_changed")
    if lease and row["state"] != "pending" and (row["command_id"],row["lease_generation"],row["worker_generation"]) != (
            lease["command_id"],lease["generation"],lease["worker_generation"]):
        raise PermissionError("release_preparation_lease_changed")
    return dict(row), scope


def claim(lease):
    """The sole claim caller is the existing release worker, never HTTP."""
    from . import release_runtime
    release_runtime._require_worker()
    if not gate():
        return None
    lease_doc = _lease_dict(lease)
    with read_connection() as conn:
        found = conn.execute("SELECT grant_id FROM lite_lifecycle_release_execution WHERE state='pending' AND revoked_at IS NULL").fetchone()
        if not found:
            return None
        row,scope = current(conn,found["grant_id"],lease=lease_doc,states=("pending",))
    from .lite_lifecycle_policy_execution import prove_loaded
    if not prove_loaded(scope["policy_baseline"]):
        raise PermissionError("loaded_policy_identity_unproved")
    decision = opa.evaluate_authorization(auth_context={"actor":{"type":"service","identity_id":EXECUTOR},
        "session":{"authenticated":True,"auth_method":"internal_worker"}},
        action_id=CLAIM,target_type="lifecycle_release_preparation",target_id=row["grant_id"],
        target_revision=row["binding_sha256"],target={"change_digest":row["binding_sha256"],
            "contract_version":1,"purpose":EXECUTOR,"execution_enabled":True,"grant_current":True},
        request_context={"confirmation_present":True})
    if (not decision.get("allow") or decision.get("reason_code")!="lifecycle_release_claim_allowed"
            or decision.get("policy_revision")!=scope["policy_baseline"]
            or decision.get("continuation_approval_id") or decision.get("continuation_exception_id")):
        raise PermissionError("release_preparation_claim_denied")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            again,latest = current(tx,row["grant_id"],lease=lease_doc,states=("pending",))
            if again["binding_sha256"]!=row["binding_sha256"] or latest!=scope:
                raise PermissionError("release_preparation_binding_changed")
            changed = tx.execute("""UPDATE lite_lifecycle_release_execution SET state='claimed',command_id=?,
                lease_generation=?,worker_generation=?,claim_decision_id=?,updated_at=? WHERE grant_id=? AND state='pending'""",
                (lease.command_id,lease.generation,lease.worker_generation,decision["decision_id"],authority._iso(),row["grant_id"]))
            if changed.rowcount!=1:
                raise PermissionError("release_preparation_replay")
            authority._audit(tx,row["owner_id"],"release_preparation_claimed",authority._workspace(tx)["boundary_revision"],
                decision_id=decision["decision_id"],grant_id=row["grant_id"])
    return {"grant_id":row["grant_id"],"lease":lease_doc}


def finish(tx, lease, observation):
    lease_doc = _lease_dict(lease)
    row = tx.execute("""SELECT * FROM lite_lifecycle_release_execution WHERE state='claimed'
        AND command_id=? AND lease_generation=? AND worker_generation=?""",
        (lease.command_id,lease.generation,lease.worker_generation)).fetchone()
    if not row:
        return
    handoff = (observation.get("receipt") or {}).get("coordinated_handoff") or {}
    try:
        again,scope = current(tx,row["grant_id"],lease=lease_doc,states=("claimed",))
        import re
        valid = (handoff.get("state")=="prepared" and handoff.get("grant_id")==row["grant_id"]
            and re.fullmatch(r"[a-f0-9]{64}",str(handoff.get("handoff_sha256") or "")) is not None)
    except Exception:
        valid = False
    tx.execute("UPDATE lite_lifecycle_release_execution SET state=?,handoff_sha256=?,reason_code=?,updated_at=? WHERE grant_id=?",
        ("prepared" if valid else "failed",handoff.get("handoff_sha256") if valid else None,
         "" if valid else "release_preparation_unproved",authority._iso(),row["grant_id"]))
    authority._audit(tx,row["owner_id"],"release_preparation_prepared" if valid else "release_preparation_failed",
        authority._workspace(tx)["boundary_revision"],grant_id=row["grant_id"])


def summary(conn):
    return [dict(row) for row in conn.execute("""SELECT grant_id,metadata_sha256,state,expires_at,
        revoked_at,reason_code,handoff_sha256 FROM lite_lifecycle_release_execution ORDER BY issued_at DESC LIMIT 20""")]
