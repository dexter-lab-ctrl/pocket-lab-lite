"""Exact activation and worker claim for one supported optional capability.

Candidate review and candidate consent remain non-executable.  This module
adds a separate, short-lived activation record for the existing
``projection_scheduler`` owner only; it is not a capability dispatcher.
"""
from __future__ import annotations

from datetime import timedelta
import json
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from ..db.connection import begin_immediate, connection, read_connection
from . import lite_infrastructure_automation as automation
from . import lite_infrastructure_operations as operations
from . import lite_lifecycle_authority as authority
from . import lite_policy_opa as opa
from . import lite_runtime_identity
from . import lite_release_trust_configuration as trust_config
from .lite_lifecycle_contract import Capability, canonical_bytes, digest, execution_capability_binding, registry_revision

ACTION = "lifecycle.capability.activate"
CLAIM_ACTION = "lifecycle.capability.claim"
CAPABILITY_ID = "system.activity_history.reconcile.activate"
EXECUTION_OWNER = "projection_scheduler"
PURPOSE = "system-health-scheduler"
OPERATION = "projection.reconcile"


def capability() -> Capability:
    from .lite_lifecycle_contract import EXECUTION_CAPABILITIES
    return next(item for item in EXECUTION_CAPABILITIES if item.id == CAPABILITY_ID)


class CapabilityActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    capability_id: Literal["system.activity_history.reconcile.activate"]
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal[True]


class CapabilityActivationRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    activation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirm: Literal[True]


def _receipt(conn):
    row = conn.execute("SELECT review_json FROM lite_release_trust_observation WHERE singleton_id=1 AND state='historical_evidence'").fetchone()
    return json.loads(row["review_json"]) if row else {}


def _scope(conn, payload: CapabilityActivationRequest) -> dict:
    from .lite_lifecycle_candidate_consent import exact_scope
    if payload.capability_id != CAPABILITY_ID:
        raise PermissionError("capability_not_supported")
    receipt = _receipt(conn)
    if receipt.get("metadata_sha256") != payload.metadata_sha256 or receipt.get("registry_revision") != registry_revision():
        raise ValueError("capability_candidate_changed")
    review_scope = exact_scope(conn, payload)
    after = review_scope.get("after") if isinstance(review_scope, dict) else None
    expected = capability().model_dump(mode="json")
    if not isinstance(after, dict) or after != expected or digest(review_scope) != payload.scope_sha256:
        raise ValueError("capability_scope_changed")
    now = authority._trusted_now(conn)
    consent = conn.execute("""SELECT disposition,expires_at,revoked_at FROM lite_lifecycle_candidate_consent
        WHERE workspace_id=? AND capability_id=? AND metadata_sha256=? AND scope_sha256=?
        ORDER BY issued_at DESC LIMIT 1""",
        (authority._workspace(conn)["workspace_id"], CAPABILITY_ID, payload.metadata_sha256, payload.scope_sha256)).fetchone()
    if not consent or consent["revoked_at"] or consent["disposition"] != "accepted_for_review" or not now or not trust_config.future(consent["expires_at"], now):
        raise PermissionError("candidate_consent_required")
    return {"metadata_sha256": payload.metadata_sha256, "scope_sha256": payload.scope_sha256,
            "capability": expected, "consent": "accepted_for_review"}


def binding_fields(conn, payload: CapabilityActivationRequest):
    scope = _scope(conn, payload)
    ws = authority._workspace(conn)
    runtime = lite_runtime_identity.public_projection(conn)
    return {**execution_capability_binding("system_health.automatic"),
            "purpose": PURPOSE, "execution_owner": EXECUTION_OWNER,
            "operation_id": OPERATION, "workspace": ws["workspace_id"],
            "authority_epoch": ws["authority_epoch"], "policy_revision": authority._policy(conn),
            "metadata_sha256": payload.metadata_sha256, "scope_sha256": payload.scope_sha256,
            "scope": scope, "runtime_identity_sha256": runtime.get("identity_sha256"),
            "runtime_generation": runtime.get("coordinated_generation")}


