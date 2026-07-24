from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

HEALTH_MODEL_VERSION = 1
CAPABILITY_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = 1

_REASON_CODES = frozenset({
    "storage_pressure", "memory_pressure", "high_load", "temperature_high",
    "heartbeat_stale", "telemetry_stale", "supervisor_stale",
    "connection_intermittent", "remote_access_unavailable", "agent_stopped",
    "repeated_recovery", "repair_failed", "agent_version_behind",
    "schema_incompatible", "pending_command_stale", "hosted_app_at_risk",
    "backup_dependency_at_risk", "identity_needs_review", "profile_stale",
})

_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_BAND_RANK = {"unknown": -1, "normal": 0, "watch": 1, "low": 2, "critical": 3}
_VERSION_RANK = {"unknown": -1, "current": 0, "update_available": 1, "behind": 2, "incompatible": 3}


def _now_iso(now_epoch: float | None = None) -> str:
    value = time.time() if now_epoch is None else float(now_epoch)
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _epoch(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000.0 if number > 10_000_000_000 else number
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _age_seconds(value: Any, now_epoch: float) -> int | None:
    parsed = _epoch(value)
    return max(0, int(now_epoch - parsed)) if parsed is not None else None


def _is_out_of_order(current: Any, previous: Any, *, tolerance_seconds: float = 1.0) -> bool:
    current_epoch = _epoch(current)
    previous_epoch = _epoch(previous)
    return bool(
        current_epoch is not None
        and previous_epoch is not None
        and current_epoch + max(0.0, tolerance_seconds) < previous_epoch
    )


def _number(value: Any, *, minimum: float = 0.0, maximum: float = 10_000_000_000.0) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed, 3) if minimum <= parsed <= maximum else None


