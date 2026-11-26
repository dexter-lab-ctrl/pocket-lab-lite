"""Durable local consent without an executable delegation or Owner credential."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field
from ..db.connection import connection, read_connection, begin_immediate
from . import lite_infrastructure_authority as authority
from . import lite_infrastructure_automation as automation
from . import lite_policy_opa as opa
from .lite_lifecycle_contract import CAPABILITIES, RevisionIdentities, digest, inventory, registry_revision
from .lite_lifecycle_delegation import SERVICES, BY_PURPOSE, scope_review

PROFILES = ("notify", "security", "recommended", "enterprise_managed")
# Fixed server-owned purpose map. No service principal or executor is registered.
PURPOSES = {item.purpose: item.capability_id for item in SERVICES if item.grantable}


class PreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    profile: Literal["notify", "security", "recommended"]
    confirm: Literal[True]


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    expected_profile_revision: int = Field(ge=1)
    purpose: Literal["release-reconciler", "policy-reconciler"]
    confirm: Literal[True]


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    confirm: Literal[True]


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat().replace("+00:00", "Z")


def _owner(conn, context):
    owner = authority.require_owner(conn, context)
    versions = automation._owner_versions(conn, owner)
    if not versions:
        raise PermissionError("owner_required")
    config = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    return owner, tuple(versions), bool(config and config["enabled"])


def _prefs(conn):
    row = conn.execute("SELECT revision,profile,updated_at FROM lite_lifecycle_preferences WHERE singleton_id=1").fetchone()
    return dict(row) if row else {"revision": 0, "profile": "notify", "updated_at": None}


def _workspace(conn):
    return conn.execute("SELECT workspace_id,boundary_revision,delegation_revision FROM lite_lifecycle_workspace WHERE singleton_id=1").fetchone()


def _trust(conn):
    row = conn.execute("""SELECT f.metadata_version,f.root_version,o.review_json,f.metadata_sha256
        FROM lite_release_trust_floor f JOIN lite_release_trust_observation o
        ON o.singleton_id=1 AND o.release_tag=f.release_tag
        WHERE f.singleton_id=1 AND o.state='historical_evidence'""").fetchone()
    if not row:
        return None
    review = json.loads(row["review_json"])
    if (review.get("metadata_sha256") != row["metadata_sha256"] or review.get("channel") != "stable"
        or review.get("provenance") != "verified" or review.get("authenticity") != "verified"
        or review.get("integrity") != "verified" or not authority._future(review.get("expires"))
        or not authority._future(review.get("root_expires"))):
        return None
    # This is eligibility to record review-only consent, not fresh runtime trust.
    return {"metadata_version": row["metadata_version"], "root_version": row["root_version"]}


def _policy(conn):
    row = conn.execute("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    if not row or not row["active_revision_id"] or row["active_revision_id"] != row["known_good_revision_id"]:
        return None
    if conn.execute("SELECT 1 FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') LIMIT 1").fetchone():
        return None
    return row["active_revision_id"]


def _audit(conn, owner, event, revision):
    conn.execute("INSERT INTO lite_lifecycle_audit(correlation_id,owner_id,event_type,revision,occurred_at) VALUES(?,?,?,?,?)",
                 (uuid.uuid4().hex, owner, event, revision, _iso()))
    # Long-lived revocation evidence stays in grant rows; bounded recent
    # activity mirrors other Lite operational audit views.
    conn.execute("DELETE FROM lite_lifecycle_audit WHERE event_id NOT IN (SELECT event_id FROM lite_lifecycle_audit ORDER BY event_id DESC LIMIT 2000)")


def _invalidate(conn, workspace):
    rev = workspace["boundary_revision"] + 1
    conn.execute("UPDATE lite_lifecycle_workspace SET boundary_revision=?,delegation_revision=delegation_revision+1 WHERE singleton_id=1", (rev,))
    conn.execute("UPDATE lite_lifecycle_grants SET revoked_at=? WHERE revoked_at IS NULL", (_iso(),))
    return rev


def _change(conn, context, action, payload):
    owner, versions, enterprise = _owner(conn, context)
    if enterprise:
        raise PermissionError("enterprise_managed_review_required")
    ws = _workspace(conn)
    trust = _trust(conn)
    policy = _policy(conn)
    if not policy:
        raise ValueError("policy_revision_unconfirmed")
    binding = {"action": action, "request": payload.model_dump(), "workspace": ws["workspace_id"],
               "boundary_revision": ws["boundary_revision"], "owner": owner, "versions": versions,
               "profile_revision": _prefs(conn)["revision"], "registry_revision": registry_revision(),
               "trust": dict(trust) if trust else None, "policy_revision": policy}
    return owner, binding, digest(binding)


def preview(context, action, payload):
    with read_connection() as conn:
        _, binding, fingerprint = _change(conn, context, action, payload)
        scope = None
        if isinstance(payload, GrantRequest):
            if binding["boundary_revision"] != payload.expected_revision or binding["profile_revision"] != payload.expected_profile_revision:
                raise ValueError("boundary_revision_changed")
            service = BY_PURPOSE[payload.purpose]
            cap = next(c for c in CAPABILITIES if c.id == service.capability_id)
            scope = {"purpose": service.purpose, "category": service.category, "channel": "stable",
                     "capability": cap.model_dump(mode="json"), "max_risk": "A", "expires_in_days": 30,
                     "excluded": ["mutation", "secret_access", "network", "unattended_execution"]}
        elif payload.expected_revision != binding["profile_revision"]:
            raise ValueError("preference_revision_changed")
    return {"purpose": "lifecycle:" + fingerprint, "execution_eligible": False, "confirmation_required": True, "scope": scope}


def _authorize(context, action, payload):
    with read_connection() as conn:
        owner, binding, fingerprint = _change(conn, context, action, payload)
    decision = opa.evaluate_authorization(
        auth_context=context, action_id=action, target_type="lifecycle_consent",
        target_id="local_workspace", target_revision=fingerprint,
        target={"change_digest": fingerprint, "contract_version": 1, "execution_enabled": False},
        request_context={"confirmation_present": True},
    )
    if not decision.get("allow") or decision.get("policy_revision") != binding["policy_revision"]:
        raise PermissionError("policy_revision_changed")
    if decision.get("continuation_approval_id") or decision.get("continuation_exception_id"):
        raise PermissionError("continuation_not_supported")
    return owner, binding, fingerprint, decision


def _consume(conn, context, action, payload, authorized):
    owner, binding, fingerprint, decision = authorized
    current_owner, current, current_fingerprint = _change(conn, context, action, payload)
    if current_owner != owner or current != binding or current_fingerprint != fingerprint:
        raise ValueError("authority_revision_changed")
    session = context["session"]["session_id"]
    # One-time exact consent, tied to the current session and active credential.
    row = conn.execute("""SELECT a.assurance_id,a.expires_at FROM auth_session_assurance a
        JOIN webauthn_credentials c ON c.credential_id=a.credential_id
        WHERE a.session_id=? AND a.purpose=? AND c.human_id=? AND c.revoked_at IS NULL
        ORDER BY a.satisfied_at DESC LIMIT 1""",
        (session, "lifecycle:" + fingerprint, owner)).fetchone()
    if not row or not authority._future(row["expires_at"]):
        raise PermissionError("exact_passkey_confirmation_required")
    conn.execute("DELETE FROM auth_session_assurance WHERE assurance_id=?", (row["assurance_id"],))
    return owner, binding, decision


def save_profile(context, payload: PreferenceRequest):
    # Notify is a safety-only reduction, not an OPA bypass for expansion.
    authorized = None if payload.profile == "notify" else _authorize(context, "lifecycle.preferences.manage", payload)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = _owner(tx, context)
            prefs = _prefs(tx)
            if prefs["revision"] != payload.expected_revision:
                raise ValueError("preference_revision_changed")
            if authorized:
                _consume(tx, context, "lifecycle.preferences.manage", payload, authorized)
            if prefs["profile"] == payload.profile:
                return prefs
            revision = prefs["revision"] + 1
            tx.execute("""INSERT INTO lite_lifecycle_preferences VALUES(1,?,?,?,?)
                ON CONFLICT(singleton_id) DO UPDATE SET revision=excluded.revision,profile=excluded.profile,
                updated_at=excluded.updated_at,owner_id=excluded.owner_id""",
                (revision, payload.profile, _iso(), owner))
            _invalidate(tx, _workspace(tx))
            _audit(tx, owner, "preference_saved", revision)
            return _prefs(tx)


def issue(context, payload: GrantRequest):
    authorized = _authorize(context, "lifecycle.authority.manage", payload)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, binding, decision = _consume(tx, context, "lifecycle.authority.manage", payload, authorized)
            ws = _workspace(tx)
            prefs = _prefs(tx)
            trust = _trust(tx)
            if ws["boundary_revision"] != payload.expected_revision or prefs["revision"] != payload.expected_profile_revision:
                raise ValueError("boundary_revision_changed")
            if prefs["profile"] != "recommended" or not trust:
                raise ValueError("profile_or_trust_not_ready")
            cap = next(c for c in CAPABILITIES if c.id == PURPOSES[payload.purpose])
            if not cap.standing_authorization_supported or cap.mutation or cap.network or cap.secret_access or cap.unattended or cap.risk != "A":
                raise PermissionError("non_delegable_capability")
            # At most one active grant in this deliberately bounded first
            # contract. Changing it invalidates all earlier standing consent.
            rev = _invalidate(tx, ws)
            grant = uuid.uuid4().hex
            expires = (_now() + timedelta(days=30)).isoformat().replace("+00:00", "Z")
            tx.execute("""INSERT INTO lite_lifecycle_grants(grant_id,workspace_id,boundary_revision,owner_id,
                owner_auth_version,membership_version,configuration_version,profile_revision,registry_revision,
                trust_version,root_version,policy_revision,capability_id,capability_version,purpose,channel,
                scope_json,decision_id,issued_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (grant, ws["workspace_id"], rev, owner, *binding["versions"], prefs["revision"], registry_revision(),
                 trust["metadata_version"], trust["root_version"], binding["policy_revision"], cap.id, cap.version,
                 payload.purpose, "stable", json.dumps(cap.model_dump(mode="json"), separators=(",", ":")),
                 decision["decision_id"], _iso(), expires))
            tx.execute("INSERT INTO lite_lifecycle_service_delegations VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, grant, payload.purpose, BY_PURPOSE[payload.purpose].version,
                 _workspace(tx)["delegation_revision"], _iso()))
            _audit(tx, owner, "standing_consent_recorded", rev)
            return {"revision": rev, "grant_id": grant, "execution_eligible": False}


