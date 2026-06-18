from __future__ import annotations

from typing import Any


def runbook_requires_approval(runbook: Any) -> bool:
    return bool(getattr(runbook, "requires_approval", False)) or any(
        bool(getattr(step, "requires_approval", False)) for step in getattr(runbook, "steps", [])
    )


def resolve_runbook_approval_decision(
    *,
    runbook: Any,
    command: dict[str, Any],
    governance_settings: dict[str, Any],
) -> dict[str, Any]:
    """Return the effective approval decision for a runbook command.

    Personal Mode is the default public GitHub/self-hosted experience: approval-gated
    runbooks are auto-approved and fully logged. Enterprise Mode keeps strict human
    authorization and role checks enabled.
    """
    if not runbook_requires_approval(runbook):
        return {
            "decision": "not_required",
            "approved": True,
            "approval_mode": "not_required",
            "reason": "Runbook does not require approval.",
        }

    if command.get("approved") is True:
        return {
            "decision": "explicit_approval",
            "approved": True,
            "approval_mode": "human",
            "approved_by": command.get("approved_by") or "operator",
            "approval_role": command.get("approval_role") or "operator",
            "reason": command.get("reason") or "Explicit runbook approval was supplied.",
        }

    mode = str(governance_settings.get("governanceMode") or "personal").strip().lower()
    policy = dict((governance_settings.get("approvalPolicy") or {}).get(mode) or {})

    if mode == "enterprise":
        return {
            "decision": "human_required",
            "approved": False,
            "approval_mode": "enterprise",
            "reason": policy.get("reason") or "Enterprise Mode requires explicit human approval.",
        }

    if bool(policy.get("autoApproveRunbooks", True)):
        return {
            "decision": "auto_approved",
            "approved": True,
            "approval_mode": "automatic",
            "approved_by": policy.get("approvedBy") or "local-policy",
            "approval_role": policy.get("approvalRole") or "local-owner",
            "reason": policy.get("reason") or "Auto-approved by Personal Mode policy.",
        }

    return {
        "decision": "human_required",
        "approved": False,
        "approval_mode": "personal_manual",
        "reason": "Personal Mode auto-approval is disabled by policy.",
    }
