from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

CAPABILITY_SCHEMA_VERSION = 3
CAPABILITY_EVIDENCE_CURRENT_SECONDS = 180

# Backend-owned capability registry. Presentation consumes these records
# dynamically; capability IDs do not need React switch statements to render.
CAPABILITY_REGISTRY: tuple[dict[str, Any], ...] = (
    {"id": "host_apps", "label": "Can host apps", "category": "execution", "verification_strategy": "hosted_app_runtime", "schema_version": 1},
    {"id": "store_backups", "label": "Can store backups", "category": "recovery", "verification_strategy": "storage_readiness", "schema_version": 1},
    {"id": "run_safety_checks", "label": "Runs safety checks", "category": "execution", "verification_strategy": "security_execution", "schema_version": 1},
    {"id": "receive_commands", "label": "Receives commands", "category": "execution", "verification_strategy": "command_delivery", "schema_version": 1},
    {"id": "supervisor_recovery", "label": "Supervisor recovery", "category": "recovery", "verification_strategy": "supervisor_evidence", "schema_version": 1},
    {"id": "remote_access", "label": "Remote access", "category": "connectivity", "verification_strategy": "remote_access_health", "schema_version": 1},
    {"id": "serve_control_plane", "label": "Serves Pocket Lab", "category": "control_plane", "verification_strategy": "control_plane_runtime", "schema_version": 1},
    {"id": "access_phone_media", "label": "Can access phone media", "category": "media", "verification_strategy": "media_access_readiness", "schema_version": 1},
    {"id": "provide_storage", "label": "Provides storage", "category": "storage", "verification_strategy": "storage_readiness", "schema_version": 1},
    {"id": "restore_target", "label": "Restore target", "category": "recovery", "verification_strategy": "restore_target_readiness", "schema_version": 1},
    {"id": "backup_target", "label": "Backup target", "category": "recovery", "verification_strategy": "backup_target_readiness", "schema_version": 1},
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
    r"nats://|bootstrap|command_payload|raw_log|raw_evidence|/data/data/|/storage/emulated/|/home/|/mnt/|/root/|~[/\\])",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 120, fallback: str = "") -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if not text or _SECRETISH.search(text):
        return fallback
    return text[:limit]


def _epoch(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000.0 if number > 10_000_000_000 else number
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _freshness(observed_at: Any, *, now_epoch: float | None = None, current_seconds: int = CAPABILITY_EVIDENCE_CURRENT_SECONDS) -> str:
    observed = _epoch(observed_at)
    if observed is None:
        return "missing"
    now = time.time() if now_epoch is None else float(now_epoch)
    return "current" if max(0.0, now - observed) <= max(1, int(current_seconds)) else "stale"


def _expires_at(evaluated_at: Any, freshness: str, current_seconds: int = CAPABILITY_EVIDENCE_CURRENT_SECONDS) -> str | None:
    epoch = _epoch(evaluated_at)
    if epoch is None or freshness == "missing":
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).__add__(timedelta(seconds=current_seconds)).isoformat().replace("+00:00", "Z")


def _revision(material: dict[str, Any]) -> int:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return max(1, int.from_bytes(hashlib.sha256(encoded.encode("utf-8")).digest()[:8], "big") & ((1 << 63) - 1))


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
    verification_strategy: str,
    advertised: bool,
    advertised_at: Any,
    evidence_present: bool,
    runtime_ready: bool | None,
    evaluated_at: Any,
    source: str,
    ready_reason: str = "runtime_evidence_verified",
    unavailable_reason: str = "runtime_unavailable",
    explicit_status: str = "",
    freshness: str = "",
    evidence: dict[str, Any] | None = None,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    requested = str(explicit_status or "").strip().lower()
    evaluated = _safe_text(evaluated_at, 64) or None
    evidence_freshness = str(freshness or "").strip().lower() or _freshness(evaluated, now_epoch=now_epoch)
    if requested in _ALLOWED_STATUSES:
        status = requested
        reason = unavailable_reason or requested
    elif not advertised and not evidence_present:
        status = "not_advertised"
        reason = "capability_not_advertised"
    elif evidence_freshness == "stale":
        status = "stale"
        reason = "capability_evidence_stale"
    elif runtime_ready is True:
        status = "verified"
        reason = ready_reason or "runtime_evidence_verified"
    elif runtime_ready is False:
        status = "unavailable"
        reason = unavailable_reason or "runtime_unavailable"
    elif advertised:
        status = "verification_pending"
        reason = "advertised_not_runtime_verified"
    else:
        status = "verification_pending"
        reason = "runtime_evidence_incomplete"

    safe_evidence: dict[str, Any] = {}
    for key, value in (evidence or {}).items():
        safe_key = re.sub(r"[^a-z0-9_]+", "_", str(key).lower()).strip("_")[:48]
        if safe_key and isinstance(value, (bool, int, float)):
            safe_evidence[safe_key] = value

    result = {
        "id": _safe_text(capability_id, 80, "unknown"),
        "label": _safe_text(label, 96, "Capability"),
        "category": _safe_text(category, 48, "device"),
        "verification_strategy": _safe_text(verification_strategy, 64, "runtime_evidence"),
        "status": status,
        "reason_code": _safe_text(reason, 96, status),
        "source": _safe_text(source, 80, "runtime_evidence"),
        "advertised": bool(advertised),
        "advertised_at": (_safe_text(advertised_at, 64) or None) if advertised else None,
        "evaluated_at": evaluated,
        "verified_at": evaluated if status == "verified" else None,
        "freshness": "stale" if status == "stale" else evidence_freshness,
        "expires_at": _expires_at(evaluated, evidence_freshness),
        "evidence": safe_evidence,
        "schema_version": CAPABILITY_SCHEMA_VERSION,
    }
    result["revision"] = _revision({
        "id": result["id"],
        "status": result["status"],
        "source": result["source"],
        "freshness": result["freshness"],
        "evaluated_at": result["evaluated_at"],
        "evidence": result["evidence"],
    })
    return result