def revoke(context, payload: RevokeRequest):
    # Revocation never needs a new permissive decision from a pending OPA revision.
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = _owner(tx, context)
            ws = _workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            rev = _invalidate(tx, ws)
            _audit(tx, owner, "standing_consent_revoked", rev)
            return {"revision": rev, "execution_eligible": False, "inflight_cancelled": False}


def evaluate_record(conn, row, *, purpose, capability_id, capability_version, channel):
    """Future consumers must additionally verify current OPA and runtime gates.
    Never returns execution permission; only a current local record disposition.
    """
    if row["revoked_at"]:
        return "revoked"
    if not authority._future(row["expires_at"]):
        return "expired"
    ws, prefs, trust = _workspace(conn), _prefs(conn), _trust(conn)
    cap = next((c for c in CAPABILITIES if c.id == capability_id), None)
    versions = automation._owner_versions(conn, row["owner_id"])
    if (not cap or PURPOSES.get(purpose) != capability_id or row["purpose"] != purpose
        or row["capability_id"] != capability_id or row["capability_version"] != capability_version
        or cap.version != capability_version or channel != row["channel"]
        or row["workspace_id"] != ws["workspace_id"] or row["boundary_revision"] != ws["boundary_revision"]
        or row["profile_revision"] != prefs["revision"] or prefs["profile"] != "recommended"
        or row["registry_revision"] != registry_revision()
        or not trust or row["trust_version"] != trust["metadata_version"] or row["root_version"] != trust["root_version"]
        or row["policy_revision"] != _policy(conn)
        or not versions or tuple(versions) != (row["owner_auth_version"], row["membership_version"], row["configuration_version"])
        or json.loads(row["scope_json"]) != cap.model_dump(mode="json")):
        return "review_required"
    return "within_recorded_boundary"


