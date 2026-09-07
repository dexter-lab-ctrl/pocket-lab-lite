from __future__ import annotations

from typing import Any, Callable


def _number(value: Any, *, maximum: float = 10_000_000_000.0) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > maximum or parsed != parsed:
        return None
    return parsed


def _observation_metadata(metric: str, observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_metric": metric,
        "observation_status": observation.get("collection_status") or observation.get("status") or "missing",
        "observed_at": observation.get("observed_at"),
        "freshness": observation.get("freshness") or "missing",
        "reason_code": observation.get("reason_code") or "resource_observation_missing",
        "support_state": observation.get("support_state") or "unknown",
        "source": observation.get("source") or "unknown",
        "revision": observation.get("revision"),
    }


def _assessment_ready(observation: dict[str, Any]) -> bool:
    return (
        str(observation.get("collection_status") or observation.get("status") or "") == "available"
        and str(observation.get("freshness") or "missing") == "current"
        and isinstance(observation.get("value"), dict)
    )


def _unassessed_summary(label: str, observation: dict[str, Any]) -> str:
    collection = str(observation.get("collection_status") or observation.get("status") or "missing")
    freshness = str(observation.get("freshness") or "missing")
    if freshness == "stale":
        return f"{label} measurement is stale; health assessment is not confirmed."
    if collection == "verification_pending":
        return f"{label} measurement is establishing a baseline."
    if collection == "permission_denied":
        return f"{label} measurement is restricted on this device."
    if collection == "unsupported":
        return f"{label} measurement is not supported on this device."
    if collection in {"transient_failure", "unavailable"}:
        return f"{label} measurement is temporarily unavailable."
    return f"{label} measurement has not been reported yet."


