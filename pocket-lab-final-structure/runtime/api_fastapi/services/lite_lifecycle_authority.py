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
from . import lite_release_trust_configuration as trust_config
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
    grant_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
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
    return conn.execute("SELECT workspace_id,boundary_revision,delegation_revision,authority_epoch FROM lite_lifecycle_workspace WHERE singleton_id=1").fetchone()


def _trust(conn):
    row = conn.execute("""SELECT f.metadata_version,f.root_version,o.review_json,f.metadata_sha256
        FROM lite_release_trust_floor f JOIN lite_release_trust_observation o
        ON o.singleton_id=1 AND o.release_tag=f.release_tag
        WHERE f.singleton_id=1 AND o.state='historical_evidence'""").fetchone()
    if not row:
        return None
    review = json.loads(row["review_json"])
    now = trust_config.prepared_now(conn, review)
    release = conn.execute("SELECT latest_tag,status FROM release_runtime_projection WHERE owner='release'").fetchone()
    if not release or release["status"] != "healthy" or release["latest_tag"] != review.get("release_tag"):
        return None
    if (review.get("metadata_sha256") != row["metadata_sha256"] or review.get("channel") != "stable"
        or review.get("provenance") != "verified" or review.get("authenticity") != "verified"
        or review.get("integrity") != "verified" or not trust_config.future(review.get("expires"), now)
        or not trust_config.future(review.get("root_expires"), now)):
        return None
    # This is eligibility to record review-only consent, not fresh runtime trust.
    return {"metadata_version": row["metadata_version"], "root_version": row["root_version"],
            "configuration_revision": review["configuration_revision"], "root_sha256": review["root_sha256"],
            "attestation_root_sha256": review["attestation_root_sha256"]}

def _trusted_now(conn):
    row = conn.execute("SELECT review_json FROM lite_release_trust_observation WHERE singleton_id=1 AND state='historical_evidence'").fetchone()
    return trust_config.prepared_now(conn, json.loads(row["review_json"])) if row else None


def _policy(conn):
    row = conn.execute("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    if not row or not row["active_revision_id"] or row["active_revision_id"] != row["known_good_revision_id"]:
        return None
    if conn.execute("SELECT 1 FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') LIMIT 1").fetchone():
        return None
    return row["active_revision_id"]


def _audit(conn, owner, event, revision, *, decision_id=None, grant_id=None, reason_code=""):
    conn.execute("INSERT INTO lite_lifecycle_audit(correlation_id,owner_id,event_type,revision,occurred_at,decision_id,grant_id,reason_code) VALUES(?,?,?,?,?,?,?,?)",
                 (uuid.uuid4().hex, owner, event, revision, _iso(), decision_id, grant_id, reason_code))
    # Long-lived revocation evidence stays in grant rows; bounded recent
    # activity mirrors other Lite operational audit views.
    conn.execute("DELETE FROM lite_lifecycle_audit WHERE event_id NOT IN (SELECT event_id FROM lite_lifecycle_audit ORDER BY event_id DESC LIMIT 2000)")
    from .lite_control_plane_store import _bump_revision
    _bump_revision(conn, "audit", _iso(), changed_ids=["trusted-lifecycle"], reason="audit_state_changed")


def _advance(conn, workspace):
    rev = workspace["boundary_revision"] + 1
    conn.execute("UPDATE lite_lifecycle_workspace SET boundary_revision=?,delegation_revision=delegation_revision+1 WHERE singleton_id=1", (rev,))
    return rev

def _invalidate(conn, workspace):
    rev = _advance(conn, workspace)
    conn.execute("UPDATE lite_lifecycle_workspace SET authority_epoch=authority_epoch+1 WHERE singleton_id=1")
    conn.execute("UPDATE lite_lifecycle_grants SET revoked_at=? WHERE revoked_at IS NULL", (_iso(),))
    conn.execute("DELETE FROM lite_lifecycle_boundary_scopes")
    conn.execute("UPDATE lite_lifecycle_candidate_consent SET revoked_at=? WHERE revoked_at IS NULL", (_iso(),))
    conn.execute("UPDATE lite_lifecycle_policy_execution SET revoked_at=? WHERE revoked_at IS NULL AND proof_sha256 IS NULL", (_iso(),))
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
               "boundary_revision": ws["boundary_revision"], "authority_epoch": ws["authority_epoch"],
               "delegation_revision": ws["delegation_revision"], "owner": owner, "versions": versions,
               "profile_revision": _prefs(conn)["revision"], "registry_revision": registry_revision(),
               "trust": dict(trust) if trust else None, "policy_revision": policy}
    from .lite_lifecycle_candidate_consent import CandidateConsentRequest, binding_fields
    if isinstance(payload, CandidateConsentRequest):
        binding["candidate"] = binding_fields(conn, payload)
    from .lite_lifecycle_policy_execution import PolicyExecutionRequest, binding_fields as execution_binding
    if isinstance(payload, PolicyExecutionRequest):
        binding["policy_execution"] = execution_binding(conn, payload)
    return owner, binding, digest(binding)