def evaluate_delegation(conn, *, delegation_id, purpose, internal_owner, proposed, channel, category, opa_allowed, runtime_ready):
    row = conn.execute("""SELECT g.*,d.contract_version AS service_version,d.delegation_revision AS service_revision
        FROM lite_lifecycle_service_delegations d JOIN lite_lifecycle_grants g ON g.grant_id=d.grant_id
        WHERE d.delegation_id=? AND d.purpose=?""", (delegation_id, purpose)).fetchone()
    from .lite_lifecycle_delegation import DelegationReview
    if not row or purpose not in BY_PURPOSE:
        return DelegationReview(disposition="outside", reason_code="delegation_not_found")
    service = BY_PURPOSE[purpose]
    if row["service_version"] != service.version or row["service_revision"] != _workspace(conn)["delegation_revision"]:
        return DelegationReview(disposition="revoked" if row["revoked_at"] else "unknown", reason_code="delegation_revision_changed")
    cap = next((c for c in CAPABILITIES if c.id == row["capability_id"]), None)
    if cap is None:
        return DelegationReview(disposition="unknown", reason_code="capability_unknown")
    state = evaluate_record(conn, row, purpose=purpose, capability_id=cap.id, capability_version=cap.version, channel=channel)
    return scope_review(purpose=purpose, internal_owner=internal_owner, ceiling=cap, proposed=proposed,
        channel=channel, category=category, current_record=state, opa_allowed=opa_allowed, runtime_ready=runtime_ready)


