from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterable

RESOURCE_FACTS_SCHEMA_VERSION = 2
RESOURCE_CURRENT_SECONDS = 180
_ALLOWED_OBSERVATION_STATUSES = {
    "available", "verification_pending", "stale", "missing", "unsupported",
    "permission_denied", "unavailable", "transient_failure", "blocked", "not_applicable",
}
_SOURCE_PRIORITY = {
    "server_central_telemetry": 100,
    "agent_telemetry": 90,
    "canonical_observation": 80,
    "legacy_telemetry": 60,
    "system_health": 20,
}
_SECRETISH = re.compile(r"token|password|passwd|secret|credential|api[_-]?key|private[_-]?key|authorization|bearer\s+|nats://|/data/data/|/storage/emulated/|/home/|/mnt/|/root/", re.I)


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
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _number(value: Any, *, minimum: float = 0.0, maximum: float = 10_000_000_000.0) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        return None
    return round(parsed, 3)


def _freshness(observed_at: Any, now_epoch: float, current_seconds: int = RESOURCE_CURRENT_SECONDS) -> str:
    observed = _epoch(observed_at)
    if observed is None:
        return "missing"
    age = max(0.0, now_epoch - observed)
    return "current" if age <= max(1, int(current_seconds)) else "stale"


def _status(value: Any, fallback: str = "unavailable") -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower().replace("-", "_")).strip("_")
    if normalized in _ALLOWED_OBSERVATION_STATUSES:
        return normalized
    if normalized in {"ready", "healthy", "current", "reported", "supported", "ok"}:
        return "available"
    if normalized in {"collection_failed", "timeout", "provider_timeout", "transient_failure"}:
        return "transient_failure"
    if normalized in {"error", "failed", "unknown"}:
        return "unavailable"
    return fallback


def _sanitize_value(metric: str, value: Any) -> Any:
    if not isinstance(value, dict):
        return None
    if metric == "memory":
        total = _number(value.get("total_mb"))
        free = _number(value.get("free_mb"))
        used = _number(value.get("used_mb"))
        if total is None or total <= 0 or free is None or free > total:
            return None
        return {"total_mb": int(total), "free_mb": int(free), "used_mb": int(used if used is not None else max(0, total - free))}
    if metric == "storage":
        total = _number(value.get("total_mb"))
        free = _number(value.get("free_mb"))
        if total is None or total <= 0 or free is None or free > total:
            return None
        return {"total_mb": int(total), "free_mb": int(free)}
    if metric == "cpu_usage":
        usage = _number(value.get("usage_percent"), maximum=100.0)
        return {"usage_percent": usage} if usage is not None else None
    if metric == "temperature":
        celsius = _number(value.get("celsius"), minimum=1.0, maximum=150.0)
        return {"celsius": celsius} if celsius is not None else None
    if metric == "load_average":
        values = [
            _number(value.get("one_minute"), maximum=100_000.0),
            _number(value.get("five_minute"), maximum=100_000.0),
            _number(value.get("fifteen_minute"), maximum=100_000.0),
        ]
        return {"one_minute": values[0], "five_minute": values[1], "fifteen_minute": values[2]} if any(item is not None for item in values) else None
    if metric == "uptime":
        seconds = _number(value.get("seconds"), maximum=20 * 365 * 86400)
        return {"seconds": int(seconds)} if seconds is not None else None
    return None


