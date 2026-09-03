"""Shared server-owned Identity + Rules capability and policy presentation.

This module is deliberately presentation-oriented: OPA remains the enforcement
engine and policy lifecycle services remain the mutation authority.  Both the
Identity and Rules tabs consume this projection so role descriptions and
approval expectations cannot drift independently in the browser.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..db.connection import connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_identity, lite_policy_lifecycle


POLICY_TEMPLATE_ID = "enterprise_governance"
POLICY_DEFAULTS = {
    "admin_device_remove_approval": 1,
    "operator_device_remove_approval": 1,
}

ROLE_CATALOG: dict[str, dict[str, str]] = {
    "Owner": {
        "label": "Owner",
        "summary": "Full Pocket Lab authority. Owners do not need another person's approval, but sensitive actions can still require passkey confirmation and always keep hard safety guards.",
    },
    "Admin": {
        "label": "Admin",
        "summary": "Broad delegated administration. Admins can manage normal operations and lower-privilege people; high-risk actions can require independent review.",
    },
    "Operator": {
        "label": "Operator",
        "summary": "Day-to-day operational access. Operators can run normal work and request protected changes when review is required.",
    },
    "Auditor": {
        "label": "Auditor",
        "summary": "Read-only governance and evidence access for reviewing decisions, policy history and security activity.",
    },
    "Viewer": {
        "label": "Viewer",
        "summary": "Read-only workspace access without administrative or policy-changing authority.",
    },
}

ACTION_CATALOG = (
    ("people.manage", "Manage people", "Create, suspend, reactivate, remove and assign access to people."),
    ("enterprise.mode.change", "Change workspace mode", "Switch between Personal and Enterprise Mode."),
    ("device.remove", "Remove devices", "Retire a confirmed non-server device from Pocket Lab."),
    ("catalog.install", "Install apps", "Install an approved app through the normal server-owned execution path."),
    ("rules.draft", "Draft Rules", "Create a typed immutable Rules candidate for review."),
    ("rules.activate", "Activate Rules", "Activate a validated Rules revision through the supervisor-owned lifecycle."),
    ("rules.rollback", "Restore known-good Rules", "Request restoration of the proved known-good Rules revision."),
    ("rules.simulate", "Test Rules", "Run a non-executing Rules simulation."),
    ("approvals.review", "Review requests", "Approve or reject another person's protected request."),
    ("exceptions.manage", "Temporary access", "Create and revoke narrow, expiring policy exceptions."),
    ("evidence.read", "Review activity", "Read sanitized Identity and Rules evidence."),
)


class GovernanceError(RuntimeError):
    def __init__(self, reason_code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_policy_templates() -> None:
    """Register the typed governance template in the existing lifecycle.

    Parameters intentionally remain bounded integers because the lifecycle's
    canonical validator already proves integer min/max constraints.  The
    browser never supplies Rego source.
    """
    lite_policy_lifecycle.TEMPLATES.setdefault(
        POLICY_TEMPLATE_ID,
        {
            "version": "1",
            "parameters": {
                "admin_device_remove_approval": {"type": "integer", "minimum": 0, "maximum": 1, "default": 1},
                "operator_device_remove_approval": {"type": "integer", "minimum": 0, "maximum": 1, "default": 1},
            },
        },
    )


def effective_policy_parameters() -> dict[str, int]:
    apply_migrations()
    values = dict(POLICY_DEFAULTS)
    with connection() as conn:
        state = conn.execute("SELECT active_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
        revision_id = str(state["active_revision_id"] or "") if state else ""
        row = conn.execute(
            "SELECT template_id,canonical_parameters_json FROM policy_revisions WHERE revision_id=?",
            (revision_id,),
        ).fetchone() if revision_id else None
    if row and str(row["template_id"] or "") == POLICY_TEMPLATE_ID:
        try:
            parsed = json.loads(str(row["canonical_parameters_json"] or "{}"))
        except (TypeError, ValueError):
            parsed = {}
        for key in POLICY_DEFAULTS:
            raw = parsed.get(key, POLICY_DEFAULTS[key])
            values[key] = 1 if int(raw or 0) else 0
    return values


def _topology() -> dict[str, int]:
    apply_migrations()
    with connection() as conn:
        rows = conn.execute(
            """SELECT m.role,COUNT(*) AS count
               FROM enterprise_memberships m
               JOIN human_identities h ON h.human_id=m.human_id
               WHERE m.status='active' AND h.status='active'
               GROUP BY m.role"""
        ).fetchall()
        active_people = conn.execute("SELECT COUNT(*) AS count FROM human_identities WHERE status='active'").fetchone()
        invited = conn.execute("SELECT COUNT(*) AS count FROM human_identities WHERE status='invited'").fetchone()
    counts = {role: 0 for role in ROLE_CATALOG}
    for row in rows:
        if row["role"] in counts:
            counts[str(row["role"])] = int(row["count"] or 0)
    return {
        "active_people": int(active_people["count"] or 0) if active_people else 0,
        "invited_people": int(invited["count"] or 0) if invited else 0,
        "active_owners": counts["Owner"],
        "active_admins": counts["Admin"],
        "active_operators": counts["Operator"],
        "active_auditors": counts["Auditor"],
        "active_viewers": counts["Viewer"],
        "independent_approvers": counts["Owner"] + counts["Admin"],
    }


def _mode_for(action: str, role: str, params: dict[str, int]) -> str:
    if role == "Owner":
        if action in {"rules.activate", "rules.rollback", "enterprise.mode.change"}:
            return "step_up"
        return "allow"
    if role == "Admin":
        if action == "device.remove":
            return "approval" if params["admin_device_remove_approval"] else "allow"
        if action in {"people.manage", "catalog.install", "rules.draft", "rules.simulate", "approvals.review", "exceptions.manage", "evidence.read"}:
            return "allow"
        return "deny"
    if role == "Operator":
        if action == "device.remove":
            return "approval" if params["operator_device_remove_approval"] else "allow"
        if action in {"catalog.install", "rules.simulate", "evidence.read"}:
            return "allow"
        return "deny"
    if role == "Auditor":
        return "allow" if action in {"evidence.read", "rules.simulate"} else "deny"
    if role == "Viewer":
        return "allow" if action == "evidence.read" else "deny"
    return "deny"


def _capabilities(role: str, params: dict[str, int]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for action, _label, _summary in ACTION_CATALOG:
        mode = _mode_for(action, role, params)
        result[action] = mode != "deny"
        result[f"{action}.mode"] = mode
        result[f"{action}.requires_approval"] = mode == "approval"
        result[f"{action}.requires_step_up"] = mode == "step_up"
    return result


def access_projection(auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations()
    context = lite_enterprise_identity.enrich_auth_context(auth_context)
    actor = context.get("actor") or {}
    authorization = context.get("authorization") or {}
    actor_id = str(actor.get("identity_id") or "")
    enabled = bool(authorization.get("enterprise_enabled"))
    role = str(authorization.get("role") or "")
    if actor.get("type") != "human" or not actor_id:
        raise GovernanceError("human_session_required", "Sign in to review Identity and Rules authority.", 401)
    if not enabled:
        with connection() as conn:
            owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
        role = "Owner" if owner and str(owner["human_id"]) == actor_id else ""
    if not role:
        raise GovernanceError("enterprise_membership_required", "Your active access role could not be proved.")
    params = effective_policy_parameters()
    matrix = []
    for action, label, summary in ACTION_CATALOG:
        modes = {candidate: _mode_for(action, candidate, params) for candidate in ROLE_CATALOG}
        matrix.append({"action_id": action, "label": label, "summary": summary, "roles": modes})
    topology = _topology()
    return {
        "mode": "enterprise" if enabled else "personal",
        "enterprise_enabled": enabled,
        "current_role": role,
        "owner_authority": role == "Owner",
        "role": {"id": role, **ROLE_CATALOG.get(role, {"label": role, "summary": "Server-resolved Pocket Lab role."})},
        "roles": [{"id": key, **value} for key, value in ROLE_CATALOG.items()],
        "capabilities": _capabilities(role, params),
        "policy_parameters": params,
        "action_matrix": matrix,
        "topology": topology,
        "updated_at": _now(),
        "summary": "Owner has complete supported Pocket Lab authority without peer approval." if role == "Owner" else "Your server-resolved role and current Safety Rules determine what you can do.",
    }


def require_root_owner(auth_context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    context = lite_enterprise_identity.enrich_auth_context(auth_context)
    actor = context.get("actor") or {}
    authorization = context.get("authorization") or {}
    actor_id = str(actor.get("identity_id") or "")
    if actor.get("type") != "human" or not actor_id:
        raise GovernanceError("human_session_required", "A signed-in human session is required.", 401)
    if authorization.get("enterprise_enabled"):
        if not authorization.get("membership_active") or authorization.get("role") != "Owner":
            raise GovernanceError("enterprise_owner_required", "An active Enterprise Owner is required for this root-level change.")
    else:
        with connection() as conn:
            owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
        if not owner or str(owner["human_id"]) != actor_id:
            raise GovernanceError("local_owner_required", "The local Pocket Lab Owner is required for this change.")
    return context, actor_id


def require_recent_assurance(auth_context: dict[str, Any], purpose: str) -> tuple[dict[str, Any], str]:
    context, actor_id = require_root_owner(auth_context)
    now = _now()
    assurance = (context.get("session") or {}).get("assurance") or []
    if not any(
        isinstance(item, dict)
        and str(item.get("purpose") or "") == purpose
        and str(item.get("expires_at") or "") > now
        for item in assurance
    ):
        raise GovernanceError(
            "owner_step_up_required",
            "Confirm this root-level change with your passkey first.",
            428,
        )
    return context, actor_id