def verified_capabilities(
    device: dict[str, Any],
    *,
    remote_access: dict[str, Any] | None = None,
    hosted_apps: list[dict[str, Any]] | None = None,
    now_epoch: float | None = None,
) -> list[dict[str, Any]]:
    advertised = _advertised(device)
    advertised_at = device.get("last_capabilities_at") or device.get("last_seen_at") or device.get("last_seen")
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    protected = bool(device.get("is_current") or device.get("isCurrent") or role == "server_host")
    connection = str(device.get("connection") or device.get("status") or "").lower()
    online = connection in {"online", "active", "healthy", "ready"}
    process = str(device.get("agent_process_status") or "").lower()
    supervisor = str(device.get("supervisor_status") or "").lower()
    supervisor_at = device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at")
    storage = device.get("storage") if isinstance(device.get("storage"), dict) else {}
    storage_supported = storage.get("supported")
    storage_ready = bool(storage.get("ready") is True and online)
    apps = hosted_apps if isinstance(hosted_apps, list) else []
    app_runtime_ready = any(
        isinstance(app, dict) and str(app.get("status") or "").lower() in {"running", "ready", "healthy"}
        for app in apps
    )
    remote = remote_access if isinstance(remote_access, dict) else {}
    remote_ready = remote.get("ready") if isinstance(remote.get("ready"), bool) else None
    remote_at = remote.get("updated_at") or remote.get("checked_at") or remote.get("observed_at")
    remote_evidence_present = bool(remote) and any(key in remote for key in ("ready", "status", "running", "nats_reachable"))
    media_ready = device.get("phone_media_ready") if isinstance(device.get("phone_media_ready"), bool) else bool(device.get("media_roots")) if device.get("media_roots") else None
    evaluated_at = (
        device.get("last_capabilities_at") or device.get("last_system_profile_at")
        or device.get("last_seen_at") or device.get("last_seen") or _now_iso()
    )

    control_ready = device.get("control_plane_runtime_ready") if isinstance(device.get("control_plane_runtime_ready"), bool) else None
    control_at = device.get("control_plane_runtime_checked_at") or evaluated_at
    security_ready = device.get("security_execution_ready") if isinstance(device.get("security_execution_ready"), bool) else None
    security_at = device.get("security_execution_checked_at") or evaluated_at
    command_ready = device.get("command_delivery_ready") if isinstance(device.get("command_delivery_ready"), bool) else None
    command_at = device.get("command_delivery_checked_at") or device.get("last_heartbeat_at") or evaluated_at
    supervisor_ready = supervisor in {"healthy", "online", "available", "repairing"} and process not in {"missing", "errored", "error"}
    supervisor_freshness = _freshness(supervisor_at, now_epoch=now_epoch)

    explicit = device.get("capability_overrides") if isinstance(device.get("capability_overrides"), dict) else {}
    evidence: dict[str, dict[str, Any]] = {
        "host_apps": {
            "advertised": "host_apps" in advertised,
            "present": app_runtime_ready or "host_apps" in advertised,
            "ready": True if app_runtime_ready else None,
            "source": "app_runtime" if app_runtime_ready else "agent_advertisement",
            "at": evaluated_at,
            "reason": "hosted_app_runtime_verified" if app_runtime_ready else "",
        },
        "store_backups": {"advertised": "store_backups" in advertised, "present": "store_backups" in advertised or bool(storage), "ready": storage_ready if storage else None, "source": "storage_readiness", "at": evaluated_at},
        "run_safety_checks": {"advertised": "run_safety_checks" in advertised, "present": "run_safety_checks" in advertised or security_ready is not None, "ready": security_ready, "source": "security_execution_evidence", "at": security_at},
        "receive_commands": {"advertised": "receive_commands" in advertised, "present": "receive_commands" in advertised or command_ready is not None, "ready": command_ready, "source": "command_delivery_evidence", "at": command_at},
        "supervisor_recovery": {"advertised": "supervisor_recovery" in advertised, "present": "supervisor_recovery" in advertised or bool(supervisor_at), "ready": supervisor_ready if supervisor_at else None, "source": "supervisor_evidence", "at": supervisor_at or evaluated_at, "freshness": supervisor_freshness},
        "remote_access": {"advertised": "remote_access" in advertised, "present": remote_evidence_present, "ready": remote_ready, "source": "remote_access_health", "at": remote_at or evaluated_at, "freshness": _freshness(remote_at, now_epoch=now_epoch) if remote_at else "missing"},
        "serve_control_plane": {"advertised": "serve_control_plane" in advertised, "present": protected or control_ready is not None, "ready": control_ready, "source": "control_plane_runtime_evidence", "at": control_at},
        "access_phone_media": {"advertised": "access_phone_media" in advertised, "present": "access_phone_media" in advertised or media_ready is not None, "ready": media_ready, "source": "media_access_evidence", "at": evaluated_at},
        "provide_storage": {"advertised": "provide_storage" in advertised, "present": "provide_storage" in advertised or bool(storage), "ready": storage_ready if storage else None, "source": "storage_readiness", "at": evaluated_at},
        "restore_target": {"advertised": "restore_target" in advertised, "present": "restore_target" in advertised or bool(storage.get("restore_target_ready") is not None), "ready": storage.get("restore_target_ready") if isinstance(storage.get("restore_target_ready"), bool) else None, "source": "restore_target_readiness", "at": evaluated_at},
        "backup_target": {"advertised": "backup_target" in advertised, "present": "backup_target" in advertised or bool(storage.get("backup_target_ready") is not None), "ready": storage.get("backup_target_ready") if isinstance(storage.get("backup_target_ready"), bool) else None, "source": "backup_target_readiness", "at": evaluated_at},
    }

    result: list[dict[str, Any]] = []
    known: set[str] = set()
    storage_caps = {"store_backups", "provide_storage", "restore_target", "backup_target"}
    for definition in CAPABILITY_REGISTRY:
        capability_id = definition["id"]
        known.add(capability_id)
        item = evidence[capability_id]
        override = str(explicit.get(capability_id) or "").lower()
        if override not in _ALLOWED_STATUSES:
            override = ""
        if not override and storage_supported is False and capability_id in storage_caps:
            override = "unsupported"
        if not override and capability_id == "access_phone_media" and role in {"storage", "storage_node", "backup_target"} and capability_id not in advertised:
            override = "not_applicable"
        result.append(_capability(
            capability_id,
            definition["label"],
            category=definition["category"],
            verification_strategy=definition["verification_strategy"],
            advertised=bool(item.get("advertised")),
            advertised_at=advertised_at,
            evidence_present=bool(item.get("present")),
            runtime_ready=item.get("ready") if isinstance(item.get("ready"), bool) else None,
            evaluated_at=item.get("at") or evaluated_at,
            source=str(item.get("source") or "agent_advertisement"),
            ready_reason=str(item.get("reason") or "runtime_evidence_verified"),
            unavailable_reason="storage_unsupported" if override == "unsupported" else "runtime_unavailable",
            explicit_status=override,
            freshness=str(item.get("freshness") or ""),
            evidence={"online": online} if capability_id in {"receive_commands", "serve_control_plane"} else {},
            now_epoch=now_epoch,
        ))

    for capability_id in sorted(advertised - known)[:32]:
        result.append(_capability(
            capability_id,
            capability_id.replace("_", " ").title(),
            category="custom",
            verification_strategy="unknown_future_capability",
            advertised=True,
            advertised_at=advertised_at,
            evidence_present=False,
            runtime_ready=None,
            evaluated_at=evaluated_at,
            source="agent_advertisement",
            freshness=_freshness(advertised_at, now_epoch=now_epoch),
            now_epoch=now_epoch,
        ))
    return result
