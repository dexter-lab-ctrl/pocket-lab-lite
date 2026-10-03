"""Canonical app-resource governance contract for the Universal App Platform.

This module composes the existing registry, Identity roles, OPA policy input,
device-role capability truth, Recovery contracts and credential metadata.  It
does not execute adapters or replace any existing authorization engine.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import HTTPException

from . import lite_app_registry, lite_enterprise_identity


REGISTRY_ACTION_TO_SEMANTIC: dict[str, str] = {
    "open": "app.open",
    "open_full_screen": "app.open",
    "install_to_phone": "app.open",
    "check_app": "app.security_check",
    "backup_app": "app.backup.create",
    "backup_to_storage": "app.backup.to_storage",
    "preview_restore": "app.restore.preview",
    "install_app": "app.install",
    "update_app": "app.update.check",
    "repair_app": "app.repair",
    "remove_app": "app.remove",
}
LEGACY_ACTION_ALIASES: dict[str, str] = {
    "catalog.install": "app.install",
    "backup.create": "app.backup.create",
    "restore.preview": "app.restore.preview",
}
SEMANTIC_CAPABILITIES: dict[str, str] = {
    "app.open": "open",
    "app.install": "install",
    "app.security_check": "security_check",
    "app.repair": "repair",
    "app.backup.create": "backup",
    "app.backup.to_storage": "backup_to_storage",
    "app.restore.preview": "restore_preview",
    "app.update.check": "update_readiness",
    "app.remove": "remove",
    "app.credentials.read_status": "credentials",
    "app.credentials.manage": "credentials",
}
READ_ONLY_ACTIONS = frozenset({"app.open", "app.credentials.read_status"})
GOVERNED_ACTIONS = frozenset(set(SEMANTIC_CAPABILITIES) - READ_ONLY_ACTIONS)
APPROVAL_ACTIONS = frozenset({"app.remove"})
TEMPORARY_EXCEPTION_ACTIONS = frozenset({"app.install"})
ACTION_LABELS = {
    "app.open": "Open app",
    "app.install": "Install app",
    "app.security_check": "Run App Check",
    "app.repair": "Repair app",
    "app.backup.create": "Back up app",
    "app.backup.to_storage": "Back up to storage",
    "app.restore.preview": "Preview restore",
    "app.update.check": "Check update readiness",
    "app.remove": "Remove app",
    "app.credentials.read_status": "Review credential status",
    "app.credentials.manage": "Manage app credentials",
}
CONSEQUENCE = {
    "app.open": "read",
    "app.credentials.read_status": "read",
    "app.security_check": "bounded_scan",
    "app.backup.create": "safe_mutation",
    "app.backup.to_storage": "safe_mutation",
    "app.restore.preview": "preview_only",
    "app.update.check": "readiness_only",
    "app.install": "mutation",
    "app.repair": "mutation",
    "app.credentials.manage": "sensitive_metadata",
    "app.remove": "destructive",
}


def semantic_action(action_id: Any) -> str:
    raw = str(action_id or "").strip().lower().replace("-", "_")
    dotted = str(action_id or "").strip().lower()
    if dotted in SEMANTIC_CAPABILITIES:
        return dotted
    if dotted in LEGACY_ACTION_ALIASES:
        return LEGACY_ACTION_ALIASES[dotted]
    if raw in REGISTRY_ACTION_TO_SEMANTIC:
        return REGISTRY_ACTION_TO_SEMANTIC[raw]
    raise HTTPException(
        status_code=404,
        detail={"status": "unsupported_action", "summary": "This app action is not registered for governance."},
    )


def registry_action_for(action_id: Any) -> str | None:
    semantic = semantic_action(action_id)
    for registry_action, candidate in REGISTRY_ACTION_TO_SEMANTIC.items():
        if candidate == semantic:
            return registry_action
    return None


def _safe_operation_id(value: Any) -> str:
    text = str(value or "").strip()
    if text and len(text) <= 120 and all(ch.isalnum() or ch in "._:-" for ch in text):
        return text
    return "app-op-" + uuid.uuid4().hex


def _contract_revision(
    *,
    app_id: str,
    semantic: str,
    target_device_id: str,
    placement: dict[str, Any],
    capability: str,
) -> str:
    definition = lite_app_registry.app_definition(app_id)
    material = {
        "schema_version": lite_app_registry.APP_PLATFORM_SCHEMA_VERSION,
        "app_id": app_id,
        "semantic_action": semantic,
        "required_capability": capability,
        "registry_capabilities": sorted(definition.capabilities),
        "platforms": sorted(definition.platforms),
        "placement": placement,
        "target_device_id": target_device_id,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]


def _fleet_payload() -> dict[str, Any]:
    try:
        from . import lite_status

        payload = lite_status.lite_fleet()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _normalized_device_id(device: dict[str, Any]) -> str:
    return str(device.get("id") or device.get("node_id") or device.get("device_id") or "").strip().lower()


def _placement_truth(
    app_id: str,
    semantic: str,
    *,
    target_device_id: Any = None,
    fleet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from . import lite_device_roles

    definition = lite_app_registry.app_definition(app_id)
    placement = dict(definition.placement)
    required = list(placement.get("required_device_capabilities") or [])
    if semantic == "app.backup.to_storage":
        required = list(placement.get("backup_target_capabilities") or ["backup_target"])
    requested = str(target_device_id or "").strip().lower()
    fleet = fleet_payload if isinstance(fleet_payload, dict) else _fleet_payload()
    devices = fleet.get("devices") if isinstance(fleet.get("devices"), list) else []

    candidates: list[dict[str, Any]] = []
    for raw in devices:
        if not isinstance(raw, dict):
            continue
        device = lite_device_roles.enrich_device_projection(raw)
        device_id = _normalized_device_id(device)
        if requested and device_id != requested:
            continue
        server_host = bool(
            device.get("protected_server_host")
            or device.get("is_current")
            or str(device.get("role") or "") == "server_host"
        )
        if placement.get("server_host_only") and not server_host:
            continue
        if semantic == "app.backup.to_storage" and server_host:
            continue
        effective = {
            str(item.get("id") or "")
            for item in (device.get("capability_states") or [])
            if isinstance(item, dict) and item.get("effective") is True and item.get("verification") == "verified"
        }
        candidates.append({
            "device_id": device_id,
            "server_host": server_host,
            "effective_capabilities": sorted(effective),
            "connection": str(device.get("connection") or device.get("status") or "unknown"),
            "role_status": str(device.get("device_role_status") or "unknown"),
        })

    selected = candidates[0] if candidates else None
    ready = bool(selected and all(capability in set(selected["effective_capabilities"]) for capability in required))
    if requested and not selected:
        reason = "target_device_unavailable"
    elif not selected:
        reason = "required_device_unavailable"
    elif not ready:
        reason = "required_device_capability_unverified"
    else:
        reason = ""
    return {
        "kind": str(placement.get("kind") or "server_host"),
        "server_host_only": bool(placement.get("server_host_only")),
        "required_capabilities": required,
        "target_device_id": selected.get("device_id") if selected else requested or "",
        "ready": ready,
        "reason_code": reason,
        "verified_capabilities": selected.get("effective_capabilities") if selected else [],
        "device_role_status": selected.get("role_status") if selected else "unknown",
    }


def resource_contract(
    app_id: Any,
    action_id: Any,
    *,
    target_device_id: Any = None,
    operation_id: Any = None,
    fleet_payload: dict[str, Any] | None = None,
    require_placement: bool = False,
) -> dict[str, Any]:
    definition = lite_app_registry.app_definition(app_id)
    semantic = semantic_action(action_id)
    capability = SEMANTIC_CAPABILITIES[semantic]
    supported = capability in definition.capabilities
    if not supported:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "capability_not_supported",
                "summary": "This registered app does not declare the capability required for that operation.",
                "app_id": definition.id,
                "semantic_action": semantic,
            },
        )
    platform_supported = lite_app_registry.platform_supported(definition.id)
    placement = _placement_truth(
        definition.id,
        semantic,
        target_device_id=target_device_id,
        fleet_payload=fleet_payload,
    )
    if require_placement and (not platform_supported or not placement["ready"]):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "app_placement_not_ready",
                "summary": "The selected app operation does not have a verified authorized device placement.",
                "app_id": definition.id,
                "semantic_action": semantic,
                "reason_code": "unsupported_platform" if not platform_supported else placement["reason_code"],
            },
        )
    revision = _contract_revision(
        app_id=definition.id,
        semantic=semantic,
        target_device_id=str(placement.get("target_device_id") or ""),
        placement=dict(definition.placement),
        capability=capability,
    )
    risk = "low"
    registry_action = registry_action_for(semantic)
    if registry_action:
        action = lite_app_registry.action_definition(definition.id, registry_action) or {}
        risk = str(action.get("risk") or risk)
    return {
        "resource_type": "app",
        "app_id": definition.id,
        "app_label": definition.name,
        "semantic_action": semantic,
        "registry_action_id": registry_action,
        "required_capability": capability,
        "capability_supported": supported,
        "platform_supported": platform_supported,
        "registry_schema_version": lite_app_registry.APP_PLATFORM_SCHEMA_VERSION,
        "contract_revision": revision,
        "operation_id": _safe_operation_id(operation_id),
        "target_device_id": str(placement.get("target_device_id") or ""),
        "placement": placement,
        "risk": risk,
        "consequence": CONSEQUENCE.get(semantic, "mutation"),
        "governed": semantic in GOVERNED_ACTIONS,
        "read_only": semantic in READ_ONLY_ACTIONS,
        "request_fingerprint": revision,
    }


def policy_target(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_type": "app",
        "app_id": contract["app_id"],
        "app_label": contract["app_label"],
        "semantic_action": contract["semantic_action"],
        "required_capability": contract["required_capability"],
        "capability_supported": bool(contract["capability_supported"]),
        "platform_supported": bool(contract["platform_supported"]),
        "placement_ready": bool((contract.get("placement") or {}).get("ready")),
        "placement_reason_code": str((contract.get("placement") or {}).get("reason_code") or ""),
        "target_device_id": contract.get("target_device_id") or "",
        "registry_schema_version": contract["registry_schema_version"],
        "contract_revision": contract["contract_revision"],
        "request_fingerprint": contract["request_fingerprint"],
        "risk": contract["risk"],
        "consequence": contract["consequence"],
    }


def _role_mode(role: str, action: str, *, enterprise_enabled: bool) -> str:
    if not enterprise_enabled:
        return "allow" if role == "Owner" else "deny"
    if role == "Owner":
        return "allow"
    if action in READ_ONLY_ACTIONS:
        return "allow"
    if role == "Admin":
        return "approval" if action == "app.remove" else "allow"
    if role == "Operator":
        if action == "app.install":
            return "temporary_access"
        if action == "app.remove":
            return "approval"
        if action in {
            "app.security_check",
            "app.repair",
            "app.backup.create",
            "app.backup.to_storage",
            "app.restore.preview",
            "app.update.check",
        }:
            return "allow"
        return "deny"
    return "deny"


def authority_projection(auth_context: dict[str, Any], *, app_id: Any | None = None) -> dict[str, Any]:
    context = lite_enterprise_identity.enrich_auth_context(auth_context)
    authorization = context.get("authorization") or {}
    role = str(authorization.get("role") or "")
    enterprise_enabled = bool(authorization.get("enterprise_enabled"))
    if not role:
        raise HTTPException(status_code=403, detail={"status": "authority_unproved", "summary": "App authority could not be proved."})
    definitions = [lite_app_registry.app_definition(app_id)] if app_id is not None else [lite_app_registry.app_definition(item) for item in lite_app_registry.app_ids()]
    apps: list[dict[str, Any]] = []
    for definition in definitions:
        actions = []
        semantic_ids = sorted({
            REGISTRY_ACTION_TO_SEMANTIC[action]
            for action in definition.actions
            if action in REGISTRY_ACTION_TO_SEMANTIC
        } | {"app.credentials.read_status", "app.credentials.manage"})
        for semantic in semantic_ids:
            capability = SEMANTIC_CAPABILITIES[semantic]
            if capability not in definition.capabilities:
                continue
            mode = _role_mode(role, semantic, enterprise_enabled=enterprise_enabled)
            actions.append({
                "action_id": semantic,
                "label": ACTION_LABELS[semantic],
                "mode": mode,
                "allowed": mode in {"allow", "temporary_access"},
                "requires_approval": mode == "approval",
                "temporary_access_supported": semantic in TEMPORARY_EXCEPTION_ACTIONS,
                "requires_step_up": False,
                "required_capability": capability,
            })
        apps.append({
            "resource_type": "app",
            "app_id": definition.id,
            "app_label": definition.name,
            "role": role,
            "mode": "enterprise" if enterprise_enabled else "personal",
            "actions": actions,
            "summary": "You can manage this app." if role in {"Owner", "Admin"} else ("Read-only access." if role in {"Auditor", "Viewer"} else "Access follows current Safety Rules."),
        })
    return {
        "mode": "enterprise" if enterprise_enabled else "personal",
        "current_role": role,
        "resources": apps,
        "updated_at": __import__("api_fastapi.deps", fromlist=["now_utc_iso"]).now_utc_iso(),
    }


def recovery_projection(app_id: Any) -> dict[str, Any]:
    from . import lite_app_backup, lite_app_credentials

    definition = lite_app_registry.app_definition(app_id)
    backup = lite_app_backup.app_backup_status(definition.id)
    latest = backup.get("latest_backup") if isinstance(backup.get("latest_backup"), dict) else None
    profile = backup.get("profile") if isinstance(backup.get("profile"), dict) else {}
    credentials = lite_app_credentials.credential_status(definition.id)
    blockers: list[str] = []
    if backup.get("backup_supported") and not latest:
        blockers.append("No app backup has been saved yet.")
    if backup.get("backup_supported") and latest and latest.get("verification_status") != "verified":
        blockers.append("The latest app backup is not verified.")
    target = backup.get("storage_target") if isinstance(backup.get("storage_target"), dict) else {}
    if lite_app_registry.supports(definition.id, "backup_to_storage") and not target.get("ready"):
        blockers.append("A verified storage backup target is not ready.")
    return {
        "app_id": definition.id,
        "app_label": definition.name,
        "backup_supported": bool(backup.get("backup_supported")),
        "last_backup": latest,
        "last_verified_backup": latest if latest and latest.get("verification_status") == "verified" else None,
        "backup_target_readiness": target,
        "restore_preview_supported": bool(backup.get("restore_preview_supported")),
        "restore_apply_supported": bool(backup.get("restore_apply_supported")),
        "protected_user_data_excluded": not bool(profile.get("media_included", False)),
        "credential_rebinding_required": any(item.get("management") == "external_or_manual" for item in credentials.get("credentials") or []),
        "recovery_ready": not blockers,
        "recovery_blockers": blockers,
        "evidence_refs": [
            ref for ref in (
                latest.get("evidence_ref") if latest else None,
                (backup.get("latest_restore_preview") or {}).get("evidence_ref") if isinstance(backup.get("latest_restore_preview"), dict) else None,
            ) if ref
        ][:4],
        "summary": "App recovery is ready." if not blockers else blockers[0],
    }


def sanitized_evidence_link(contract: dict[str, Any], decision: dict[str, Any] | None) -> dict[str, Any]:
    decision = decision if isinstance(decision, dict) else {}
    return {
        "app_id": contract["app_id"],
        "semantic_action": contract["semantic_action"],
        "operation_id": contract["operation_id"],
        "authorization_decision_id": decision.get("decision_id"),
        "policy_revision": decision.get("policy_revision"),
        "contract_revision": contract["contract_revision"],
        "target_device_id": contract.get("target_device_id") or None,
        "sanitized": True,
    }
