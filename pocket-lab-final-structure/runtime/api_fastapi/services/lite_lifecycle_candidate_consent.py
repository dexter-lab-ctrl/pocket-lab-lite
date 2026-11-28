"""Exact candidate decisions, separate from all executable authority.

A signed release and a human's exact decision never register a new executor.
Only an existing locally qualified admission/claim path could consume a future
execution grant; this table is deliberately not such a grant.
"""
from __future__ import annotations

from datetime import timedelta
import json
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from ..db.connection import connection, read_connection, begin_immediate
from . import lite_lifecycle_authority as authority
from . import lite_infrastructure_automation as automation
from . import lite_release_trust_configuration as trust_config
from .lite_lifecycle_contract import canonical_bytes, digest, registry_revision


class CandidateConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,79}$")
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: Literal["accepted_for_review", "declined", "deferred"]
    confirm: Literal[True]


class CandidateRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    consent_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirm: Literal[True]


def _observation(conn):
    row = conn.execute("SELECT review_json FROM lite_release_trust_observation WHERE singleton_id=1 AND state='historical_evidence'").fetchone()
    return json.loads(row["review_json"]) if row else {}


def exact_scope(conn, payload):
    if not authority._trust(conn):
        raise ValueError("candidate_trust_not_current")
    receipt = _observation(conn)
    if receipt.get("metadata_sha256") != payload.metadata_sha256 or receipt.get("registry_revision") != registry_revision():
        raise ValueError("candidate_changed")
    review = receipt.get("capability_review") or {}
    matches = [scope for scope in review.get("exact_scopes", []) if scope.get("id") == payload.capability_id]
    if len(matches) != 1 or digest(matches[0]) != payload.scope_sha256:
        raise ValueError("candidate_scope_changed")
    return matches[0]


def binding_fields(conn, payload):
    scope = exact_scope(conn, payload)
    return {"metadata_sha256": payload.metadata_sha256, "scope_sha256": digest(scope),
            "capability_id": payload.capability_id}


def preview(context, payload):
    with read_connection() as conn:
        _, binding, fingerprint = authority._change(conn, context, "lifecycle.authority.manage", payload)
        if binding["boundary_revision"] != payload.expected_revision:
            raise ValueError("boundary_revision_changed")
        scope = exact_scope(conn, payload)
    return {"purpose": "lifecycle:" + fingerprint, "scope": scope,
            "disposition": payload.disposition, "execution_eligible": False, "confirmation_required": True}


def _stable_binding(binding):
    # Independent scopes survive unrelated boundary revision increments, but
    # never an authority epoch, policy, trust, registry or profile change.
    return {k: binding[k] for k in ("workspace", "authority_epoch", "owner", "versions",
            "profile_revision", "registry_revision", "trust", "policy_revision", "candidate")}