def _legacy_observations(telemetry: dict[str, Any], source: str) -> dict[str, dict[str, Any]]:
    observed_at = telemetry.get("sampled_at") or telemetry.get("timestamp") or telemetry.get("time")
    result: dict[str, dict[str, Any]] = {}

    def add(metric: str, value: dict[str, Any] | None, unit: str | None = None) -> None:
        if value is None:
            return
        result[metric] = {
            "metric": metric,
            "value": value,
            "unit": unit,
            "status": "available",
            "source": source,
            "observed_at": observed_at,
            "reason_code": "legacy_telemetry_value",
            "support_state": "supported",
            "schema_version": 0,
        }

    memory_total = _number(telemetry.get("memory_total_mb") if telemetry.get("memory_total_mb") is not None else telemetry.get("memoryTotalMB"))
    memory_free = _number(telemetry.get("memory_free_mb") if telemetry.get("memory_free_mb") is not None else telemetry.get("memoryFreeMB"))
    memory_used = _number(telemetry.get("memory_usage_mb"))
    if memory_total is not None and memory_total > 0 and memory_free is not None and memory_free <= memory_total:
        add("memory", {"total_mb": int(memory_total), "free_mb": int(memory_free), "used_mb": int(memory_used if memory_used is not None else max(0, memory_total - memory_free))}, "MB")
    storage_total = _number(telemetry.get("total_space_mb") if telemetry.get("total_space_mb") is not None else telemetry.get("totalSpaceMB"))
    storage_free = _number(telemetry.get("free_space_mb") if telemetry.get("free_space_mb") is not None else telemetry.get("freeSpaceMB"))
    if storage_total is not None and storage_total > 0 and storage_free is not None and storage_free <= storage_total:
        add("storage", {"total_mb": int(storage_total), "free_mb": int(storage_free)}, "MB")
    cpu_usage = _number(telemetry.get("cpu_usage_percent"), maximum=100.0)
    if cpu_usage is not None:
        add("cpu_usage", {"usage_percent": cpu_usage}, "percent")
    cpu_temp = _number(telemetry.get("cpu_temp_c") if telemetry.get("cpu_temp_c") is not None else telemetry.get("cpuTemp"), minimum=1.0, maximum=150.0)
    if cpu_temp is not None:
        add("temperature", {"celsius": cpu_temp}, "celsius")
    return result


def normalize_resource_observations(
    telemetry: Any,
    *,
    source: str = "agent_telemetry",
    now_epoch: float | None = None,
    current_seconds: int = RESOURCE_CURRENT_SECONDS,
) -> dict[str, dict[str, Any]]:
    if not isinstance(telemetry, dict):
        return {}
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    raw = telemetry.get("resource_observations") if isinstance(telemetry.get("resource_observations"), dict) else {}
    if not raw:
        raw = _legacy_observations(telemetry, "legacy_telemetry")
    fallback_at = telemetry.get("sampled_at") or telemetry.get("timestamp") or telemetry.get("time")
    normalized: dict[str, dict[str, Any]] = {}
    for metric in ("memory", "storage", "cpu_usage", "temperature", "load_average", "uptime"):
        candidate = raw.get(metric) if isinstance(raw.get(metric), dict) else None
        if not candidate:
            continue
        observed_at = _safe_text(candidate.get("observed_at") or fallback_at, 64) or None
        if observed_at is not None and _epoch(observed_at) is None:
            observed_at = None
        state = _status(candidate.get("status"))
        value = _sanitize_value(metric, candidate.get("value"))
        if state == "available" and value is None:
            state = "unavailable"
            reason = "malformed_value"
        else:
            reason = _safe_text(candidate.get("reason_code"), 80, "collected" if state == "available" else state)
        freshness = _freshness(observed_at, now_epoch, current_seconds)
        if freshness == "stale" and state == "available":
            display_status = "stale"
        else:
            display_status = state
        record = {
            "metric": metric,
            "value": value,
            "unit": _safe_text(candidate.get("unit"), 32) or None,
            "status": display_status,
            "collection_status": state,
            "source": _safe_text(candidate.get("source"), 80, source),
            "observed_at": observed_at,
            "freshness": freshness,
            "reason_code": reason,
            "support_state": _safe_text(candidate.get("support_state"), 32, "supported" if state not in {"unsupported", "not_applicable"} else "unsupported"),
            "schema_version": max(0, min(100, int(candidate.get("schema_version") or telemetry.get("schema_version") or 0))),
        }
        revision_material = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        record["revision"] = max(1, int.from_bytes(hashlib.sha256(revision_material.encode("utf-8")).digest()[:8], "big") & ((1 << 63) - 1))
        normalized[metric] = record
    return normalized


