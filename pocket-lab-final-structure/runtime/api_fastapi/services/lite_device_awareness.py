from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from .. import deps


RECENTLY_OFFLINE_SECONDS = max(
    60, min(int(os.environ.get("POCKETLAB_FLEET_RECENTLY_OFFLINE_SECONDS", "900")), 24 * 60 * 60)
)
STALE_SECONDS = max(
    RECENTLY_OFFLINE_SECONDS, min(int(os.environ.get("POCKETLAB_FLEET_STALE_SECONDS", str(7 * 24 * 60 * 60))), 180 * 24 * 60 * 60)
)
REVIEW_SECONDS = max(
    STALE_SECONDS, min(int(os.environ.get("POCKETLAB_FLEET_REVIEW_SECONDS", str(30 * 24 * 60 * 60))), 365 * 24 * 60 * 60)
)
MAX_LIFECYCLE_EVENTS = max(
    20, min(int(os.environ.get("POCKETLAB_FLEET_LIFECYCLE_EVENT_LIMIT", "200")), 1000)
)

_SAFE_TEXT_RE = re.compile(
    r"(?:token|password|secret|credential|api[_-]?key|private[_-]?key|"
    r"nats://|bootstrap|command_payload|raw_log|raw_evidence|/data/data/|/home/|~\/)",
    re.IGNORECASE,
)
_TERMINAL_TRUST = {"verified", "protected_server_host"}
_TERMINAL_ENROLLMENT = {"ready", "invite_expired", "invite_revoked", "join_blocked"}

CAPABILITY_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("host_apps", "Can host apps"),
    ("store_backups", "Can store backups"),
    ("run_safety_checks", "Runs safety checks"),
    ("receive_commands", "Receives commands"),
    ("supervisor_recovery", "Supervisor recovery"),
    ("remote_access", "Remote access"),
    ("serve_control_plane", "Serves Pocket Lab"),
    ("access_phone_media", "Can access phone media"),
    ("provide_storage", "Provides storage"),
    ("restore_target", "Restore target"),
    ("backup_target", "Backup target"),
)

_CAPABILITY_ALIASES = {
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms(value: Any = None) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number if number > 10_000_000_000 else number * 1000)
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any, limit: int = 220, fallback: str = "") -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if not text:
        return fallback
    if _SAFE_TEXT_RE.search(text):
        return fallback or "Protected metadata"
    return text[:limit]