def summary(context):
    with read_connection() as conn:
        _, versions, enterprise = _owner(conn, context)
        ws = _workspace(conn)
        prefs = _prefs(conn)
        receipt = conn.execute("SELECT receipt_id,release_tag,checked_at,receipt_json FROM lite_release_trust_receipts ORDER BY metadata_version DESC LIMIT 1").fetchone()
        trust_observation = conn.execute("SELECT state,reason_code,review_json FROM lite_release_trust_observation WHERE singleton_id=1").fetchone()
        rows = conn.execute("""SELECT g.*,d.delegation_id FROM lite_lifecycle_grants g LEFT JOIN lite_lifecycle_service_delegations d ON d.grant_id=g.grant_id ORDER BY boundary_revision DESC LIMIT 20""").fetchall()
        grants = [{"grant_id": row["grant_id"], "purpose": row["purpose"], "capability_id": row["capability_id"],
                   "capability_version": row["capability_version"], "expires_at": row["expires_at"],
                   "delegation_id": row["delegation_id"], "channel": row["channel"],
                   "scope": json.loads(row["scope_json"]), "category": BY_PURPOSE[row["purpose"]].category if row["purpose"] in BY_PURPOSE else "unknown",
                   "status": evaluate_record(conn, row, purpose=row["purpose"], capability_id=row["capability_id"],
                                             capability_version=row["capability_version"], channel=row["channel"])}
                  for row in rows]
        audit = [dict(row) for row in conn.execute("SELECT correlation_id,event_type,revision,occurred_at FROM lite_lifecycle_audit ORDER BY event_id DESC LIMIT 20")]
        identity = conn.execute("SELECT release_tag,verified,source_commit,artifact_sha256 FROM lite_installed_release_identity ORDER BY updated_at_epoch_ms DESC LIMIT 1").fetchone()
        policy = conn.execute("""SELECT r.content_hash,r.template_version,r.revision_id FROM policy_runtime_state s
            JOIN policy_revisions r ON s.active_revision_id=r.revision_id WHERE s.state_id=1""").fetchone()
        fence = conn.execute("SELECT * FROM lite_system_health_activation_fence WHERE singleton_id=1").fetchone()
        floor = conn.execute("SELECT metadata_version,root_version FROM lite_release_trust_floor WHERE singleton_id=1").fetchone()
        eligible_to_record = bool(_trust(conn)) and not enterprise and prefs["profile"] == "recommended"
        revisions = RevisionIdentities(
            release_source_commit=identity["source_commit"] or None if identity else None,
            frontend_artifact_sha256=identity["artifact_sha256"] or None if identity else None,
            policy_content_sha256=policy["content_hash"] if policy else None,
            policy_contract_version=policy["template_version"] if policy else None,
            # DB active revision is not an independently observed loaded OPA revision.
            capability_registry_revision=registry_revision(), boundary_revision=ws["boundary_revision"],
            workspace_governance_revision=versions[2], authorization_version=versions[0],
            delegation_revision=ws["delegation_revision"], trust_root_version=floor["root_version"] if floor else None,
            signed_metadata_version=floor["metadata_version"] if floor else None,
            recovery_assisted_source_revision=fence["assisted_source_revision"] or None if fence else None,
            recovery_assisted_runtime_revision=fence["assisted_runtime_revision"] or None if fence else None,
            recovery_automatic_source_revision=fence["automatic_source_revision"] or None if fence else None,
            recovery_automatic_runtime_revision=fence["automatic_runtime_revision"] or None if fence else None)
        history = []
        for item in conn.execute("SELECT receipt_id,receipt_json FROM lite_release_trust_receipts ORDER BY metadata_version DESC LIMIT 20"):
            raw = json.loads(item["receipt_json"])
            history.append({"receipt_id": item["receipt_id"], **{key: raw.get(key) for key in
                ("release_tag","checked_at","expires","authenticity","integrity","provenance","compatibility","impact")}})
    latest = json.loads(trust_observation["review_json"]) if trust_observation else {}
    raw = latest or (json.loads(receipt["receipt_json"]) if receipt else {})
    historical = {key: raw.get(key) for key in ("release_tag","checked_at","expires","root_expires","authenticity","integrity","provenance","compatibility","impact","reason_code")} if raw else None
    state = trust_observation["state"] if trust_observation else "trust_setup_required"
    if state == "historical_evidence" and (not authority._future(raw.get("expires")) or not authority._future(raw.get("root_expires"))):
        state = "metadata_expired"
    return {"schema_version": 1, "registry_revision": registry_revision(),
            "preferences": prefs, "enterprise_managed": enterprise,
            "boundary_revision": ws["boundary_revision"], "capabilities": inventory(),
            "revisions": revisions.model_dump(), "assessment": latest.get("assessment"),
            "services": [{"purpose": item.purpose,"category": item.category,"grantable": item.grantable,
                          "version": item.version,"execution_eligible": False} for item in SERVICES],
            "can_record_consent": eligible_to_record, "grants": grants, "audit": audit,
            "release_trust": {"state": state,
                              "reason_code": trust_observation["reason_code"] if trust_observation else "independent_root_required",
                              "installed_tag": identity["release_tag"] or None if identity else None,
                              "historical_identity_verified": bool(identity and identity["verified"]),
                              "receipt": historical, "history": history, "fresh_verification": False},
            "effective_execution": {"software": False, "policy": False, "delegated": False},
            "execution_eligible": False, "sanitized": True}