def preview(context, action, payload):
    with read_connection() as conn:
        _, binding, fingerprint = _change(conn, context, action, payload)
        scope = None
        if isinstance(payload, GrantRequest):
            if binding["boundary_revision"] != payload.expected_revision or binding["profile_revision"] != payload.expected_profile_revision:
                raise ValueError("boundary_revision_changed")
            if _prefs(conn)["profile"] != "recommended" or not _trust(conn):
                raise ValueError("profile_or_trust_not_ready")
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
    execution = "policy_execution" in binding
    decision = opa.evaluate_authorization(
        auth_context=context, action_id=action, target_type="lifecycle_policy_execution" if execution else "lifecycle_consent",
        target_id="local_workspace", target_revision=fingerprint,
        target={"change_digest": fingerprint, "contract_version": 1, "execution_enabled": execution,
                **({"purpose": "policy-reconciler"} if execution else {})},
        request_context={"confirmation_present": True},
    )
    if not decision.get("allow") or decision.get("policy_revision") != binding["policy_revision"]:
        raise PermissionError("policy_revision_changed")
    if decision.get("continuation_approval_id") or decision.get("continuation_exception_id"):
        raise PermissionError("continuation_not_supported")
    # Independent loaded-policy observation after decision evaluation, outside
    # the SQLite writer lock. The transaction then fences durable activation.
    consistent, _, observed = opa._policy_consistency()
    if not consistent or observed != binding["policy_revision"]:
        raise PermissionError("loaded_policy_revision_unconfirmed")
    decision = {**decision, "observed_policy_revision": observed}
    return owner, binding, fingerprint, decision


