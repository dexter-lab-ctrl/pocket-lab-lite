from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .. import deps

VALID_GOVERNANCE_MODES = {"personal", "enterprise"}

DEFAULT_GOVERNANCE_SETTINGS: dict[str, Any] = {
    "governanceMode": "personal",
    "enterpriseModeEnabled": False,
    "description": "Personal mode auto-approves approval-gated runbooks and logs evidence. Enterprise mode enforces human approval.",
    "approvalPolicy": {
        "personal": {
            "autoApproveRunbooks": True,
            "autoApproveDryRuns": True,
            "approvedBy": "local-policy",
            "approvalRole": "local-owner",
            "reason": "Auto-approved by Pocket Lab Personal Mode policy for the default self-hosted experience.",
        },
        "enterprise": {
            "autoApproveRunbooks": False,
            "enforceHumanApproval": True,
            "enforceRoles": True,
            "reason": "Enterprise Mode requires explicit human approval for governed runbooks.",
        },
    },
}


def _settings_path() -> Path:
    return Path(deps.settings().state_dir) / "governance_settings.json"


def _merge_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_GOVERNANCE_SETTINGS)
    merged.update({k: v for k, v in payload.items() if k != "approvalPolicy"})
    policy = dict(DEFAULT_GOVERNANCE_SETTINGS["approvalPolicy"])
    incoming_policy = payload.get("approvalPolicy")
    if isinstance(incoming_policy, dict):
        for key, value in incoming_policy.items():
            if isinstance(value, dict) and isinstance(policy.get(key), dict):
                policy[key] = {**policy[key], **value}
            else:
                policy[key] = value
    merged["approvalPolicy"] = policy
    mode = str(merged.get("governanceMode") or "personal").strip().lower()
    if mode not in VALID_GOVERNANCE_MODES:
        mode = "personal"
    merged["governanceMode"] = mode
    merged["enterpriseModeEnabled"] = mode == "enterprise"
    return merged


def get_governance_settings() -> dict[str, Any]:
    mode_override = os.environ.get("POCKETLAB_GOVERNANCE_MODE", "").strip().lower()
    path = _settings_path()
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            import json

            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}
    merged = _merge_defaults(payload)
    if mode_override in VALID_GOVERNANCE_MODES:
        merged["governanceMode"] = mode_override
        merged["enterpriseModeEnabled"] = mode_override == "enterprise"
        merged["source"] = "environment"
    else:
        merged["source"] = "state"
    return merged


def update_governance_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = get_governance_settings()
    requested = dict(current)
    requested.update(payload or {})
    mode = str(requested.get("governanceMode") or "personal").strip().lower()
    if mode not in VALID_GOVERNANCE_MODES:
        raise ValueError(f"Unsupported governance mode: {mode}")
    requested["governanceMode"] = mode
    requested["enterpriseModeEnabled"] = mode == "enterprise"
    requested["source"] = "state"

    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(requested, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return requested
