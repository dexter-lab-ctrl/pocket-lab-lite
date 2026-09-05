from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

CAPABILITY_SCHEMA_VERSION = 2
CAPABILITY_REGISTRY: tuple[dict[str, str], ...] = (
    {"id": "host_apps", "label": "Can host apps", "category": "apps"},
    {"id": "store_backups", "label": "Can store backups", "category": "recovery"},
    {"id": "run_safety_checks", "label": "Runs safety checks", "category": "security"},
    {"id": "receive_commands", "label": "Receives commands", "category": "control"},
    {"id": "supervisor_recovery", "label": "Supervisor recovery", "category": "recovery"},
    {"id": "remote_access", "label": "Remote access", "category": "connectivity"},
    {"id": "serve_control_plane", "label": "Serves Pocket Lab", "category": "control"},
    {"id": "access_phone_media", "label": "Can access phone media", "category": "media"},
    {"id": "provide_storage", "label": "Provides storage", "category": "storage"},
    {"id": "restore_target", "label": "Restore target", "category": "recovery"},
    {"id": "backup_target", "label": "Backup target", "category": "recovery"},
)
_ALLOWED_STATUSES = {
    "not_advertised", "advertised", "verification_pending", "verified",
    "unavailable", "unsupported", "stale", "blocked", "not_applicable",
}
_ALIASES = {
    "app_host": "host_apps",
    "host-apps": "host_apps",
    "media_storage": "provide_storage",
    "storage": "provide_storage",
    "backup-target": "backup_target",
    "security_scanner": "run_safety_checks",
    "node-command": "receive_commands",
    "agent-restart": "receive_commands",
    "agent-supervisor": "supervisor_recovery",
    "agent-repair": "supervisor_recovery",
    "control_plane": "serve_control_plane",
    "server_host": "serve_control_plane",
}
_SECRETISH = re.compile(
    r"(?:token|password|secret|credential|api[_-]?key|private[_-]?key|authorization|bearer\s+|"
    r"nats://|bootstrap|command_payload|raw_log|raw_evidence|/data/data/|/home/|/mnt/|/root/|~[/\\])",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 120, fallback: str = "") -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if not text or _SECRETISH.search(text):
        return fallback
    return text[:limit]


def _advertised(device: dict[str, Any]) -> set[str]:
    raw = device.get("advertised_capabilities")
    if not isinstance(raw, list):
        raw = device.get("agent_capabilities")
    if not isinstance(raw, list):
        raw = device.get("capabilities")
    result: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        value = str(item or "").strip().lower().replace(" ", "_")
        value = _ALIASES.get(value, value)
        if value:
            result.add(value[:80])
    return result