def preview(context, payload):
    with read_connection() as conn:
        _, binding, fingerprint = authority._change(conn, ACTION, payload)
        runtime = lite_runtime_identity.public_projection(conn)
    return {"purpose": "lifecycle:" + fingerprint,
            "scope": {"capability_id": CAPABILITY_ID, "operation_id": OPERATION,
                      "execution_owner": EXECUTION_OWNER, "candidate_scope_sha256": payload.scope_sha256},
            "runtime_identity": runtime,
            "activation_required": True, "execution_eligible": False,
            "confirmation_required": True, "qualification_only": True}


def activate(context, payload):
    authorized = authority._authorize(context, ACTION, payload)
    if authorized[3].get("reason_code") != "lifecycle_capability_activation_allowed":
        raise PermissionError("capability_activation_admission_denied")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, binding, decision = authority._consume(tx, context, ACTION, payload, authorized)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            runtime = lite_runtime_identity.public_projection(tx)
            if runtime.get("status") != "stable":
                raise PermissionError("runtime_identity_unavailable")
            if binding.get("runtime_identity_sha256") != runtime.get("identity_sha256"):
                raise PermissionError("runtime_identity_changed")
            now = authority._trusted_now(tx)
            if now is None:
                raise PermissionError("trusted_time_unavailable")
            active = tx.execute("""SELECT activation_id FROM lite_lifecycle_capability_activation
                WHERE workspace_id=? AND capability_id=? AND state IN ('activated','blocked')""",
                (ws["workspace_id"], CAPABILITY_ID)).fetchone()
            if active:
                raise ValueError("capability_activation_already_current")
            activation_id = uuid.uuid4().hex
            stamp = now.isoformat().replace("+00:00", "Z")
            record = {**binding, "owner_id": owner, "activation_id": activation_id,
                      "issued_at": stamp, "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")}
            tx.execute("""INSERT INTO lite_lifecycle_capability_activation(
                activation_id,workspace_id,owner_id,capability_id,capability_version,
                metadata_sha256,scope_sha256,scope_json,binding_json,binding_sha256,
                decision_id,issued_at,expires_at,authority_epoch,policy_revision,
                execution_owner,state,reason_code,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (activation_id, ws["workspace_id"], owner, CAPABILITY_ID, 1,
                 payload.metadata_sha256, payload.scope_sha256,
                 canonical_bytes(binding["scope"]).decode("ascii"),
                 canonical_bytes(record).decode("ascii"), digest(record),
                 decision["decision_id"], stamp, record["expires_at"], ws["authority_epoch"],
                 binding["policy_revision"], EXECUTION_OWNER, "activated", "", stamp))
            rev = authority._advance(tx, ws)
            authority._audit(tx, owner, "capability_activation_recorded", rev,
                             decision_id=decision["decision_id"], grant_id=activation_id)
            return {"activation_id": activation_id, "revision": rev, "state": "activated",
                    "execution_owner": EXECUTION_OWNER, "execution_eligible": True}


def revoke(context, payload):
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = authority._owner(tx, context)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            row = tx.execute("""SELECT activation_id FROM lite_lifecycle_capability_activation
                WHERE activation_id=? AND workspace_id=? AND state IN ('activated','blocked')""",
                (payload.activation_id, ws["workspace_id"])).fetchone()
            if not row:
                raise ValueError("capability_activation_not_current")
            stamp = authority._iso()
            tx.execute("UPDATE lite_lifecycle_capability_activation SET state='revoked',reason_code='owner_revoked',updated_at=? WHERE activation_id=?",
                       (stamp, payload.activation_id))
            rev = authority._advance(tx, ws)
            authority._audit(tx, owner, "capability_activation_revoked", rev, grant_id=payload.activation_id)
            return {"activation_id": payload.activation_id, "revision": rev, "state": "revoked",
                    "execution_eligible": False}


def _row(conn):
    return conn.execute("""SELECT * FROM lite_lifecycle_capability_activation
        WHERE capability_id=? ORDER BY issued_at DESC LIMIT 1""", (CAPABILITY_ID,)).fetchone()


def execution_enabled(conn):
    try:
        row = _row(conn)
    except Exception as exc:
        # Older disposable fixtures can intentionally stop before the optional
        # capability migration.  Capability absence is a closed gate, not a
        # reason for a read path or scheduler to fail open.
        if "no such table" in str(exc).lower():
            return False
        raise
    if not row or row["state"] != "activated" or not operations.automatic_gate_open():
        return False
    now = authority._trusted_now(conn)
    if not now or not trust_config.future(row["expires_at"], now):
        return False
    ws = authority._workspace(conn)
    runtime = lite_runtime_identity.public_projection(conn)
    try:
        binding = json.loads(row["binding_json"])
    except (TypeError, ValueError):
        return False
    versions = automation._owner_versions(conn, row["owner_id"])
    return (row["execution_owner"] == EXECUTION_OWNER
            and row["authority_epoch"] == ws["authority_epoch"]
            and row["policy_revision"] == authority._policy(conn)
            and row["binding_sha256"] == digest(binding)
            and binding.get("runtime_identity_sha256") == runtime.get("identity_sha256")
            and runtime.get("status") == "stable"
            and versions is not None)


def claim(attempt_id: str):
    """Recheck the exact activation at the existing worker owner boundary."""
    with read_connection() as conn:
        if not execution_enabled(conn):
            raise PermissionError("capability_activation_unavailable")
        row = _row(conn)
        binding = json.loads(row["binding_json"])
        context = {"actor": {"type": "service", "identity_id": "system-health-scheduler"},
                   "session": {"authenticated": True, "auth_method": "internal_worker"}}
        decision = opa.evaluate_authorization(
            auth_context=context, action_id=CLAIM_ACTION,
            target_type="lifecycle_capability_activation", target_id=row["activation_id"],
            target_revision=row["binding_sha256"],
            target={"change_digest": row["binding_sha256"], "contract_version": 1,
                    "purpose": PURPOSE, "capability_id": CAPABILITY_ID,
                    "execution_enabled": True, "grant_current": True},
            request_context={"confirmation_present": True})
    if not decision.get("allow") or decision.get("reason_code") != "lifecycle_capability_claim_allowed":
        raise PermissionError("capability_claim_denied")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _row(tx)
            if not row or not execution_enabled(tx) or row["claimed_at"]:
                raise PermissionError("capability_claim_replay")
            updated = tx.execute("""UPDATE lite_lifecycle_capability_activation
                SET claimed_at=?,claim_decision_id=?,last_attempt_id=?,updated_at=?
                WHERE activation_id=? AND state='activated' AND claimed_at IS NULL""",
                (authority._iso(), decision["decision_id"], attempt_id, authority._iso(), row["activation_id"]))
            if updated.rowcount != 1:
                raise PermissionError("capability_claim_replay")
    return {"activation_id": row["activation_id"], "binding_sha256": row["binding_sha256"],
            "decision_id": decision["decision_id"], "execution_owner": EXECUTION_OWNER}


def summary(conn):
    try:
        rows = conn.execute("""SELECT activation_id,capability_id,capability_version,execution_owner,
            state,issued_at,expires_at,claimed_at,last_attempt_id,reason_code,terminal_evidence_sha256
            FROM lite_lifecycle_capability_activation ORDER BY issued_at DESC LIMIT 20""").fetchall()
    except Exception as exc:
        if "no such table" in str(exc).lower():
            return []
        raise
    result = []
    now = authority._trusted_now(conn)
    for row in rows:
        item = dict(row)
        if item["state"] == "activated" and (not now or not trust_config.future(item["expires_at"], now)):
            item["state"] = "expired"
            item["reason_code"] = "activation_expired"
        item["execution_eligible"] = bool(item["state"] == "activated" and execution_enabled(conn))
        result.append(item)
    return result