def assess_resource_observations(
    observations: dict[str, Any],
    previous: dict[str, Any],
    policy: dict[str, Any],
    now_iso: str,
    now_epoch: float,
    *,
    hysteresis_band: Callable[..., str],
    recovery_duration_guard: Callable[..., dict[str, Any]],
    duration_guard: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Assess health directly from canonical resource observations.

    Observation availability and health are intentionally separate. A valid
    measurement may be displayed even when its health assessment is unknown
    because the observation is stale. No unavailable observation is promoted to
    a healthy status and no legacy telemetry is synthesized here.
    """
    observations = observations if isinstance(observations, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    resources: dict[str, Any] = {}
    recovery_seconds = int(policy["recovery_minimum_seconds"])

    storage_obs = observations.get("storage") if isinstance(observations.get("storage"), dict) else {}
    storage_value = storage_obs.get("value") if isinstance(storage_obs.get("value"), dict) else {}
    total_mb = _number(storage_value.get("total_mb"))
    free_mb = _number(storage_value.get("free_mb"))
    storage_percent = round((free_mb / total_mb) * 100.0, 1) if free_mb is not None and total_mb and total_mb > 0 else None
    prior_storage = previous.get("storage") if isinstance(previous.get("storage"), dict) else {}
    if _assessment_ready(storage_obs) and storage_percent is not None:
        storage_status = hysteresis_band(storage_percent, str(prior_storage.get("status") or "unknown"), policy["storage"], low_is_bad=True)
    elif _assessment_ready(storage_obs) and free_mb is not None:
        absolute_percent = 100.0 if free_mb >= 4096 else 15.0 if free_mb >= 2048 else 7.0 if free_mb >= 512 else 1.0
        storage_status = hysteresis_band(absolute_percent, str(prior_storage.get("status") or "unknown"), policy["storage"], low_is_bad=True)
    else:
        storage_status = "unknown"
    storage_summary = (
        _unassessed_summary("Storage", storage_obs) if storage_status == "unknown"
        else "Storage has room available." if storage_status == "normal"
        else "Storage is getting full." if storage_status == "watch"
        else "Storage is low." if storage_status == "low"
        else "Storage is critically low."
    )
    resources["storage"] = recovery_duration_guard({
        "status": storage_status,
        "available_mb": int(free_mb) if free_mb is not None else None,
        "total_mb": int(total_mb) if total_mb is not None else None,
        "available_percent": storage_percent,
        "summary": storage_summary,
        **_observation_metadata("storage", storage_obs),
    }, prior_storage, now_iso, now_epoch, recovery_seconds)

    memory_obs = observations.get("memory") if isinstance(observations.get("memory"), dict) else {}
    memory_value = memory_obs.get("value") if isinstance(memory_obs.get("value"), dict) else {}
    memory_total = _number(memory_value.get("total_mb"))
    memory_free = _number(memory_value.get("free_mb"))
    memory_percent = round((memory_free / memory_total) * 100.0, 1) if memory_free is not None and memory_total and memory_total > 0 else None
    prior_memory = previous.get("memory") if isinstance(previous.get("memory"), dict) else {}
    memory_status = (
        hysteresis_band(memory_percent, str(prior_memory.get("status") or "unknown"), policy["memory"], low_is_bad=True)
        if _assessment_ready(memory_obs) and memory_percent is not None else "unknown"
    )
    memory_summary = (
        _unassessed_summary("Memory", memory_obs) if memory_status == "unknown"
        else "Memory is available." if memory_status == "normal"
        else "Available memory is limited." if memory_status == "watch"
        else "Memory is low." if memory_status == "low"
        else "Memory is critically low."
    )
    resources["memory"] = recovery_duration_guard({
        "status": memory_status,
        "available_mb": int(memory_free) if memory_free is not None else None,
        "total_mb": int(memory_total) if memory_total is not None else None,
        "available_percent": memory_percent,
        "summary": memory_summary,
        **_observation_metadata("memory", memory_obs),
    }, prior_memory, now_iso, now_epoch, recovery_seconds)

    workload_obs = observations.get("pocketlab_workload_cpu") if isinstance(observations.get("pocketlab_workload_cpu"), dict) else {}
    workload_value = workload_obs.get("value") if isinstance(workload_obs.get("value"), dict) else {}
    workload_percent = _number(workload_value.get("usage_percent"), maximum=100.0)
    process_count = _number(workload_value.get("process_count"), maximum=512.0)
    prior_load = previous.get("load") if isinstance(previous.get("load"), dict) else {}
    load_status = (
        hysteresis_band(workload_percent, str(prior_load.get("status") or "unknown"), policy["load"], low_is_bad=False)
        if _assessment_ready(workload_obs) and workload_percent is not None else "unknown"
    )
    load_summary = (
        _unassessed_summary("Pocket Lab workload CPU", workload_obs) if load_status == "unknown"
        else "Pocket Lab workload CPU is normal." if load_status == "normal"
        else "Pocket Lab workload CPU is elevated." if load_status == "watch"
        else "Pocket Lab workload CPU is high." if load_status == "low"
        else "Pocket Lab workload CPU is critically high."
    )
    load_resource = {
        "status": load_status,
        "usage_percent": workload_percent,
        "process_count": int(process_count) if process_count is not None else None,
        "summary": load_summary,
        **_observation_metadata("pocketlab_workload_cpu", workload_obs),
    }
    resources["load"] = recovery_duration_guard(
        duration_guard(load_resource, prior_load, now_iso, now_epoch, int(policy["load"]["minimum_seconds"])),
        prior_load,
        now_iso,
        now_epoch,
        recovery_seconds,
    )

    temperature_obs = observations.get("temperature") if isinstance(observations.get("temperature"), dict) else {}
    temperature_value = temperature_obs.get("value") if isinstance(temperature_obs.get("value"), dict) else {}
    temperature = _number(temperature_value.get("celsius"), maximum=200.0)
    prior_temperature = previous.get("temperature") if isinstance(previous.get("temperature"), dict) else {}
    temperature_status = (
        hysteresis_band(temperature, str(prior_temperature.get("status") or "unknown"), policy["temperature"], low_is_bad=False)
        if _assessment_ready(temperature_obs) and temperature is not None else "unknown"
    )
    temperature_summary = (
        _unassessed_summary("Temperature", temperature_obs) if temperature_status == "unknown"
        else "Temperature is normal." if temperature_status == "normal"
        else "Device temperature is elevated." if temperature_status == "watch"
        else "Device temperature is high." if temperature_status == "low"
        else "Device temperature is critically high."
    )
    resources["temperature"] = recovery_duration_guard({
        "status": temperature_status,
        "celsius": temperature,
        "summary": temperature_summary,
        **_observation_metadata("temperature", temperature_obs),
    }, prior_temperature, now_iso, now_epoch, recovery_seconds)
    return resources