def record(context, payload):
    authorized = authority._authorize(context, "lifecycle.authority.manage", payload)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, binding, decision = authority._consume(tx, context, "lifecycle.authority.manage", payload, authorized)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            scope = exact_scope(tx, payload)
            now = authority._trusted_now(tx)
            if now is None:
                raise PermissionError("trusted_time_unavailable")
            rev = authority._advance(tx, ws)
            stamp = now.isoformat()
            consent = uuid.uuid4().hex
            tx.execute("""UPDATE lite_lifecycle_candidate_consent SET revoked_at=? WHERE workspace_id=?
                AND metadata_sha256=? AND capability_id=? AND revoked_at IS NULL""",
                (stamp, ws["workspace_id"], payload.metadata_sha256, payload.capability_id))
            tx.execute("""INSERT INTO lite_lifecycle_candidate_consent
                (consent_id,workspace_id,owner_id,capability_id,metadata_sha256,scope_sha256,scope_json,
                 binding_json,disposition,decision_id,issued_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (consent, ws["workspace_id"], owner, payload.capability_id, payload.metadata_sha256,
                 payload.scope_sha256, canonical_bytes(scope).decode("ascii"),
                 canonical_bytes(_stable_binding(binding)).decode("ascii"), payload.disposition,
                 decision["decision_id"], stamp, (now + timedelta(days=30)).isoformat()))
            authority._audit(tx, owner, "candidate_consent_" + payload.disposition, rev,
                             decision_id=decision["decision_id"], grant_id=consent)
            # Historical records remain bounded; current decisions for older
            # releases have no authority and are retired when a new one is recorded.
            tx.execute("UPDATE lite_lifecycle_candidate_consent SET revoked_at=? WHERE metadata_sha256<>? AND revoked_at IS NULL",
                       (stamp, payload.metadata_sha256))
            tx.execute("""DELETE FROM lite_lifecycle_candidate_consent WHERE revoked_at IS NOT NULL
                AND consent_id NOT IN (SELECT consent_id FROM lite_lifecycle_candidate_consent
                WHERE revoked_at IS NOT NULL ORDER BY issued_at DESC,consent_id DESC LIMIT 200)""")
            return {"consent_id": consent, "revision": rev, "disposition": payload.disposition, "execution_eligible": False}


def revoke(context, payload):
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = authority._owner(tx, context)
            ws = authority._workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            row = tx.execute("SELECT consent_id FROM lite_lifecycle_candidate_consent WHERE consent_id=? AND revoked_at IS NULL AND workspace_id=?",
                             (payload.consent_id, ws["workspace_id"])).fetchone()
            if not row:
                raise ValueError("candidate_consent_not_current")
            rev = authority._advance(tx, ws)
            tx.execute("UPDATE lite_lifecycle_candidate_consent SET revoked_at=? WHERE consent_id=?",
                       (authority._iso(), payload.consent_id))
            authority._audit(tx, owner, "candidate_consent_revoked", rev, grant_id=payload.consent_id)
            return {"revision": rev, "execution_eligible": False}


def status(conn, row, *, ws, prefs, trust, now, policy, receipt, owner, versions, enterprise):
    if row["revoked_at"]:
        return "revoked"
    if now is None:
        return "review_required"
    if not trust_config.future(row["expires_at"], now):
        return "expired"
    saved = json.loads(row["binding_json"])
    current = {"workspace": ws["workspace_id"], "authority_epoch": ws["authority_epoch"],
        "owner": owner, "versions": list(versions), "profile_revision": prefs["revision"],
        "registry_revision": registry_revision(), "trust": trust, "policy_revision": policy,
        "candidate": {"metadata_sha256": row["metadata_sha256"], "scope_sha256": row["scope_sha256"],
                      "capability_id": row["capability_id"]}}
    if (enterprise or not trust or not policy or receipt.get("metadata_sha256") != row["metadata_sha256"]
            or saved != current or digest(json.loads(row["scope_json"])) != row["scope_sha256"]
            or not any(digest(scope) == row["scope_sha256"] for scope in
                       (receipt.get("capability_review") or {}).get("exact_scopes", []))):
        return "review_required"
    return row["disposition"]


def summary(conn, *, ws, prefs, trust, now, policy, owner, versions, enterprise):
    receipt = _observation(conn)
    rows = conn.execute("""SELECT * FROM lite_lifecycle_candidate_consent WHERE workspace_id=?
        ORDER BY (revoked_at IS NULL) DESC,issued_at DESC,consent_id DESC LIMIT 20""", (ws["workspace_id"],)).fetchall()
    return [{"consent_id": row["consent_id"], "capability_id": row["capability_id"],
             "metadata_sha256": row["metadata_sha256"], "scope_sha256": row["scope_sha256"],
             "status": status(conn, row, ws=ws, prefs=prefs, trust=trust, now=now,
                              policy=policy, receipt=receipt, owner=owner, versions=versions, enterprise=enterprise),
             "expires_at": row["expires_at"], "execution_eligible": False} for row in rows]