def _integer(value: Any, *, minimum: int = 0, maximum: int = 2_000_000_000) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _safe_text(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    return text[:limit]


def _status(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower().replace("-", " ")).strip("_")


def _policy() -> dict[str, Any]:
    def env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    return {
        "storage": {
            "watch": env_float("POCKETLAB_DEVICE_HEALTH_STORAGE_WATCH_PERCENT", 20.0),
            "low": env_float("POCKETLAB_DEVICE_HEALTH_STORAGE_LOW_PERCENT", 10.0),
            "critical": env_float("POCKETLAB_DEVICE_HEALTH_STORAGE_CRITICAL_PERCENT", 5.0),
            "hysteresis": env_float("POCKETLAB_DEVICE_HEALTH_STORAGE_HYSTERESIS_PERCENT", 2.0),
        },
        "memory": {
            "watch": env_float("POCKETLAB_DEVICE_HEALTH_MEMORY_WATCH_PERCENT", 25.0),
            "low": env_float("POCKETLAB_DEVICE_HEALTH_MEMORY_LOW_PERCENT", 15.0),
            "critical": env_float("POCKETLAB_DEVICE_HEALTH_MEMORY_CRITICAL_PERCENT", 8.0),
            "hysteresis": env_float("POCKETLAB_DEVICE_HEALTH_MEMORY_HYSTERESIS_PERCENT", 3.0),
        },
        "load": {
            "watch": env_float("POCKETLAB_DEVICE_HEALTH_LOAD_WATCH_PERCENT", 70.0),
            "low": env_float("POCKETLAB_DEVICE_HEALTH_LOAD_LOW_PERCENT", 85.0),
            "critical": env_float("POCKETLAB_DEVICE_HEALTH_LOAD_CRITICAL_PERCENT", 95.0),
            "hysteresis": env_float("POCKETLAB_DEVICE_HEALTH_LOAD_HYSTERESIS_PERCENT", 3.0),
            "minimum_seconds": max(0, int(env_float("POCKETLAB_DEVICE_HEALTH_LOAD_MINIMUM_SECONDS", 60.0))),
        },
        "temperature": {
            "watch": env_float("POCKETLAB_DEVICE_HEALTH_TEMPERATURE_WATCH_C", 70.0),
            "low": env_float("POCKETLAB_DEVICE_HEALTH_TEMPERATURE_LOW_C", 80.0),
            "critical": env_float("POCKETLAB_DEVICE_HEALTH_TEMPERATURE_CRITICAL_C", 90.0),
            "hysteresis": env_float("POCKETLAB_DEVICE_HEALTH_TEMPERATURE_HYSTERESIS_C", 2.0),
        },
        "heartbeat_current_seconds": max(30, int(env_float("POCKETLAB_DEVICE_HEALTH_HEARTBEAT_CURRENT_SECONDS", 90.0))),
        "telemetry_current_seconds": max(60, int(env_float("POCKETLAB_DEVICE_HEALTH_TELEMETRY_CURRENT_SECONDS", 180.0))),
        "supervisor_current_seconds": max(30, int(env_float("POCKETLAB_DEVICE_HEALTH_SUPERVISOR_CURRENT_SECONDS", 120.0))),
        "profile_current_seconds": max(3600, int(env_float("POCKETLAB_DEVICE_HEALTH_PROFILE_CURRENT_SECONDS", 86400.0))),
        "reconnect_window_seconds": max(60, int(env_float("POCKETLAB_DEVICE_HEALTH_RECONNECT_WINDOW_SECONDS", 3600.0))),
        "recovery_minimum_seconds": max(0, int(env_float("POCKETLAB_DEVICE_HEALTH_RECOVERY_MINIMUM_SECONDS", 30.0))),
        "expected_agent_version": _safe_text(os.environ.get("POCKETLAB_LITE_EXPECTED_AGENT_VERSION", "2.5.0-lite-trust-capability-awareness"), 80),
        "expected_supervisor_version": _safe_text(os.environ.get("POCKETLAB_LITE_EXPECTED_SUPERVISOR_VERSION", "1.0.0-lite-agent-supervisor"), 80),
    }


def _raw_low_bad_band(value: float | None, thresholds: dict[str, float]) -> str:
    if value is None:
        return "unknown"
    if value < thresholds["critical"]:
        return "critical"
    if value <= thresholds["low"]:
        return "low"
    if value <= thresholds["watch"]:
        return "watch"
    return "normal"


def _raw_high_bad_band(value: float | None, thresholds: dict[str, float]) -> str:
    if value is None:
        return "unknown"
    if value >= thresholds["critical"]:
        return "critical"
    if value >= thresholds["low"]:
        return "low"
    if value >= thresholds["watch"]:
        return "watch"
    return "normal"


def _hysteresis_band(value: float | None, previous: str, thresholds: dict[str, float], *, low_is_bad: bool) -> str:
    raw = _raw_low_bad_band(value, thresholds) if low_is_bad else _raw_high_bad_band(value, thresholds)
    prior = previous if previous in _BAND_RANK else "unknown"
    if value is None or prior == "unknown" or raw == prior:
        return raw
    margin = max(0.0, float(thresholds.get("hysteresis") or 0.0))
    if low_is_bad:
        if _BAND_RANK[raw] > _BAND_RANK[prior]:
            boundary = {"watch": thresholds["watch"], "low": thresholds["low"], "critical": thresholds["critical"]}[raw]
            return raw if value <= boundary - margin else prior
        boundary = {"normal": thresholds["watch"], "watch": thresholds["low"], "low": thresholds["critical"]}[raw]
        return raw if value >= boundary + margin else prior
    if _BAND_RANK[raw] > _BAND_RANK[prior]:
        boundary = {"watch": thresholds["watch"], "low": thresholds["low"], "critical": thresholds["critical"]}[raw]
        return raw if value >= boundary + margin else prior
    boundary = {"normal": thresholds["watch"], "watch": thresholds["low"], "low": thresholds["critical"]}[raw]
    return raw if value <= boundary - margin else prior


def _duration_guard(resource: dict[str, Any], previous: dict[str, Any], now_iso: str, now_epoch: float, minimum_seconds: int) -> dict[str, Any]:
    if minimum_seconds <= 0:
        resource["candidate_status"] = None
        resource["candidate_since"] = None
        return resource
    desired = str(resource.get("status") or "unknown")
    prior_status = str(previous.get("status") or "unknown")
    if prior_status == "unknown":
        if desired in {"watch", "low", "critical"}:
            candidate = str(previous.get("candidate_status") or "")
            candidate_since = previous.get("candidate_since")
            if candidate == desired and candidate_since:
                age = _age_seconds(candidate_since, now_epoch) or 0
                if age >= minimum_seconds:
                    resource["candidate_status"] = None
                    resource["candidate_since"] = None
                    return resource
            resource["status"] = "unknown"
            resource["candidate_status"] = desired
            resource["candidate_since"] = candidate_since if candidate == desired and candidate_since else now_iso
            return resource
        resource["candidate_status"] = None
        resource["candidate_since"] = None
        return resource
    if desired in _BAND_RANK and prior_status in _BAND_RANK and _BAND_RANK[desired] > _BAND_RANK[prior_status]:
        candidate = str(previous.get("candidate_status") or "")
        candidate_since = previous.get("candidate_since")
        if candidate != desired or not candidate_since:
            resource["status"] = prior_status
            resource["candidate_status"] = desired
            resource["candidate_since"] = now_iso
            return resource
        age = _age_seconds(candidate_since, now_epoch) or 0
        if age < minimum_seconds:
            resource["status"] = prior_status
            resource["candidate_status"] = desired
            resource["candidate_since"] = candidate_since
            return resource
    resource["candidate_status"] = None
    resource["candidate_since"] = None
    return resource


def _recovery_duration_guard(
    resource: dict[str, Any],
    previous: dict[str, Any],
    now_iso: str,
    now_epoch: float,
    minimum_seconds: int,
) -> dict[str, Any]:
    desired = str(resource.get("status") or "unknown")
    prior_status = str(previous.get("status") or "unknown")
    if minimum_seconds <= 0 or desired not in _BAND_RANK or prior_status not in _BAND_RANK:
        resource["recovery_candidate_status"] = None
        resource["recovery_candidate_since"] = None
        return resource
    if _BAND_RANK[desired] < _BAND_RANK[prior_status]:
        candidate = str(previous.get("recovery_candidate_status") or "")
        candidate_since = previous.get("recovery_candidate_since")
        if candidate == desired and candidate_since:
            age = _age_seconds(candidate_since, now_epoch) or 0
            if age >= minimum_seconds:
                resource["recovery_candidate_status"] = None
                resource["recovery_candidate_since"] = None
                return resource
        resource["status"] = prior_status
        resource["recovery_candidate_status"] = desired
        resource["recovery_candidate_since"] = candidate_since if candidate == desired and candidate_since else now_iso
        return resource
    resource["recovery_candidate_status"] = None
    resource["recovery_candidate_since"] = None
    return resource


def _freshness_state(value: Any, now_epoch: float, current_seconds: int) -> dict[str, Any]:
    parsed = _epoch(value)
    if parsed is not None and parsed > now_epoch + 300:
        return {
            "state": "clock_skew",
            "age_seconds": 0,
            "reported_at": _safe_text(value, 64) or None,
        }
    age = _age_seconds(value, now_epoch)
    return {
        "state": "missing" if age is None else "current" if age <= current_seconds else "stale",
        "age_seconds": age,
        "reported_at": _safe_text(value, 64) or None,
    }


def _semantic(value: Any) -> tuple[int, int, int] | None:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", str(value or ""))
    return tuple(int(part) for part in match.groups()) if match else None


def _version_posture(value: Any, expected: Any) -> dict[str, Any]:
    current_parsed = _semantic(value)
    expected_parsed = _semantic(expected)
    if not current_parsed or not expected_parsed:
        return {"status": "unknown", "reported": _safe_text(value, 80), "expected": _safe_text(expected, 80)}
    if current_parsed == expected_parsed:
        status = "current"
    elif current_parsed[0] != expected_parsed[0]:
        status = "incompatible" if current_parsed[0] < expected_parsed[0] else "current"
    elif current_parsed < expected_parsed:
        status = "behind"
    else:
        status = "current"
    return {"status": status, "reported": _safe_text(value, 80), "expected": _safe_text(expected, 80)}


def _attention_template(reason: str) -> tuple[str, str, str, str]:
    templates = {
        "storage_pressure": ("resource", "Storage is getting full.", "Review storage before installing another app or creating a large backup.", "review_storage"),
        "memory_pressure": ("resource", "Available memory is limited.", "Review the device and pause nonessential work if the condition continues.", "review_device"),
        "high_load": ("resource", "System load has stayed high.", "Review the device and wait for active work to finish.", "review_device"),
        "temperature_high": ("resource", "Device temperature is high.", "Let the device cool and review active work.", "review_device"),
        "heartbeat_stale": ("connection", "The device has stopped reporting.", "Review the device connection before starting new work.", "review_device"),
        "telemetry_stale": ("resource", "Resource information is out of date.", "Wait for the device to report fresh health information.", "review_device"),
        "supervisor_stale": ("recovery", "Automatic recovery status is out of date.", "Review the device locally if the agent also stops reporting.", "review_device"),
        "connection_intermittent": ("connection", "Connection is intermittent.", "Review Remote Access Health and the device connection.", "open_remote_access_health"),
        "remote_access_unavailable": ("connection", "Remote access is not ready.", "Open Remote Access Health for the safest next step.", "open_remote_access_health"),
        "agent_stopped": ("recovery", "The device agent is stopped.", "Restart the agent through Pocket Lab when the action is available.", "restart_agent"),
        "repeated_recovery": ("recovery", "Automatic recovery has repeated.", "Review the device before starting more work.", "review_device"),
        "repair_failed": ("recovery", "Automatic recovery needs manual attention.", "Review the device locally and retry only after the cause is clear.", "review_device"),
        "agent_version_behind": ("software", "Agent software update is recommended.", "Review the device software posture. No update will run automatically.", "update_agent"),
        "schema_incompatible": ("software", "Device software is not compatible with this control plane.", "Review the device and rejoin or update it explicitly.", "review_device"),
        "pending_command_stale": ("command", "A device command has not completed.", "Review the device before sending another command.", "review_device"),
        "hosted_app_at_risk": ("dependency", "A hosted app may be affected.", "Open the app or review this device before starting more work.", "open_app"),
        "backup_dependency_at_risk": ("dependency", "Backup access may be affected.", "Open Backup & Restore and verify another safe copy is available.", "open_backup_restore"),
        "identity_needs_review": ("trust", "Device identity needs review.", "Review device identity before trusting new actions.", "review_identity"),
        "profile_stale": ("software", "System profile is out of date.", "Wait for a fresh device profile before making compatibility decisions.", "review_device"),
    }
    return templates.get(reason, ("device", "Device needs review.", "Review the device for the safest next step.", "review_device"))


def _reason_severity(reason: str, assessment: dict[str, Any]) -> str:
    if reason in {"heartbeat_stale", "agent_stopped", "repair_failed", "schema_incompatible"}:
        return "high"
    if reason in {"storage_pressure", "memory_pressure", "high_load", "temperature_high"}:
        resource = assessment.get("resources", {}).get(reason.split("_")[0] if reason != "high_load" else "load", {})
        return "critical" if resource.get("status") == "critical" else "high" if resource.get("status") == "low" else "medium"
    if reason in {"repeated_recovery", "hosted_app_at_risk", "backup_dependency_at_risk", "pending_command_stale"}:
        return "medium"
    return "low"


def _recommendation(reason_codes: list[str], recovery: dict[str, Any], dependency: dict[str, Any]) -> tuple[str, str | None]:
    order = (
        "agent_stopped", "repair_failed", "heartbeat_stale", "storage_pressure",
        "memory_pressure", "temperature_high", "high_load", "connection_intermittent",
        "remote_access_unavailable", "backup_dependency_at_risk", "hosted_app_at_risk",
        "identity_needs_review", "schema_incompatible", "agent_version_behind",
        "profile_stale", "telemetry_stale", "supervisor_stale",
    )
    if recovery.get("status") == "repairing":
        return "wait_for_recovery", None
    chosen = next((reason for reason in order if reason in reason_codes), "")
    action = _attention_template(chosen)[3] if chosen else "review_device"
    target: str | None = None
    if action == "open_app":
        apps = dependency.get("affected_apps") if isinstance(dependency.get("affected_apps"), list) else []
        target = str((apps[0] or {}).get("app_id") or "") if apps and isinstance(apps[0], dict) else None
    return action, target or None


def _resource_assessment(signals: dict[str, Any], previous: dict[str, Any], policy: dict[str, Any], now_iso: str, now_epoch: float) -> dict[str, Any]:
    telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
    storage = signals.get("storage") if isinstance(signals.get("storage"), dict) else {}
    resources: dict[str, Any] = {}

    total_mb = _number(telemetry.get("total_space_mb"))
    free_mb = _number(telemetry.get("free_space_mb"))
    if free_mb is None:
        available_bytes = _number(storage.get("available_bytes"))
        free_mb = round(available_bytes / (1024 * 1024), 1) if available_bytes is not None else None
    storage_percent = round((free_mb / total_mb) * 100.0, 1) if free_mb is not None and total_mb and total_mb > 0 else None
    prior_storage = previous.get("storage") if isinstance(previous.get("storage"), dict) else {}
    if storage_percent is not None:
        storage_status = _hysteresis_band(storage_percent, str(prior_storage.get("status") or "unknown"), policy["storage"], low_is_bad=True)
    elif free_mb is not None:
        absolute_percent = 100.0 if free_mb >= 4096 else 15.0 if free_mb >= 2048 else 7.0 if free_mb >= 512 else 1.0
        storage_status = _hysteresis_band(absolute_percent, str(prior_storage.get("status") or "unknown"), policy["storage"], low_is_bad=True)
    else:
        storage_status = "unknown"
    resources["storage"] = _recovery_duration_guard({
        "status": storage_status,
        "available_mb": int(free_mb) if free_mb is not None else None,
        "available_percent": storage_percent,
        "summary": "Storage information is unavailable." if storage_status == "unknown" else "Storage has room available." if storage_status == "normal" else "Storage is getting full." if storage_status == "watch" else "Storage is low." if storage_status == "low" else "Storage is critically low.",
    }, prior_storage, now_iso, now_epoch, int(policy["recovery_minimum_seconds"]))

    memory_total = _number(telemetry.get("memory_total_mb"))
    memory_free = _number(telemetry.get("memory_free_mb"))
    memory_percent = round((memory_free / memory_total) * 100.0, 1) if memory_free is not None and memory_total and memory_total > 0 else None
    prior_memory = previous.get("memory") if isinstance(previous.get("memory"), dict) else {}
    memory_status = _hysteresis_band(memory_percent, str(prior_memory.get("status") or "unknown"), policy["memory"], low_is_bad=True)
    resources["memory"] = _recovery_duration_guard({
        "status": memory_status,
        "available_mb": int(memory_free) if memory_free is not None else None,
        "available_percent": memory_percent,
        "summary": "Memory information is unavailable." if memory_status == "unknown" else "Memory is available." if memory_status == "normal" else "Available memory is limited." if memory_status == "watch" else "Memory is low." if memory_status == "low" else "Memory is critically low.",
    }, prior_memory, now_iso, now_epoch, int(policy["recovery_minimum_seconds"]))

    load_percent = _number(telemetry.get("cpu_usage_percent"), maximum=100.0)
    prior_load = previous.get("load") if isinstance(previous.get("load"), dict) else {}
    load_status = _hysteresis_band(load_percent, str(prior_load.get("status") or "unknown"), policy["load"], low_is_bad=False)
    load_resource = {
        "status": load_status,
        "usage_percent": load_percent,
        "summary": "System load is unavailable." if load_status == "unknown" else "System load is normal." if load_status == "normal" else "System load is elevated." if load_status == "watch" else "System load is high." if load_status == "low" else "System load is critically high.",
    }
    resources["load"] = _recovery_duration_guard(
        _duration_guard(load_resource, prior_load, now_iso, now_epoch, int(policy["load"]["minimum_seconds"])),
        prior_load,
        now_iso,
        now_epoch,
        int(policy["recovery_minimum_seconds"]),
    )

    temperature = _number(telemetry.get("cpu_temp_c"), maximum=200.0)
    prior_temperature = previous.get("temperature") if isinstance(previous.get("temperature"), dict) else {}
    temperature_status = _hysteresis_band(temperature, str(prior_temperature.get("status") or "unknown"), policy["temperature"], low_is_bad=False)
    resources["temperature"] = _recovery_duration_guard({
        "status": temperature_status,
        "celsius": temperature,
        "summary": "Temperature is unavailable." if temperature_status == "unknown" else "Temperature is normal." if temperature_status == "normal" else "Device temperature is elevated." if temperature_status == "watch" else "Device temperature is high." if temperature_status == "low" else "Device temperature is critically high.",
    }, prior_temperature, now_iso, now_epoch, int(policy["recovery_minimum_seconds"]))
    return resources


def evaluate_device_health(
    device: dict[str, Any],
    *,
    signals: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    """Return a bounded deterministic assessment from sanitized current device state."""
    previous = previous if isinstance(previous, dict) else {}
    signals = signals if isinstance(signals, dict) else {}
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    now_iso = _now_iso(now_epoch)
    policy = _policy()
    device_id = _safe_text(device.get("id") or device.get("node_id") or device.get("name"), 120)
    last_seen = device.get("last_seen_state") if isinstance(device.get("last_seen_state"), dict) else {}
    previous_freshness = previous.get("source_freshness") if isinstance(previous.get("source_freshness"), dict) else {}
    telemetry_reported_at = (
        last_seen.get("last_telemetry_at")
        or (signals.get("telemetry", {}).get("timestamp") if isinstance(signals.get("telemetry"), dict) else None)
    )
    telemetry_out_of_order = _is_out_of_order(
        telemetry_reported_at,
        (previous_freshness.get("telemetry") or {}).get("reported_at")
        if isinstance(previous_freshness.get("telemetry"), dict)
        else None,
    )

    freshness = {
        "heartbeat": _freshness_state(last_seen.get("last_heartbeat_at") or device.get("last_heartbeat_at") or device.get("last_seen_at"), now_epoch, policy["heartbeat_current_seconds"]),
        "telemetry": _freshness_state(telemetry_reported_at, now_epoch, policy["telemetry_current_seconds"]),
        "system_profile": _freshness_state(
            last_seen.get("last_system_profile_at")
            or (device.get("system_profile", {}).get("collected_at") if isinstance(device.get("system_profile"), dict) else None),
            now_epoch,
            policy["profile_current_seconds"],
        ),
        "supervisor": _freshness_state(last_seen.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at"), now_epoch, policy["supervisor_current_seconds"]),
    }
    if telemetry_out_of_order and isinstance(previous_freshness.get("telemetry"), dict):
        freshness["telemetry"] = {
            **previous_freshness["telemetry"],
            "ignored_out_of_order": True,
        }
    heartbeat_state = freshness["heartbeat"]["state"]
    freshness["state"] = "missing" if heartbeat_state == "missing" else "stale" if heartbeat_state == "stale" else "partial" if any(value["state"] != "current" for key, value in freshness.items() if key != "heartbeat") else "current"

    previous_resources = previous.get("resources") if isinstance(previous.get("resources"), dict) else {}
    resources = (
        previous_resources
        if telemetry_out_of_order and previous_resources
        else _resource_assessment(signals, previous_resources, policy, now_iso, now_epoch)
    )

    status = _status(device.get("status") or device.get("connection") or "unknown")
    agent_status = _status(device.get("agent_status") or status)
    process_status = _status(
        device.get("agent_process_status")
        or (device.get("dependencies", {}).get("agent_process_status") if isinstance(device.get("dependencies"), dict) else "")
    )
    supervisor_status = _status(
        device.get("supervisor_status")
        or (device.get("dependencies", {}).get("supervisor_status") if isinstance(device.get("dependencies"), dict) else "")
    )
    staleness = _status(device.get("staleness_state") or last_seen.get("staleness_state"))
    reconnect_count = _integer(signals.get("reconnect_count") or device.get("reconnect_count")) or 0
    dependencies = device.get("dependencies") if isinstance(device.get("dependencies"), dict) else {}
    command_delivery = _status(dependencies.get("command_delivery_status"))
    last_connected_at = last_seen.get("last_nats_connected_at")
    reconnect_age = _age_seconds(last_connected_at, now_epoch)
    reconnects_in_window = bool(
        reconnect_count >= 4
        and reconnect_age is not None
        and reconnect_age <= int(policy["reconnect_window_seconds"])
    )

    if supervisor_status == "repairing" or status == "repairing" or dependencies.get("recovery_in_progress"):
        connection_status = "recovering"
        connection_summary = "Pocket Lab is restoring the device connection."
    elif process_status in {"stopped", "missing", "errored", "error"} or status == "agent_stopped":
        connection_status = "disconnected"
        connection_summary = "The device agent is not reporting."
    elif staleness in {"offline", "stale", "review_recommended"} or (status in {"offline", "failed", "unhealthy"} and heartbeat_state != "current"):
        connection_status = "disconnected"
        connection_summary = "The device has stopped reporting."
    elif reconnects_in_window:
        connection_status = "intermittent"
        connection_summary = f"The device reconnected {reconnect_count} times during the recent connection window."
    elif dependencies.get("remote_access_status") in {"not_ready", "unavailable", "remote_access_not_ready"}:
        connection_status = "remote_access_not_ready"
        connection_summary = "The local device connection is available, but remote access is not ready."
    elif status in {"healthy", "active", "online", "ready"} or device.get("is_current"):
        connection_status = "stable"
        connection_summary = "The device connection is stable."
    else:
        connection_status = "unknown"
        connection_summary = "Connection quality is not available yet."
    connection = {
        "status": connection_status,
        "summary": connection_summary,
        "reconnect_count": reconnect_count,
        "command_delivery_status": command_delivery or "unknown",
        "remote_access_status": _status(dependencies.get("remote_access_status")) or "unknown",
        "last_connected_at": _safe_text(last_connected_at, 64) or None,
        "reconnect_window_seconds": int(policy["reconnect_window_seconds"]),
        "last_disconnected_at": _safe_text(last_seen.get("last_nats_disconnected_at"), 64) or None,
    }

    repair_count = _integer(signals.get("supervisor_repair_count") or device.get("supervisor_repair_count")) or 0
    last_recovery_at = last_seen.get("last_recovery_at") or device.get("last_recovery_at") or device.get("last_supervisor_repair_at")
    recovery_age = _age_seconds(last_recovery_at, now_epoch)
    last_recovery_result = _status(device.get("last_recovery_result") or dependencies.get("last_recovery_result"))
    if connection_status == "recovering":
        recovery_status = "repairing"
        recovery_summary = "Automatic recovery is in progress."
    elif process_status in {"stopped", "missing", "errored", "error"} and supervisor_status in {"", "unknown", "missing", "stopped", "failed"}:
        recovery_status = "manual_attention_required"
        recovery_summary = "The agent is stopped and automatic recovery is not available."
    elif last_recovery_result in {"failed", "failure", "timed_out"}:
        recovery_status = "manual_attention_required"
        recovery_summary = "The most recent automatic recovery did not complete."
    elif repair_count >= 4 and recovery_age is not None and recovery_age <= 3600:
        recovery_status = "repeated_recovery"
        recovery_summary = "The device has needed repeated automatic recovery."
    elif last_recovery_result in {"recovered", "succeeded", "completed"} and recovery_age is not None and recovery_age <= 86400:
        recovery_status = "recovered"
        recovery_summary = "Automatic recovery completed."
    else:
        recovery_status = "no_recent_recovery"
        recovery_summary = "No recent recovery was needed."
    recovery = {
        "status": recovery_status,
        "summary": recovery_summary,
        "recent_recovery_count": repair_count if recovery_age is not None and recovery_age <= 3600 else 0,
        "last_recovery_at": _safe_text(last_recovery_at, 64) or None,
        "last_recovery_result": last_recovery_result or "unknown",
        "automatic_recovery_available": bool(dependencies.get("recovery_available") or supervisor_status not in {"", "unknown", "missing"}),
    }
    previous_recovery = previous.get("recovery") if isinstance(previous.get("recovery"), dict) else {}
    if (
        connection_status != "recovering"
        and _is_out_of_order(last_recovery_at, previous_recovery.get("last_recovery_at"))
        and previous_recovery
    ):
        recovery = {**previous_recovery, "ignored_out_of_order": True}
        recovery_status = str(recovery.get("status") or "no_recent_recovery")

    profile = device.get("system_profile") if isinstance(device.get("system_profile"), dict) else {}
    agent_version = signals.get("agent_version") or profile.get("agent_version") or device.get("agent_version")
    supervisor_version = signals.get("supervisor_version") or profile.get("supervisor_version") or device.get("supervisor_version")
    version_parts = {
        "node_agent": _version_posture(agent_version, policy["expected_agent_version"]),
        "supervisor": _version_posture(supervisor_version, policy["expected_supervisor_version"]),
    }
    profile_schema = _integer(profile.get("schema_version"), minimum=1, maximum=100)
    capability_schema = _integer(signals.get("capability_schema_version") or device.get("capability_schema_version"), minimum=1, maximum=100)
    version_parts["system_profile_schema"] = {
        "status": "unknown" if profile_schema is None else "current" if profile_schema == PROFILE_SCHEMA_VERSION else "incompatible",
        "reported": profile_schema,
        "expected": PROFILE_SCHEMA_VERSION,
    }
    version_parts["capability_schema"] = {
        "status": "unknown" if capability_schema is None else "current" if capability_schema == CAPABILITY_SCHEMA_VERSION else "incompatible",
        "reported": capability_schema,
        "expected": CAPABILITY_SCHEMA_VERSION,
    }
    version_states = [str(part.get("status") or "unknown") for part in version_parts.values()]
    if "incompatible" in version_states:
        version_status = "incompatible"
    elif "behind" in version_states:
        version_status = "behind"
    elif version_states and all(value == "current" for value in version_states):
        version_status = "current"
    else:
        version_status = "unknown"
    versions = {"status": version_status, **version_parts}

    reason_codes: list[str] = []
    for resource_name, reason in (("storage", "storage_pressure"), ("memory", "memory_pressure"), ("load", "high_load"), ("temperature", "temperature_high")):
        if resources[resource_name]["status"] in {"watch", "low", "critical"}:
            reason_codes.append(reason)
    if heartbeat_state == "stale" or connection_status == "disconnected" and staleness in {"offline", "stale", "review_recommended"}:
        reason_codes.append("heartbeat_stale")
    if freshness["telemetry"]["state"] == "stale":
        reason_codes.append("telemetry_stale")
    if freshness["supervisor"]["state"] == "stale" and not device.get("is_current"):
        reason_codes.append("supervisor_stale")
    if connection_status == "intermittent":
        reason_codes.append("connection_intermittent")
    if connection_status == "remote_access_not_ready":
        reason_codes.append("remote_access_unavailable")
    if process_status in {"stopped", "missing", "errored", "error"} or status == "agent_stopped":
        reason_codes.append("agent_stopped")
    if recovery_status == "repeated_recovery":
        reason_codes.append("repeated_recovery")
    if recovery_status == "manual_attention_required" and "agent_stopped" not in reason_codes:
        reason_codes.append("repair_failed")
    if versions["node_agent"]["status"] == "behind":
        reason_codes.append("agent_version_behind")
    if versions["status"] == "incompatible":
        reason_codes.append("schema_incompatible")
    if command_delivery in {"stale", "timed_out", "undeliverable"} or int(dependencies.get("pending_command_count") or 0) > 0 and heartbeat_state == "stale":
        reason_codes.append("pending_command_stale")
    if _status(
        device.get("identity_status")
        or (device.get("identity", {}).get("status") if isinstance(device.get("identity"), dict) else "")
    ) in {"join_blocked", "needs_review", "mismatch"}:
        reason_codes.append("identity_needs_review")
    if freshness["system_profile"]["state"] == "stale":
        reason_codes.append("profile_stale")

    dependency_stale = freshness["state"] in {"missing", "stale"}
    hosted_apps = dependencies.get("hosted_apps") if isinstance(dependencies.get("hosted_apps"), list) else []
    material_risk = any(code in reason_codes for code in {"storage_pressure", "memory_pressure", "high_load", "temperature_high", "heartbeat_stale", "agent_stopped", "repeated_recovery", "repair_failed"})
    affected_apps = [
        {"app_id": _safe_text(item.get("app_id"), 80), "label": _safe_text(item.get("label") or "Hosted app", 120)}
        for item in hosted_apps[:8] if isinstance(item, dict)
    ] if material_risk and not dependency_stale else []
    backup_count = int(dependencies.get("backup_set_count") or 0)
    backup_risk = backup_count > 0 and any(code in reason_codes for code in {"heartbeat_stale", "agent_stopped", "connection_intermittent", "storage_pressure", "repeated_recovery", "repair_failed"}) and not dependency_stale
    if affected_apps:
        reason_codes.append("hosted_app_at_risk")
    if backup_risk:
        reason_codes.append("backup_dependency_at_risk")
    dependency_impact = {
        "status": "unknown" if dependency_stale else "at_risk" if affected_apps or backup_risk else "none",
        "impact_severity": "unknown" if dependency_stale else "medium" if affected_apps or backup_risk else "none",
        "impact_summary": "Dependency information is out of date." if dependency_stale else "Hosted apps or backups may be affected." if affected_apps or backup_risk else "No dependent app or backup impact is reported.",
        "affected_apps": affected_apps,
        "affected_backup_sets": [f"{backup_count} verified backup set{'s' if backup_count != 1 else ''}"] if backup_risk else [],
        "affected_capabilities": [value for value in ("remote_access" if connection_status in {"intermittent", "remote_access_not_ready", "disconnected"} else "", "host_apps" if affected_apps else "", "store_backups" if backup_risk else "") if value],
        "affected_recovery_paths": ["automatic_recovery"] if recovery_status in {"repeated_recovery", "manual_attention_required"} else [],
        "source_stale": dependency_stale,
    }

    reason_codes = [code for code in dict.fromkeys(reason_codes) if code in _REASON_CODES][:16]
    assessment_stub = {"resources": resources}
    severities = [_reason_severity(reason, assessment_stub) for reason in reason_codes]
    severity = max(severities, key=lambda item: _SEVERITY_RANK[item]) if severities else "none"
    if recovery_status == "repairing":
        overall_status = "repairing"
        summary = "Automatic recovery is in progress."
    elif connection_status == "disconnected" and "heartbeat_stale" in reason_codes:
        overall_status = "unreachable"
        summary = "The device has stopped reporting."
    elif severity in {"critical", "high"}:
        overall_status = "degraded"
        summary = _attention_template(reason_codes[0])[1] if reason_codes else "The device needs attention."
    elif severity == "medium":
        overall_status = "needs_attention"
        summary = _attention_template(reason_codes[0])[1]
    elif severity == "low":
        overall_status = "watch"
        summary = _attention_template(reason_codes[0])[1]
    elif not reason_codes and freshness["state"] != "current":
        overall_status = "unknown"
        summary = "Device health is waiting for fresh reports."
    elif not reason_codes and versions["status"] == "unknown":
        overall_status = "unknown"
        summary = "Device software posture is not available yet."
    elif connection_status == "stable" and heartbeat_state == "current":
        overall_status = "healthy"
        summary = "No immediate action is needed."
    else:
        overall_status = "unknown"
        summary = "Device health is not available yet."

    recommendation, recommendation_target = _recommendation(reason_codes, recovery, dependency_impact)
    material = {
        "model": HEALTH_MODEL_VERSION,
        "node_id": device_id,
        "status": overall_status,
        "severity": severity,
        "reason_codes": reason_codes,
        "resources": {key: {field: value for field, value in item.items() if field in {"status", "candidate_status", "candidate_since", "recovery_candidate_status", "recovery_candidate_since"}} for key, item in resources.items()},
        "connection": {key: connection.get(key) for key in ("status", "reconnect_count", "command_delivery_status", "remote_access_status")},
        "recovery": {key: recovery.get(key) for key in ("status", "recent_recovery_count", "last_recovery_result", "automatic_recovery_available")},
        "versions": {key: value.get("status") if isinstance(value, dict) else value for key, value in versions.items()},
        "dependency": {key: dependency_impact.get(key) for key in ("status", "impact_severity", "source_stale")},
        "recommendation": [recommendation, recommendation_target],
        "freshness": {key: value.get("state") if isinstance(value, dict) else value for key, value in freshness.items()},
    }
    health_revision = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20]
    unchanged = health_revision == str(previous.get("health_revision") or "")
    last_evaluated_at = previous.get("last_evaluated_at") if unchanged else now_iso

    previous_attention = {
        str(item.get("id") or ""): item
        for item in (previous.get("attention_items") or [])
        if isinstance(item, dict) and item.get("id")
    }
    attention_items: list[dict[str, Any]] = []
    for reason in reason_codes[:12]:
        category, item_summary, recommendation_text, action = _attention_template(reason)
        item_id = hashlib.sha256(f"{device_id}:{reason}".encode("utf-8")).hexdigest()[:24]
        prior_item = previous_attention.get(item_id, {})
        item_severity = _reason_severity(reason, assessment_stub)
        item_material = [category, item_severity, item_summary, recommendation_text, action]
        prior_material = [prior_item.get("category"), prior_item.get("severity"), prior_item.get("summary"), prior_item.get("recommendation"), prior_item.get("recommended_action")]
        attention_items.append({
            "id": item_id,
            "node_id": device_id,
            "category": category,
            "severity": item_severity,
            "status": "active",
            "reason_code": reason,
            "summary": item_summary,
            "recommendation": recommendation_text,
            "recommended_action": action,
            "created_at": prior_item.get("created_at") or now_iso,
            "updated_at": prior_item.get("updated_at") if item_material == prior_material else now_iso,
            "resolved_at": None,
            "source_revision": _integer(device.get("awareness_revision") or device.get("revision")) or 0,
        })

    return {
        "model_version": HEALTH_MODEL_VERSION,
        "node_id": device_id,
        "status": overall_status,
        "severity": severity,
        "summary": summary,
        "reason_codes": reason_codes,
        "attention_items": attention_items,
        "attention_count": len(attention_items),
        "recommended_action": recommendation if reason_codes or overall_status == "repairing" else "none",
        "recommended_action_target": recommendation_target,
        "last_evaluated_at": last_evaluated_at or now_iso,
        "health_revision": health_revision,
        "source_revision": _integer(device.get("awareness_revision") or device.get("revision")) or 0,
        "source_freshness": freshness,
        "resources": resources if not unchanged else previous.get("resources", resources),
        "connection": connection if not unchanged else previous.get("connection", connection),
        "recovery": recovery if not unchanged else previous.get("recovery", recovery),
        "versions": versions if not unchanged else previous.get("versions", versions),
        "dependency_impact": dependency_impact if not unchanged else previous.get("dependency_impact", dependency_impact),
        "sanitized": True,
    }