def choose_resource_observation(
    candidates: Iterable[dict[str, Any]],
    *,
    now_epoch: float | None = None,
) -> dict[str, Any] | None:
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    ranked: list[tuple[int, float, int, dict[str, Any]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        observed = _epoch(candidate.get("observed_at")) or 0.0
        freshness = str(candidate.get("freshness") or _freshness(candidate.get("observed_at"), now_epoch))
        freshness_rank = {"current": 3, "stale": 2, "missing": 0}.get(freshness, 1)
        source = str(candidate.get("source") or "")
        source_rank = max((priority for key, priority in _SOURCE_PRIORITY.items() if key in source), default=40)
        status_rank = 1 if str(candidate.get("collection_status") or candidate.get("status")) == "available" else 0
        ranked.append((freshness_rank, observed, source_rank + status_rank, candidate))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return dict(ranked[0][3])


def reconcile_resource_observations(
    *sources: dict[str, dict[str, Any]],
    now_epoch: float | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for metric in ("memory", "storage", "cpu_usage", "temperature", "load_average", "uptime"):
        chosen = choose_resource_observation(
            [source[metric] for source in sources if isinstance(source, dict) and isinstance(source.get(metric), dict)],
            now_epoch=now_epoch,
        )
        if chosen:
            result[metric] = chosen
    return result


def health_signal_telemetry(observations: dict[str, dict[str, Any]], *, sampled_at: Any = None) -> dict[str, Any]:
    telemetry: dict[str, Any] = {
        "sampled_at": sampled_at,
        "timestamp": sampled_at,
        "resource_observations": observations,
    }
    memory = observations.get("memory") or {}
    if memory.get("value") and memory.get("collection_status") == "available":
        value = memory["value"]
        telemetry.update({"memory_total_mb": value.get("total_mb"), "memory_free_mb": value.get("free_mb"), "memory_usage_mb": value.get("used_mb")})
    storage = observations.get("storage") or {}
    if storage.get("value") and storage.get("collection_status") == "available":
        value = storage["value"]
        telemetry.update({"total_space_mb": value.get("total_mb"), "free_space_mb": value.get("free_mb")})
    cpu = observations.get("cpu_usage") or {}
    if cpu.get("value") and cpu.get("collection_status") == "available":
        telemetry["cpu_usage_percent"] = cpu["value"].get("usage_percent")
    temperature = observations.get("temperature") or {}
    if temperature.get("value") and temperature.get("collection_status") == "available":
        telemetry["cpu_temp_c"] = temperature["value"].get("celsius")
    return telemetry


def _software_fact(device: dict[str, Any], component: str) -> dict[str, Any]:
    profile = device.get("system_profile") if isinstance(device.get("system_profile"), dict) else {}
    facts = device.get("device_facts") if isinstance(device.get("device_facts"), dict) else {}
    proactive = device.get("proactive_health") if isinstance(device.get("proactive_health"), dict) else {}
    proactive_facts = proactive.get("device_facts") if isinstance(proactive.get("device_facts"), dict) else {}

    persisted: list[tuple[Any, Any, Any, Any]] = []
    for container in (facts, proactive_facts):
        software = container.get("software") if isinstance(container.get("software"), dict) else {}
        record = software.get(component) if isinstance(software.get(component), dict) else {}
        if record.get("version") not in (None, "", "unknown"):
            persisted.append((
                record.get("version"),
                record.get("source") or "canonical_device_facts",
                record.get("observed_at"),
                record.get("freshness") or record.get("status"),
            ))

    if component == "node_agent":
        candidates = [
            (device.get("agent_version"), device.get("agent_version_source") or "runtime_heartbeat", device.get("last_heartbeat_at") or device.get("last_seen_at"), device.get("agent_version_freshness")),
            (profile.get("agent_version"), "system_profile", profile.get("collected_at"), profile.get("freshness")),
            *persisted,
        ]
    else:
        candidates = [
            (device.get("supervisor_version"), device.get("supervisor_status_source") or "supervisor_evidence", device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at"), device.get("supervisor_status_freshness")),
            (profile.get("supervisor_version"), "system_profile", profile.get("collected_at"), profile.get("freshness")),
            *persisted,
        ]
    present = [(str(value), str(source), observed_at, freshness) for value, source, observed_at, freshness in candidates if value not in (None, "", "unknown")]
    if not present:
        return {"component": component, "version": None, "status": "unknown", "source": "unavailable", "observed_at": None, "freshness": "missing", "reason_code": "version_not_reported"}
    present.sort(key=lambda row: (_epoch(row[2]) or 0.0, 1 if str(row[3]).lower() in {"fresh", "current"} else 0), reverse=True)
    value, source, observed_at, freshness = present[0]
    normalized_freshness = "current" if str(freshness).lower() in {"fresh", "current"} else "stale" if str(freshness).lower() in {"stale", "saved"} else _freshness(observed_at, time.time(), 86400)
    return {"component": component, "version": _safe_text(value, 80), "status": "current" if normalized_freshness == "current" else "stale", "source": _safe_text(source, 80, "runtime"), "observed_at": _safe_text(observed_at, 64) or None, "freshness": normalized_freshness, "reason_code": "authoritative_version_evidence" if normalized_freshness == "current" else "version_evidence_stale"}


def build_device_facts(
    device: dict[str, Any],
    *,
    telemetry: dict[str, Any] | None = None,
    telemetry_source: str = "agent_telemetry",
    now_epoch: float | None = None,
) -> dict[str, Any]:
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    sources: list[dict[str, dict[str, Any]]] = []
    existing = device.get("resource_observations") if isinstance(device.get("resource_observations"), dict) else {}
    if existing:
        sources.append(existing)
    facts = device.get("device_facts") if isinstance(device.get("device_facts"), dict) else {}
    if isinstance(facts.get("resources"), dict):
        sources.append(facts["resources"])
    proactive = device.get("proactive_health") if isinstance(device.get("proactive_health"), dict) else {}
    if isinstance(proactive.get("resource_observations"), dict):
        sources.append(proactive["resource_observations"])
    if isinstance(proactive.get("device_facts"), dict) and isinstance(proactive["device_facts"].get("resources"), dict):
        sources.append(proactive["device_facts"]["resources"])
    candidate_telemetry = telemetry if isinstance(telemetry, dict) else device.get("telemetry") if isinstance(device.get("telemetry"), dict) else {}
    if not candidate_telemetry and isinstance(device.get("_health_signals"), dict):
        candidate_telemetry = device["_health_signals"].get("telemetry") if isinstance(device["_health_signals"].get("telemetry"), dict) else {}
    normalized = normalize_resource_observations(candidate_telemetry, source=telemetry_source, now_epoch=now_epoch)
    if normalized:
        for value in normalized.values():
            if telemetry_source and value.get("source") in {"legacy_telemetry", "platform"}:
                value["source"] = telemetry_source
        sources.append(normalized)
    resources = reconcile_resource_observations(*sources, now_epoch=now_epoch)
    software = {
        "node_agent": _software_fact(device, "node_agent"),
        "supervisor": _software_fact(device, "supervisor"),
    }
    observed_at = max((str(item.get("observed_at")) for item in resources.values() if item.get("observed_at")), default=None)
    result = {
        "schema_version": RESOURCE_FACTS_SCHEMA_VERSION,
        "device_id": _safe_text(device.get("id") or device.get("node_id") or device.get("name"), 120),
        "resources": resources,
        "software": software,
        "observed_at": observed_at,
        "sanitized": True,
    }
    revision_material = json.dumps({"resources": resources, "software": software}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    result["revision"] = max(1, int.from_bytes(hashlib.sha256(revision_material.encode("utf-8")).digest()[:8], "big") & ((1 << 63) - 1))
    return result


def apply_device_facts(
    device: dict[str, Any],
    *,
    telemetry: dict[str, Any] | None = None,
    telemetry_source: str = "agent_telemetry",
) -> dict[str, Any]:
    facts = build_device_facts(device, telemetry=telemetry, telemetry_source=telemetry_source)
    result = {**device, "device_facts": facts, "resource_observations": facts["resources"]}
    signals = dict(result.get("_health_signals") or {}) if isinstance(result.get("_health_signals"), dict) else {}
    sampled_at = None
    if isinstance(telemetry, dict):
        sampled_at = telemetry.get("sampled_at") or telemetry.get("timestamp") or telemetry.get("time")
    if sampled_at is None:
        sampled_at = device.get("last_telemetry_at")
    canonical_telemetry = health_signal_telemetry(facts["resources"], sampled_at=sampled_at)
    existing_telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
    signals["telemetry"] = {**existing_telemetry, **canonical_telemetry}
    signals["resource_observations"] = facts["resources"]
    software = facts.get("software") or {}
    if software.get("node_agent", {}).get("version"):
        signals["agent_version"] = software["node_agent"]["version"]
    if software.get("supervisor", {}).get("version"):
        signals["supervisor_version"] = software["supervisor"]["version"]
    result["_health_signals"] = signals
    return result