def _normalize_id(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-._")
    return raw or "unknown-node"


def _read_state(name: str, default: Any) -> Any:
    try:
        return deps.core.read_json_file(deps.settings().state_dir / name, default)
    except Exception:
        return default


def _as_list(value: Any, limit: int = 1000) -> list[dict[str, Any]]:
    return [item for item in (value if isinstance(value, list) else [])[:limit] if isinstance(item, dict)]


def _device_keys(device: dict[str, Any]) -> set[str]:
    values = {
        _normalize_id(device.get("id")),
        _normalize_id(device.get("node_id")),
        _normalize_id(device.get("name")),
        _normalize_id(device.get("hostname")),
    }
    return {value for value in values if value != "unknown-node"}


def _matches_device(record: dict[str, Any], keys: set[str]) -> bool:
    if not keys:
        return False
    record_keys = {
        _normalize_id(record.get("device_id")),
        _normalize_id(record.get("node_id")),
        _normalize_id(record.get("hostname")),
        _normalize_id(record.get("name")),
        _normalize_id(record.get("existing_node_id")),
        _normalize_id(record.get("intended_node_id")),
    }
    return bool(keys.intersection({value for value in record_keys if value != "unknown-node"}))


def _latest_timestamp(values: Iterable[tuple[str, Any]]) -> tuple[str | None, str]:
    winner_at: str | None = None
    winner_source = "unknown"
    winner_epoch = 0
    for source, value in values:
        epoch = _epoch_ms(value)
        if epoch > winner_epoch:
            winner_epoch = epoch
            winner_at = str(value)
            winner_source = source
    return winner_at, winner_source


def _staleness(last_seen_at: Any, online: bool) -> dict[str, Any]:
    if online:
        return {
            "state": "online",
            "age_seconds": 0,
            "stale_since": None,
            "review_recommended": False,
        }
    epoch = _epoch_ms(last_seen_at)
    if not epoch:
        return {
            "state": "unknown",
            "age_seconds": None,
            "stale_since": None,
            "review_recommended": False,
        }
    age = max(0, int((int(time.time() * 1000) - epoch) / 1000))
    if age < RECENTLY_OFFLINE_SECONDS:
        state = "recently_offline"
    elif age < STALE_SECONDS:
        state = "offline"
    elif age < REVIEW_SECONDS:
        state = "stale"
    else:
        state = "review_recommended"
    return {
        "state": state,
        "age_seconds": age,
        "stale_since": str(last_seen_at) if state in {"stale", "review_recommended"} else None,
        "review_recommended": state == "review_recommended",
    }


def _normalized_advertised_capabilities(device: dict[str, Any]) -> set[str]:
    raw = device.get("advertised_capabilities")
    if not isinstance(raw, list):
        raw = device.get("agent_capabilities")
    if not isinstance(raw, list):
        raw = device.get("capabilities")
    normalized: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        value = str(item or "").strip().lower().replace(" ", "_")
        value = _CAPABILITY_ALIASES.get(value, value)
        if value:
            normalized.add(value)
    return normalized


def _capability(
    capability_id: str,
    label: str,
    *,
    advertised: bool,
    runtime_ready: bool | None,
    verified_at: Any,
    source: str,
    ready_reason: str = "",
    unavailable_reason: str = "",
) -> dict[str, Any]:
    if not advertised:
        status = "unknown"
        reason = "capability_not_advertised"
    elif runtime_ready is True:
        status = "ready"
        reason = ready_reason or "verified"
    elif runtime_ready is False:
        status = "not_ready"
        reason = unavailable_reason or "runtime_unavailable"
    else:
        status = "available"
        reason = "advertised_not_runtime_verified"
    return {
        "id": capability_id,
        "label": label,
        "status": status,
        "source": source,
        "verified_at": str(verified_at or "") or None,
        "reason_code": reason,
    }


def verified_capabilities(
    device: dict[str, Any],
    *,
    remote_access: dict[str, Any] | None = None,
    hosted_apps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    advertised = _normalized_advertised_capabilities(device)
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    protected = bool(device.get("is_current") or device.get("isCurrent") or role == "server_host")
    status = str(device.get("connection") or device.get("status") or "").lower()
    online = status in {"online", "active", "healthy", "ready"}
    supervisor = str(device.get("supervisor_status") or "").lower()
    process = str(device.get("agent_process_status") or "").lower()
    storage = device.get("storage") if isinstance(device.get("storage"), dict) else {}
    storage_ready = bool(storage.get("ready")) and online
    remote = remote_access if protected and isinstance(remote_access, dict) else {}
    remote_ready = bool(remote.get("ready")) if protected else bool(device.get("tailnet_ip") and online)
    apps = hosted_apps or []
    app_runtime_ready = any(str(app.get("status") or "").lower() in {"running", "ready", "healthy"} for app in apps)
    verified_at = (
        device.get("last_system_profile_at")
        or device.get("last_seen_at")
        or device.get("last_seen")
        or _now_iso()
    )

    runtime: dict[str, bool | None] = {
        "host_apps": app_runtime_ready if apps else (True if protected and "host_apps" in advertised else None),
        "store_backups": storage_ready,
        "run_safety_checks": True if protected and "run_safety_checks" in advertised else None,
        "receive_commands": online and "receive_commands" in advertised,
        "supervisor_recovery": (
            supervisor in {"healthy", "repairing"} and process not in {"missing", "errored", "error"}
        ),
        "remote_access": remote_ready,
        "serve_control_plane": True if protected else False,
        "access_phone_media": bool(protected and "access_phone_media" in advertised),
        "provide_storage": storage_ready,
        "restore_target": storage_ready,
        "backup_target": storage_ready,
    }
    result: list[dict[str, Any]] = []
    for capability_id, label in CAPABILITY_DEFINITIONS:
        result.append(
            _capability(
                capability_id,
                label,
                advertised=capability_id in advertised,
                runtime_ready=runtime.get(capability_id),
                verified_at=verified_at,
                source="agent_and_runtime" if capability_id in advertised else "agent_advertisement",
            )
        )
    return result


def _catalog_hosted_apps() -> dict[str, list[dict[str, Any]]]:
    state = _read_state("lite_catalog_state.json", {})
    apps = state.get("apps") if isinstance(state, dict) and isinstance(state.get("apps"), dict) else {}
    server_id = _normalize_id(os.environ.get("POCKETLAB_NODE_ID") or "pocket-lab-lite-server")
    result: dict[str, list[dict[str, Any]]] = {}
    for app_id, app in list(apps.items())[:32]:
        if not isinstance(app, dict):
            continue
        install_state = str(app.get("install_state") or "").lower()
        runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
        runtime_status = str(runtime.get("health") or app.get("status") or install_state or "unknown").lower()
        if install_state not in {"installed", "ready"} and runtime_status not in {"healthy", "ready", "running"}:
            continue
        host_id = _normalize_id(app.get("host_device_id") or server_id)
        result.setdefault(host_id, []).append(
            {
                "app_id": _safe_text(app_id, 80),
                "label": _safe_text(app.get("name") or str(app_id).replace("-", " ").title(), 80),
                "status": "running" if runtime_status in {"healthy", "ready", "running"} else "needs_attention",
                "dependency_level": "primary",
                "route_ready": bool((app.get("route") or {}).get("enabled")) if isinstance(app.get("route"), dict) else False,
            }
        )
    return result


def _backup_dependencies() -> dict[str, dict[str, Any]]:
    app_state = _read_state("lite_app_backup_state.json", {})
    backup_state = _read_state("backup_state.json", {})
    result: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    for payload in (app_state, backup_state):
        if isinstance(payload, dict):
            for key in ("backups", "backup_sets", "manifests", "targets"):
                candidates.extend(_as_list(payload.get(key), 500))
            for key in ("latest_backup", "last_backup"):
                if isinstance(payload.get(key), dict):
                    candidates.append(payload[key])
    verified_by_device: dict[str, int] = {}
    latest_by_device: dict[str, str] = {}
    for item in candidates:
        device_id = _normalize_id(item.get("target_device_id") or item.get("device_id") or item.get("node_id"))
        if device_id == "unknown-node":
            continue
        status = str(item.get("verification_status") or item.get("status") or "").lower()
        if status in {"verified", "succeeded", "healthy", "ready"}:
            verified_by_device[device_id] = verified_by_device.get(device_id, 0) + 1
        at = item.get("verified_at") or item.get("created_at") or item.get("updated_at")
        if _epoch_ms(at) > _epoch_ms(latest_by_device.get(device_id)):
            latest_by_device[device_id] = str(at)
    total_verified = sum(verified_by_device.values())
    for device_id, count in verified_by_device.items():
        result[device_id] = {
            "backup_set_count": count,
            "backup_repository_count": 1 if count else 0,
            "latest_backup_at": latest_by_device.get(device_id),
            "latest_verified_backup_at": latest_by_device.get(device_id),
            "stores_only_verified_copy": bool(count and total_verified == count),
        }
    return result


def _invite_records() -> list[dict[str, Any]]:
    payload = _read_state("fleet_invites.json", {"invites": []})
    return _as_list(payload.get("invites") if isinstance(payload, dict) else [], 500)


def _safe_events() -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for name in ("fleet_invite_events.json", "fleet_device_events.json"):
        payload = _read_state(name, {"events": []})
        combined.extend(_as_list(payload.get("events") if isinstance(payload, dict) else [], MAX_LIFECYCLE_EVENTS * 4))
    combined.sort(key=lambda item: _epoch_ms(item.get("occurred_at") or item.get("created_at") or item.get("timestamp")), reverse=True)
    return combined[: MAX_LIFECYCLE_EVENTS * 4]


_EVENT_TYPE_ALIASES = {
    "pocketlab.events.fleet.invite_created": "invite_created",
    "pocketlab.events.fleet.invite_accepted": "invite_accepted",
    "pocketlab.events.fleet.bootstrap_blocked": "identity_mismatch_blocked",
    "lite.fleet.device_removed": "device_removed",
}


def _normalize_event(record: dict[str, Any], device_id: str) -> dict[str, Any]:
    raw_type = str(record.get("event_type") or record.get("type") or "device_activity")
    event_type = _EVENT_TYPE_ALIASES.get(raw_type, raw_type.rsplit(".", 1)[-1].replace("-", "_"))
    occurred_at = (
        record.get("occurred_at")
        or record.get("created_at")
        or record.get("timestamp")
        or record.get("updated_at")
        or _now_iso()
    )
    reason_code = _safe_text(record.get("reason_code"), 80)
    if not reason_code and event_type == "identity_mismatch_blocked":
        reason_code = "invite_identity_mismatch"
    summary = _safe_text(record.get("summary"), 220)
    if not summary:
        summary = {
            "invite_created": "Device invite created.",
            "invite_accepted": "Device invite accepted.",
            "identity_mismatch_blocked": "A mismatched join attempt was blocked.",
            "device_removed": "Saved device record removed.",
        }.get(event_type, "Device activity recorded.")
    material = json.dumps(
        [device_id, event_type, occurred_at, reason_code, record.get("invite_id"), record.get("command_id")],
        separators=(",", ":"),
        sort_keys=False,
    )
    return {
        "event_id": hashlib.sha256(material.encode("utf-8")).hexdigest()[:24],
        "node_id": device_id,
        "event_type": event_type[:80],
        "reason_code": reason_code,
        "summary": summary,
        "occurred_at": str(occurred_at),
        "status": _safe_text(record.get("status") or ("blocked" if "blocked" in event_type else "recorded"), 32),
        "sanitized": True,
    }


def build_awareness_context() -> dict[str, Any]:
    return {
        "invites": _invite_records(),
        "events": _safe_events(),
        "hosted_apps": _catalog_hosted_apps(),
        "backup_dependencies": _backup_dependencies(),
    }


def enrich_device(
    device: dict[str, Any],
    *,
    remote_access: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context = context or build_awareness_context()
    device_id = _normalize_id(device.get("id") or device.get("node_id") or device.get("name"))
    keys = _device_keys(device)
    protected = bool(
        device.get("is_current")
        or device.get("isCurrent")
        or str(device.get("role") or "").lower() == "server_host"
    )
    matching_invites = [item for item in context.get("invites", []) if _matches_device(item, keys)]
    matching_invites.sort(key=lambda item: _epoch_ms(item.get("updated_at") or item.get("created_at")), reverse=True)
    invite = matching_invites[0] if matching_invites else {}
    recent_events = [
        _normalize_event(item, device_id)
        for item in context.get("events", [])
        if _matches_device(item, keys)
    ][:20]
    mismatch_events = [item for item in recent_events if item["event_type"] == "identity_mismatch_blocked"]

    status = str(device.get("status") or device.get("connection") or "").lower()
    online = status in {"healthy", "active", "online", "ready"}
    first_heartbeat = device.get("first_heartbeat_at")
    accepted_at = invite.get("accepted_at") or device.get("accepted_at")
    identity_status = str(device.get("identity_status") or "").lower()
    if protected:
        identity_status = "protected_server_host"
    elif identity_status not in _TERMINAL_TRUST:
        if mismatch_events and not first_heartbeat:
            identity_status = "join_blocked"
        elif first_heartbeat or (online and accepted_at):
            identity_status = "verified"
        elif accepted_at:
            identity_status = "pending"
        else:
            identity_status = "not_enrolled"

    invite_status = str(invite.get("status") or "").lower()
    if protected:
        enrollment_status = "ready"
    elif identity_status == "join_blocked":
        enrollment_status = "join_blocked"
    elif device.get("repair_required"):
        enrollment_status = "repair_required"
    elif online and identity_status == "verified":
        enrollment_status = "ready"
    elif accepted_at:
        enrollment_status = "waiting_for_heartbeat"
    elif invite_status == "revoked":
        enrollment_status = "invite_revoked"
    elif invite_status == "expired" or (
        invite.get("expires_at_epoch") and float(invite.get("expires_at_epoch") or 0) <= time.time()
    ):
        enrollment_status = "invite_expired"
    elif invite:
        enrollment_status = "invite_pending"
    else:
        enrollment_status = "not_enrolled"

    last_seen_at, last_seen_source = _latest_timestamp(
        (
            ("heartbeat", device.get("last_heartbeat_at") or device.get("last_seen_at") or device.get("last_seen")),
            ("telemetry", device.get("last_telemetry_at")),
            ("system_profile", device.get("last_system_profile_at")),
            ("supervisor", device.get("last_supervisor_at") or device.get("last_supervisor_heartbeat_at")),
            ("command", device.get("last_command_completed_at") or device.get("last_command_received_at")),
            ("nats", device.get("last_nats_connected_at")),
            ("recovery", device.get("last_recovery_at") or device.get("last_supervisor_repair_at")),
        )
    )
    staleness = _staleness(last_seen_at, online)

    hosted_apps = context.get("hosted_apps", {}).get(device_id, [])
    backup = context.get("backup_dependencies", {}).get(device_id, {})
    capabilities = verified_capabilities(
        device,
        remote_access=remote_access,
        hosted_apps=hosted_apps,
    )
    capability_by_id = {item["id"]: item for item in capabilities}

    device_commands = [
        item for item in (commands or [])
        if _normalize_id(item.get("node_id") or item.get("entity_id")) == device_id
    ]
    active_commands = [
        item for item in device_commands
        if str(item.get("status") or "").lower() in {"queued", "published", "received", "accepted", "running"}
    ]
    pending_count = len(active_commands)
    process_status = str(device.get("agent_process_status") or "").lower()
    supervisor_status = str(device.get("supervisor_status") or "").lower()
    if protected:
        delivery_status = "deliverable"
    elif process_status in {"stopped", "missing", "errored", "error"}:
        delivery_status = "agent_stopped"
    elif supervisor_status == "repairing" or status == "repairing":
        delivery_status = "repairing"
    elif online and capability_by_id.get("receive_commands", {}).get("status") == "ready":
        delivery_status = "deliverable"
    elif enrollment_status in {"invite_pending", "waiting_for_heartbeat"}:
        delivery_status = "waiting_for_agent"
    elif staleness["state"] in {"recently_offline", "offline", "stale", "review_recommended"}:
        delivery_status = "temporarily_unreachable"
    else:
        delivery_status = "unknown"

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    recommended_actions: list[str] = []
    if protected:
        blockers.append({"code": "protected_server_host", "summary": "This protected server host cannot be removed."})
    if online and not protected:
        blockers.append({"code": "device_online", "summary": "Online devices are protected. Disconnect or move its responsibilities before removal."})
    for app in hosted_apps:
        blockers.append({"code": "hosts_active_app", "summary": f"{app.get('label') or 'An app'} runs on this device."})
    if backup.get("stores_only_verified_copy"):
        blockers.append({"code": "only_verified_backup_copy", "summary": "This device stores the only verified backup copy."})
    elif int(backup.get("backup_set_count") or 0) > 0:
        warnings.append({"code": "stores_backup_sets", "summary": "This device stores verified backup sets."})
    if pending_count:
        blockers.append({"code": "pending_commands", "summary": "A device command is still active."})
    if status == "repairing" or supervisor_status == "repairing":
        blockers.append({"code": "active_recovery", "summary": "Device recovery is still in progress."})
    if staleness["state"] not in {"stale", "review_recommended"} and not blockers and not protected:
        warnings.append({"code": "not_stale", "summary": "Only old offline device records should normally be removed."})
    if hosted_apps:
        recommended_actions.append("Move the app")
    if backup.get("stores_only_verified_copy"):
        recommended_actions.append("Create another verified backup")
    if pending_count:
        recommended_actions.append("Wait for active commands to finish")

    assessment_revision_material = json.dumps(
        {
            "device_id": device_id,
            "online": online,
            "staleness": staleness["state"],
            "hosted_apps": [(item.get("app_id"), item.get("status")) for item in hosted_apps],
            "backup": backup,
            "pending_commands": pending_count,
            "supervisor": supervisor_status,
            "blockers": blockers,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assessment_revision = hashlib.sha256(assessment_revision_material.encode("utf-8")).hexdigest()[:20]
    safe_to_remove = bool(not blockers and not protected and staleness["state"] in {"stale", "review_recommended"})

    identity = {
        "status": identity_status,
        "verified_at": device.get("identity_verified_at") or (first_heartbeat if identity_status == "verified" else None),
        "source": "agent_invite_match" if identity_status == "verified" else "lifecycle_projection",
        "mismatch_count": max(int(device.get("identity_mismatch_count") or 0), len(mismatch_events)),
        "last_mismatch_at": device.get("last_identity_mismatch_at") or (mismatch_events[0]["occurred_at"] if mismatch_events else None),
        "last_blocked_reason": device.get("last_identity_reason_code") or (mismatch_events[0]["reason_code"] if mismatch_events else ""),
        "blocked_join_count": max(int(device.get("blocked_join_count") or 0), len(mismatch_events)),
        "last_blocked_join_at": device.get("last_blocked_join_at") or (mismatch_events[0]["occurred_at"] if mismatch_events else None),
        "repair_required": bool(device.get("repair_required") or identity_status in {"join_blocked", "needs_review"}),
        "repair_reason_code": _safe_text(device.get("repair_reason_code"), 80),
    }
    enrollment = {
        "status": enrollment_status,
        "invite_id": _safe_text(invite.get("invite_id"), 120) or None,
        "invite_created_at": invite.get("created_at"),
        "invite_expires_at": invite.get("expires_at"),
        "invite_accepted_at": accepted_at,
        "invite_revoked_at": invite.get("revoked_at"),
        "invite_expired_at": invite.get("expired_at"),
        "enrolled_at": device.get("enrolled_at") or first_heartbeat,
        "first_heartbeat_at": first_heartbeat,
        "first_supervisor_heartbeat_at": device.get("first_supervisor_heartbeat_at"),
        "first_ready_at": device.get("first_ready_at") or (first_heartbeat if enrollment_status == "ready" else None),
        "last_join_attempt_at": device.get("last_join_attempt_at") or accepted_at,
        "last_successful_join_at": device.get("last_successful_join_at") or (first_heartbeat if identity_status == "verified" else None),
    }
    last_seen = {
        "last_seen_at": last_seen_at,
        "last_seen_source": last_seen_source,
        "last_heartbeat_at": device.get("last_heartbeat_at") or device.get("last_seen_at") or device.get("last_seen"),
        "last_telemetry_at": device.get("last_telemetry_at"),
        "last_system_profile_at": device.get("last_system_profile_at"),
        "last_supervisor_heartbeat_at": device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at"),
        "last_command_received_at": device.get("last_command_received_at"),
        "last_command_completed_at": device.get("last_command_completed_at"),
        "last_nats_connected_at": device.get("last_nats_connected_at"),
        "last_nats_disconnected_at": device.get("last_nats_disconnected_at"),
        "last_tailnet_ready_at": device.get("last_tailnet_ready_at"),
        "last_recovery_at": device.get("last_recovery_at") or device.get("last_supervisor_repair_at"),
        "heartbeat_age_seconds": staleness["age_seconds"],
        "supervisor_age_seconds": (
            max(0, int((int(time.time() * 1000) - _epoch_ms(device.get("last_supervisor_at"))) / 1000))
            if _epoch_ms(device.get("last_supervisor_at")) else None
        ),
        "connection_age_seconds": staleness["age_seconds"],
        "staleness_state": staleness["state"],
        "stale_since": staleness["stale_since"],
        "review_recommended": staleness["review_recommended"],
    }
    storage = device.get("storage") if isinstance(device.get("storage"), dict) else {}
    storage_available_bytes = storage.get("available_bytes")
    if storage_available_bytes in (None, ""):
        available_gb = storage.get("available_gb") or device.get("available_gb") or device.get("storage_available_gb")
        try:
            storage_available_bytes = int(float(available_gb) * 1024 * 1024 * 1024) if available_gb not in (None, "") else None
        except (TypeError, ValueError):
            storage_available_bytes = None
    storage_pressure_state = "unknown"
    if storage_available_bytes is not None:
        storage_pressure_state = "critical" if storage_available_bytes < 512 * 1024 * 1024 else "low" if storage_available_bytes < 2 * 1024 * 1024 * 1024 else "healthy"

    dependencies = {
        "hosted_app_count": len(hosted_apps),
        "hosted_apps": hosted_apps[:16],
        "hosted_service_count": 1 if protected else 0,
        "control_plane_role": "primary" if protected else "none",
        "backup_target_status": capability_by_id.get("backup_target", {}).get("status", "unknown"),
        "backup_repository_count": int(backup.get("backup_repository_count") or 0),
        "backup_set_count": int(backup.get("backup_set_count") or 0),
        "latest_backup_at": backup.get("latest_backup_at"),
        "latest_verified_backup_at": backup.get("latest_verified_backup_at"),
        "stores_only_verified_copy": bool(backup.get("stores_only_verified_copy")),
        "restore_target_status": capability_by_id.get("restore_target", {}).get("status", "unknown"),
        "storage_dependency_count": int(capability_by_id.get("provide_storage", {}).get("status") in {"ready", "available"}),
        "storage_available_bytes": storage_available_bytes,
        "storage_pressure_state": storage_pressure_state,
        "tailscale_installed": bool((remote_access or {}).get("running") or device.get("tailscale_installed")) if protected else bool(device.get("tailscale_installed")),
        "tailscaled_running": bool((remote_access or {}).get("running")) if protected else bool(device.get("tailscaled_running")),
        "tailnet_ip_ready": bool((remote_access or {}).get("ip")) if protected else bool(device.get("tailnet_ip_ready") or device.get("tailnet_ip")),
        "nats_tailnet_reachable": bool((remote_access or {}).get("nats_reachable")) if protected else bool(device.get("nats_tailnet_reachable")),
        "remote_access_status": capability_by_id.get("remote_access", {}).get("status", "unknown"),
        "remote_access_last_verified_at": (
            remote_access.get("checked_at") if protected and isinstance(remote_access, dict) else device.get("last_tailnet_ready_at")
        ),
        "command_delivery_status": delivery_status,
        "last_command_ack_at": device.get("last_command_received_at"),
        "pending_command_count": pending_count,
        "active_command_count": pending_count,
        "supervisor_status": supervisor_status or "unknown",
        "agent_process_status": process_status or "unknown",
        "recovery_available": capability_by_id.get("supervisor_recovery", {}).get("status") in {"ready", "available"},
        "recovery_in_progress": status == "repairing" or supervisor_status == "repairing",
        "last_recovery_result": _safe_text(device.get("last_recovery_result"), 80),
    }
    removal = {
        "node_id": device_id,
        "safe_to_remove": safe_to_remove,
        "confirmation_required": True,
        "assessment_revision": assessment_revision,
        "blockers": blockers[:16],
        "warnings": warnings[:16],
        "recommended_actions": recommended_actions[:8],
        "staleness_state": staleness["state"],
    }

    return {
        **device,
        "advertised_capabilities": sorted(_normalized_advertised_capabilities(device)),
        "capabilities": [item for item in (device.get("capabilities") or []) if isinstance(item, str)][:32],
        "capability_states": capabilities,
        "capability_labels": list(dict.fromkeys(
            [str(item) for item in (device.get("capability_labels") or []) if str(item).strip()]
            + [item["label"] for item in capabilities if item["status"] in {"ready", "available"}]
        ))[:32],
        "enrollment": enrollment,
        "enrollment_status": enrollment_status,
        "identity": identity,
        "identity_status": identity_status,
        "last_seen_state": last_seen,
        "staleness_state": staleness["state"],
        "review_recommended": staleness["review_recommended"],
        "dependencies": dependencies,
        "removal_assessment": removal,
        "recent_lifecycle": recent_events,
        "trust_revision": assessment_revision,
        "staleness_policy": {
            "recently_offline_seconds": RECENTLY_OFFLINE_SECONDS,
            "stale_seconds": STALE_SECONDS,
            "review_seconds": REVIEW_SECONDS,
        },
    }


def enrich_devices(
    devices: list[dict[str, Any]],
    *,
    remote_access: dict[str, Any] | None = None,
    commands: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    context = build_awareness_context()
    return [
        enrich_device(item, remote_access=remote_access, context=context, commands=commands)
        for item in devices
        if isinstance(item, dict)
    ]