def _consume(conn, context, action, payload, authorized):
    owner, binding, fingerprint, decision = authorized
    current_owner, current, current_fingerprint = _change(conn, context, action, payload)
    if current_owner != owner or current != binding or current_fingerprint != fingerprint:
        raise ValueError("authority_revision_changed")
    evidence = conn.execute("""SELECT actor_type,actor_id,action_id,target_revision,allow,policy_revision
        FROM policy_decisions WHERE decision_id=?""", (decision["decision_id"],)).fetchone()
    if (not evidence or evidence["actor_type"] != "human" or evidence["actor_id"] != owner
            or evidence["action_id"] != action or evidence["target_revision"] != fingerprint
            or not evidence["allow"] or evidence["policy_revision"] != binding["policy_revision"]
            or decision.get("observed_policy_revision") != binding["policy_revision"]):
        raise PermissionError("policy_decision_binding_changed")
    session = context["session"]["session_id"]
    from .lite_lifecycle_candidate_consent import CandidateConsentRequest
    from .lite_lifecycle_policy_execution import PolicyExecutionRequest
    trusted_consent = isinstance(payload, (GrantRequest, CandidateConsentRequest, PolicyExecutionRequest))
    if trusted_consent:
        now = _trusted_now(conn)
        current_session = conn.execute("SELECT idle_expires_at,absolute_expires_at FROM auth_sessions WHERE session_id=?", (session,)).fetchone()
        if not current_session or not all(trust_config.future(current_session[key], now) for key in ("idle_expires_at","absolute_expires_at")):
            raise PermissionError("current_session_time_unconfirmed")
    # One-time exact consent, tied to the current session and active credential.
    row = conn.execute("""SELECT a.assurance_id,a.expires_at FROM auth_session_assurance a
        JOIN webauthn_credentials c ON c.credential_id=a.credential_id
        WHERE a.session_id=? AND a.purpose=? AND c.human_id=? AND c.revoked_at IS NULL
        ORDER BY a.satisfied_at DESC LIMIT 1""",
        (session, "lifecycle:" + fingerprint, owner)).fetchone()
    if (not row or not authority._future(row["expires_at"])
            or (trusted_consent and not trust_config.future(row["expires_at"], _trusted_now(conn)))):
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
            _audit(tx, owner, "preference_saved", revision, decision_id=authorized[3]["decision_id"] if authorized else None)
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
            # Only the same purpose is superseded. Other independently
            # approved scopes remain valid under the same authority epoch.
            now = _trusted_now(tx)
            if now is None:
                raise PermissionError("trusted_time_unavailable")
            rev = _advance(tx, ws)
            tx.execute("UPDATE lite_lifecycle_grants SET revoked_at=? WHERE purpose=? AND revoked_at IS NULL", (_iso(), payload.purpose))
            scope = json.dumps(cap.model_dump(mode="json"), separators=(",", ":"))
            tx.execute("""INSERT INTO lite_lifecycle_boundary_scopes VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(purpose) DO UPDATE SET authority_epoch=excluded.authority_epoch,
                scope_revision=excluded.scope_revision,owner_id=excluded.owner_id,scope_json=excluded.scope_json,
                decision_id=excluded.decision_id,approved_at=excluded.approved_at""",
                (payload.purpose, ws["authority_epoch"], rev, owner, scope, decision["decision_id"], now.isoformat()))
            grant = uuid.uuid4().hex
            expires = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
            tx.execute("""INSERT INTO lite_lifecycle_grants(grant_id,workspace_id,boundary_revision,owner_id,
                owner_auth_version,membership_version,configuration_version,profile_revision,registry_revision,
                trust_version,root_version,policy_revision,capability_id,capability_version,purpose,channel,
                scope_json,decision_id,issued_at,expires_at,authority_epoch,trust_configuration_revision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (grant, ws["workspace_id"], rev, owner, *binding["versions"], prefs["revision"], registry_revision(),
                 trust["metadata_version"], trust["root_version"], binding["policy_revision"], cap.id, cap.version,
                 payload.purpose, "stable", scope,
                 decision["decision_id"], now.isoformat(), expires, ws["authority_epoch"], trust["configuration_revision"]))
            tx.execute("INSERT INTO lite_lifecycle_service_delegations VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, grant, payload.purpose, BY_PURPOSE[payload.purpose].version,
                 _workspace(tx)["delegation_revision"], _iso()))
            _audit(tx, owner, "standing_consent_recorded", rev, decision_id=decision["decision_id"], grant_id=grant)
            _prune_grants(tx)
            return {"revision": rev, "grant_id": grant, "execution_eligible": False}


def revoke(context, payload: RevokeRequest):
    # Revocation never needs a new permissive decision from a pending OPA revision.
    with connection() as conn:
        with begin_immediate(conn) as tx:
            owner, _, _ = _owner(tx, context)
            ws = _workspace(tx)
            if ws["boundary_revision"] != payload.expected_revision:
                raise ValueError("boundary_revision_changed")
            if payload.grant_id:
                row = tx.execute("SELECT purpose,revoked_at FROM lite_lifecycle_grants WHERE grant_id=?", (payload.grant_id,)).fetchone()
                if not row or row["revoked_at"]:
                    raise ValueError("grant_not_current")
                rev = _advance(tx, ws)
                tx.execute("UPDATE lite_lifecycle_grants SET revoked_at=? WHERE grant_id=?", (_iso(),payload.grant_id))
                tx.execute("DELETE FROM lite_lifecycle_boundary_scopes WHERE purpose=?", (row["purpose"],))
            else:
                rev = _invalidate(tx, ws)
            _audit(tx, owner, "standing_consent_revoked", rev, grant_id=payload.grant_id)
            _prune_grants(tx)
            return {"revision": rev, "execution_eligible": False, "inflight_cancelled": False}


def _prune_grants(conn):
    # Preserve active grants; keep a bounded revoked history and corresponding
    # independent audit records. Delete referencing delegation rows first.
    old = conn.execute("""SELECT grant_id FROM lite_lifecycle_grants WHERE revoked_at IS NOT NULL
        ORDER BY boundary_revision DESC LIMIT -1 OFFSET 200""").fetchall()
    for row in old:
        conn.execute("DELETE FROM lite_lifecycle_service_delegations WHERE grant_id=?", (row[0],))
        conn.execute("DELETE FROM lite_lifecycle_grants WHERE grant_id=?", (row[0],))

def record_denial(context, reason_code, decision_id=None):
    actor, session = context.get("actor") or {}, context.get("session") or {}
    if actor.get("type") != "human" or not session.get("authenticated"):
        return
    with connection() as conn:
        with begin_immediate(conn) as tx:
            human_id = str(actor.get("identity_id") or "")
            if not authority._human_authority(tx, human_id, str(session.get("session_id") or "")):
                return
            _audit(tx, human_id, "lifecycle_review_denied", _workspace(tx)["boundary_revision"],
                   decision_id=decision_id, reason_code=reason_code)

def evaluate_record(conn, row, *, purpose, capability_id, capability_version, channel, evaluation=None):
    """Future consumers must additionally verify current OPA and runtime gates.
    Never returns execution permission; only a current local record disposition.
    """
    if row["revoked_at"]:
        return "revoked"
    ws, prefs, trust, now, policy = evaluation or (_workspace(conn), _prefs(conn), _trust(conn), _trusted_now(conn), _policy(conn))
    if now is None:
        return "review_required"
    if not trust_config.future(row["expires_at"], now):
        return "expired"
    scope = conn.execute("SELECT * FROM lite_lifecycle_boundary_scopes WHERE purpose=?", (purpose,)).fetchone()
    cap = next((c for c in CAPABILITIES if c.id == capability_id), None)
    versions = automation._owner_versions(conn, row["owner_id"])
    mode = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    if ((mode and mode["enabled"]) or not cap or PURPOSES.get(purpose) != capability_id or row["purpose"] != purpose
        or row["capability_id"] != capability_id or row["capability_version"] != capability_version
        or cap.version != capability_version or channel != row["channel"]
        or row["workspace_id"] != ws["workspace_id"] or row["authority_epoch"] != ws["authority_epoch"]
        or not scope or scope["authority_epoch"] != ws["authority_epoch"] or scope["scope_revision"] != row["boundary_revision"]
        or scope["owner_id"] != row["owner_id"] or scope["scope_json"] != row["scope_json"]
        or row["profile_revision"] != prefs["revision"] or prefs["profile"] != "recommended"
        or row["registry_revision"] != registry_revision()
        or not trust or row["trust_version"] != trust["metadata_version"] or row["root_version"] != trust["root_version"]
        or row["trust_configuration_revision"] != trust["configuration_revision"]
        or row["policy_revision"] != policy
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
    if row["service_version"] != service.version:
        return DelegationReview(disposition="revoked" if row["revoked_at"] else "unknown", reason_code="delegation_revision_changed")
    cap = next((c for c in CAPABILITIES if c.id == row["capability_id"]), None)
    if cap is None:
        return DelegationReview(disposition="unknown", reason_code="capability_unknown")
    state = evaluate_record(conn, row, purpose=purpose, capability_id=cap.id, capability_version=cap.version, channel=channel)
    return scope_review(purpose=purpose, internal_owner=internal_owner, ceiling=cap, proposed=proposed,
        channel=channel, category=category, current_record=state, opa_allowed=opa_allowed, runtime_ready=runtime_ready)


def summary(context):
    with read_connection() as conn:
        actor, session = context.get("actor") or {}, context.get("session") or {}
        if actor.get("type") != "human" or not session.get("authenticated"):
            raise PermissionError("human_required")
        current = authority._human_authority(conn, str(actor.get("identity_id") or ""), str(session.get("session_id") or ""))
        if not current:
            raise PermissionError("human_required")
        is_owner = current["role"] == "Owner"
        enterprise = current["enterprise_enabled"]
        owner, versions, _ = _owner(conn, context) if is_owner else (None, (None, None, None), enterprise)
        ws = _workspace(conn)
        prefs = _prefs(conn)
        receipt = conn.execute("SELECT receipt_id,release_tag,checked_at,receipt_json FROM lite_release_trust_receipts ORDER BY metadata_version DESC LIMIT 1").fetchone()
        trust_observation = conn.execute("SELECT state,reason_code,review_json FROM lite_release_trust_observation WHERE singleton_id=1").fetchone()
        evaluation = (ws, prefs, _trust(conn), _trusted_now(conn), _policy(conn))
        from .lite_lifecycle_candidate_consent import summary as candidate_summary
        from .lite_lifecycle_policy_execution import summary as policy_execution_summary, gate as policy_execution_gate
        from .lite_policy_candidate_differential import supported_differential
        policy_executions = policy_execution_summary(conn) if is_owner else []
        candidate_consents = candidate_summary(conn, ws=ws, prefs=prefs, trust=evaluation[2], now=evaluation[3],
            policy=evaluation[4], owner=owner, versions=versions, enterprise=enterprise) if is_owner else []
        rows = conn.execute("""SELECT g.*,d.delegation_id FROM lite_lifecycle_grants g LEFT JOIN lite_lifecycle_service_delegations d ON d.grant_id=g.grant_id ORDER BY (g.revoked_at IS NULL) DESC,boundary_revision DESC LIMIT 20""").fetchall() if is_owner else []
        grants = [{"grant_id": row["grant_id"], "purpose": row["purpose"], "capability_id": row["capability_id"],
                   "capability_version": row["capability_version"], "expires_at": row["expires_at"],
                   "delegation_id": row["delegation_id"], "channel": row["channel"],
                   "scope": json.loads(row["scope_json"]), "category": BY_PURPOSE[row["purpose"]].category if row["purpose"] in BY_PURPOSE else "unknown",
                   "status": evaluate_record(conn, row, purpose=row["purpose"], capability_id=row["capability_id"],
                                             capability_version=row["capability_version"], channel=row["channel"], evaluation=evaluation)}
                  for row in rows]
        audit = [dict(row) for row in conn.execute("SELECT correlation_id,event_type,revision,occurred_at,decision_id,grant_id,reason_code FROM lite_lifecycle_audit ORDER BY event_id DESC LIMIT 20")]
        identity = conn.execute("SELECT release_tag,verified,source_commit,artifact_sha256 FROM lite_installed_release_identity WHERE owner='installed'").fetchone()
        policy = conn.execute("""SELECT r.content_hash,r.template_version,r.revision_id FROM policy_runtime_state s
            JOIN policy_revisions r ON s.active_revision_id=r.revision_id WHERE s.state_id=1""").fetchone()
        fence = conn.execute("SELECT * FROM lite_system_health_activation_fence WHERE singleton_id=1").fetchone()
        floor = conn.execute("SELECT metadata_version,root_version FROM lite_release_trust_floor WHERE singleton_id=1").fetchone()
        eligible_to_record = is_owner and bool(evaluation[2]) and bool(evaluation[4]) and not enterprise and prefs["profile"] == "recommended"
        trust_setup = trust_config.configuration(conn)
        now = evaluation[3]
        transitions = [dict(row) for row in conn.execute("SELECT event_id,state,reason_code,occurred_at,release_tag FROM lite_release_trust_transitions ORDER BY event_id DESC LIMIT 20")] if is_owner else []
        identity = dict(identity) if identity else {}
        revisions = RevisionIdentities(
            release_source_commit=identity["source_commit"] or None if identity else None,
            frontend_artifact_sha256=identity["artifact_sha256"] or None if identity else None,
            policy_content_sha256=policy["content_hash"] if policy else None,
            policy_contract_version=policy["template_version"] if policy else None,
            # DB active revision is not an independently observed loaded OPA revision.
            capability_registry_revision=registry_revision(), boundary_revision=ws["boundary_revision"],
            workspace_governance_revision=versions[2], authorization_version=versions[0],
            delegation_revision=ws["delegation_revision"], authority_epoch=ws["authority_epoch"],
            trust_configuration_revision=trust_setup["revision"] if trust_setup else None,
            trust_root_sha256=trust_setup["root_sha256"] or None if trust_setup else None,
            trust_root_version=floor["root_version"] if floor else None,
            signed_metadata_version=floor["metadata_version"] if floor else None,
            recovery_assisted_source_revision=fence["assisted_source_revision"] or None if fence else None,
            recovery_assisted_runtime_revision=fence["assisted_runtime_revision"] or None if fence else None,
            recovery_automatic_source_revision=fence["automatic_source_revision"] or None if fence else None,
            recovery_automatic_runtime_revision=fence["automatic_runtime_revision"] or None if fence else None)
        observed_policy = conn.execute("""SELECT observed_opa_revision,updated_at FROM policy_activation_operations
            WHERE observed_opa_revision=? AND state='active' ORDER BY updated_at DESC LIMIT 1""",
            (evaluation[4],)).fetchone()
        history = []
        for item in conn.execute("SELECT receipt_id,receipt_json FROM lite_release_trust_receipts ORDER BY metadata_version DESC LIMIT 20"):
            raw = json.loads(item["receipt_json"])
            history.append({"receipt_id": item["receipt_id"], **{key: raw.get(key) for key in
                ("release_tag","checked_at","expires","authenticity","integrity","provenance","compatibility","impact")}})
    latest = json.loads(trust_observation["review_json"]) if trust_observation else {}
    from .lite_capability_review import public_review
    candidate_review = public_review(latest.get("capability_review")) if is_owner else None
    policy_review = dict(latest.get("policy_review") or {})
    if isinstance(policy_review.get("differential"), dict):
        policy_review["differential"] = {key: val for key, val in policy_review["differential"].items()
                                         if key != "note_suffixes"}
    raw = latest or (json.loads(receipt["receipt_json"]) if receipt else {})
    historical = {key: raw.get(key) for key in ("release_tag","checked_at","expires","root_expires","authenticity","integrity","provenance","compatibility","impact","reason_code")} if raw else None
    state = trust_observation["state"] if trust_observation else "trust_setup_required"
    if state == "historical_evidence":
        if now is None:
            state = "current_trust_unconfirmed"
        elif not trust_config.future(raw.get("expires"), now) or not trust_config.future(raw.get("root_expires"), now):
            state = "metadata_expired"
    return {"schema_version": 1, "registry_revision": registry_revision(),
            "preferences": prefs, "enterprise_managed": enterprise, "owner_authority": is_owner,
            "boundary_revision": ws["boundary_revision"], "authority_epoch": ws["authority_epoch"], "capabilities": inventory() if is_owner else [],
            "revisions": revisions.model_dump() if is_owner else {},
            "historical_loaded_policy": dict(observed_policy) if observed_policy and is_owner else None,
            "assessment": latest.get("assessment"),
            "candidate_consents": candidate_consents,
            "policy_executions": policy_executions,
            "policy_execution_qualification_enabled": bool(is_owner and policy_execution_gate()),
            "policy_execution_review_available": bool(eligible_to_record and policy_execution_gate()
                and latest.get("provenance") == "verified"
                and supported_differential(policy_review.get("differential") or {})
                and (latest.get("capability_review") or {}).get("total") == 0),
            "candidate_review": ({key: latest.get(key) for key in
                ("release_tag", "checked_at", "metadata_sha256", "source_package", "policy_review", "policy_runtime_observation", "migration_review", "coordinated_preflight")} | {"capability_review": candidate_review, "policy_review": policy_review}
                if is_owner and latest.get("provenance") == "verified" else None),
            "services": [{"purpose": item.purpose,"category": item.category,"grantable": item.grantable,
                          "version": item.version,"execution_eligible": False} for item in SERVICES],
            "can_record_consent": eligible_to_record, "grants": grants if is_owner else [], "audit": audit if is_owner else [],
            "release_trust": {"state": state,
                              "reason_code": trust_observation["reason_code"] if trust_observation else "independent_root_required",
                              "installed_tag": identity.get("release_tag") or None,
                              "historical_identity_verified": bool(identity.get("verified")),
                              "receipt": historical, "history": history if is_owner else [], "transitions": transitions,
                              "configuration_state": trust_setup["state"] if trust_setup else "unconfigured",
                              "current_review_eligible": bool(evaluation[2]), "fresh_verification": False},
            "effective_execution": {"software": False, "policy": False, "delegated": False},
            "execution_eligible": False, "sanitized": True}