def _capability(
    capability_id: str,
    label: str,
    *,
    category: str,
    advertised: bool,
    runtime_ready: bool | None,
    evaluated_at: Any,
    source: str,
    ready_reason: str = "runtime_evidence_verified",
    unavailable_reason: str = "runtime_unavailable",
    explicit_status: str = "",
    freshness: str = "current",
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested = str(explicit_status or "").strip().lower()
    freshness_value = str(freshness or "unknown").strip().lower()
    if requested in _ALLOWED_STATUSES:
        status = requested
        reason = unavailable_reason or requested
    elif not advertised:
        status = "not_advertised"
        reason = "capability_not_advertised"
    elif freshness_value == "stale":
        status = "stale"
        reason = "capability_evidence_stale"
    elif runtime_ready is True:
        status = "verified"
        reason = ready_reason or "runtime_evidence_verified"
    elif runtime_ready is False:
        status = "unavailable"
        reason = unavailable_reason or "runtime_unavailable"
    else:
        status = "verification_pending"
        reason = "advertised_not_runtime_verified"
    evaluated = _safe_text(evaluated_at, 64) or None
    safe_evidence: dict[str, Any] = {}
    for key, value in (evidence or {}).items():
        safe_key = re.sub(r"[^a-z0-9_]+", "_", str(key).lower()).strip("_")[:48]
        if safe_key and isinstance(value, (bool, int, float)):
            safe_evidence[safe_key] = value
    return {
        "id": _safe_text(capability_id, 80, "unknown"),
        "label": _safe_text(label, 96, "Capability"),
        "category": _safe_text(category, 48, "device"),
        "status": status,
        "source": _safe_text(source, 80, "runtime_evidence"),
        "advertised": bool(advertised),
        "evaluated_at": evaluated,
        "verified_at": evaluated if status == "verified" else None,
        "freshness": "stale" if status == "stale" else freshness_value or "unknown",
        "reason_code": _safe_text(reason, 96, status),
        "evidence": safe_evidence,
        "schema_version": CAPABILITY_SCHEMA_VERSION,
    }


def verified_capabilities(
    device: dict[str, Any],
    *,
    remote_access: dict[str, Any] | None = None,
    hosted_apps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    advertised = _advertised(device)
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    protected = bool(device.get("is_current") or device.get("isCurrent") or role == "server_host")
    connection = str(device.get("connection") or device.get("status") or "").lower()
    online = connection in {"online", "active", "healthy", "ready"}
    process = str(device.get("agent_process_status") or "").lower()
    supervisor = str(device.get("supervisor_status") or "").lower()
    supervisor_freshness = str(device.get("supervisor_status_freshness") or "").lower()
    storage = device.get("storage") if isinstance(device.get("storage"), dict) else {}
    storage_supported = storage.get("supported")
    storage_ready = bool(storage.get("ready")) and online
    apps = hosted_apps if isinstance(hosted_apps, list) else []
    app_runtime_ready = any(
        isinstance(app, dict) and str(app.get("status") or "").lower() in {"running", "ready", "healthy"}
        for app in apps
    )
    remote = remote_access if protected and isinstance(remote_access, dict) else {}
    remote_ready = bool(remote.get("ready")) if protected else bool(device.get("tailnet_ip") and online)
    remote_at = remote.get("checked_at") if protected else device.get("last_tailnet_ready_at")
    media_ready = bool(device.get("phone_media_ready") is True or device.get("media_roots"))
    evaluated_at = (
        device.get("last_capabilities_at") or device.get("last_system_profile_at")
        or device.get("last_seen_at") or device.get("last_seen") or _now_iso()
    )
    supervisor_at = device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at") or evaluated_at

    evidence: dict[str, dict[str, Any]] = {
        "host_apps": {
            "advertised": "host_apps" in advertised or app_runtime_ready,
            "ready": app_runtime_ready if apps else None,
            "source": "app_runtime" if app_runtime_ready else "agent_advertisement",
            "at": evaluated_at,
            "reason": "hosted_app_runtime_verified" if app_runtime_ready else "",
        },
        "store_backups": {"advertised": "store_backups" in advertised, "ready": storage_ready, "source": "storage_readiness", "at": evaluated_at},
        "run_safety_checks": {
            "advertised": "run_safety_checks" in advertised,
            "ready": device.get("security_execution_ready") if isinstance(device.get("security_execution_ready"), bool) else None,
            "source": "security_execution_evidence",
            "at": device.get("security_execution_checked_at") or evaluated_at,
        },
        "receive_commands": {
            "advertised": "receive_commands" in advertised,
            "ready": device.get("command_delivery_ready") if isinstance(device.get("command_delivery_ready"), bool) else (online and process not in {"missing", "errored", "error", "stopped"} if "receive_commands" in advertised else None),
            "source": "command_delivery_evidence",
            "at": device.get("last_heartbeat_at") or evaluated_at,
        },
        "supervisor_recovery": {
            "advertised": "supervisor_recovery" in advertised,
            "ready": supervisor in {"healthy", "online", "available", "repairing"} and process not in {"missing", "errored", "error"},
            "source": "supervisor_evidence",
            "at": supervisor_at,
            "freshness": "stale" if supervisor_freshness in {"stale", "saved"} else "current" if supervisor_freshness in {"fresh", "current"} else "missing",
        },
        "remote_access": {"advertised": "remote_access" in advertised, "ready": remote_ready, "source": "remote_access_health", "at": remote_at or evaluated_at, "freshness": "current" if remote_at else "missing"},
        "serve_control_plane": {
            "advertised": "serve_control_plane" in advertised or protected,
            "ready": device.get("control_plane_runtime_ready") if isinstance(device.get("control_plane_runtime_ready"), bool) else None,
            "source": "control_plane_runtime_evidence",
            "at": device.get("control_plane_runtime_checked_at") or evaluated_at,
        },
        "access_phone_media": {"advertised": "access_phone_media" in advertised, "ready": media_ready if "access_phone_media" in advertised else None, "source": "media_root_evidence", "at": evaluated_at},
        "provide_storage": {"advertised": "provide_storage" in advertised, "ready": storage_ready, "source": "storage_readiness", "at": evaluated_at},
        "restore_target": {"advertised": "restore_target" in advertised, "ready": storage_ready, "source": "storage_readiness", "at": evaluated_at},
        "backup_target": {"advertised": "backup_target" in advertised, "ready": storage_ready, "source": "storage_readiness", "at": evaluated_at},
    }

    result: list[dict[str, Any]] = []
    known: set[str] = set()
    storage_caps = {"store_backups", "provide_storage", "restore_target", "backup_target"}
    for definition in CAPABILITY_REGISTRY:
        capability_id = definition["id"]
        known.add(capability_id)
        item = evidence[capability_id]
        explicit_status = "unsupported" if storage_supported is False and capability_id in storage_caps else ""
        result.append(_capability(
            capability_id,
            definition["label"],
            category=definition["category"],
            advertised=bool(item.get("advertised")),
            runtime_ready=item.get("ready") if isinstance(item.get("ready"), bool) else None,
            evaluated_at=item.get("at") or evaluated_at,
            source=str(item.get("source") or "agent_advertisement"),
            ready_reason=str(item.get("reason") or "runtime_evidence_verified"),
            unavailable_reason="storage_unsupported" if explicit_status else "runtime_unavailable",
            explicit_status=explicit_status,
            freshness=str(item.get("freshness") or "current"),
            evidence={"online": online} if capability_id in {"receive_commands", "serve_control_plane"} else {},
        ))
    for capability_id in sorted(advertised - known)[:32]:
        result.append(_capability(
            capability_id,
            capability_id.replace("_", " ").title(),
            category="custom",
            advertised=True,
            runtime_ready=None,
            evaluated_at=evaluated_at,
            source="agent_advertisement",
        ))
    return result
