"""Bounded, platform-safe resource telemetry providers for Pocket Lab Lite.

Collectors return compatibility numeric fields plus canonical observations.  A
failed metric never becomes an invented numeric zero and never invalidates the
rest of the sample.  No private filesystem paths are included in returned
payloads.
"""
from __future__ import annotations

import glob
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

RESOURCE_OBSERVATION_SCHEMA_VERSION = 2
_MAX_TEXT_BYTES = 64 * 1024
_MAX_THERMAL_ZONES = 64
_CPU_PREVIOUS: tuple[int, int] | None = None


@dataclass(frozen=True)
class ResourceProvider:
    metric: str
    source: str
    collector: Callable[..., dict[str, Any]]
    max_duration_ms: float = 250.0


def _run_provider(provider: ResourceProvider, observed_at: str, *args: Any) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = provider.collector(observed_at, *args)
    except PermissionError:
        result = _failure(provider.metric, source=provider.source, observed_at=observed_at, reason_code="permission_denied")
    except Exception:
        result = _failure(provider.metric, source=provider.source, observed_at=observed_at, reason_code="collection_failed")
    elapsed_ms = (time.monotonic() - started) * 1000.0
    if elapsed_ms > max(1.0, float(provider.max_duration_ms)):
        return _failure(provider.metric, source=provider.source, observed_at=observed_at, reason_code="provider_timeout")
    return result if isinstance(result, dict) else _failure(provider.metric, source=provider.source, observed_at=observed_at, reason_code="collection_failed")


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_source(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9_.:-]+", "_", str(value or "").strip().lower()).strip("_:")
    return (text or fallback)[:80]


def _observation(
    metric: str,
    *,
    value: Any = None,
    unit: str = "",
    status: str,
    source: str,
    observed_at: str,
    reason_code: str,
    support_state: str = "supported",
) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "unit": unit or None,
        "status": status,
        "source": _safe_source(source, "platform"),
        "observed_at": observed_at,
        "freshness": "current",
        "reason_code": reason_code,
        "support_state": support_state,
        "schema_version": RESOURCE_OBSERVATION_SCHEMA_VERSION,
    }


def _failure(metric: str, *, source: str, observed_at: str, reason_code: str) -> dict[str, Any]:
    status = "permission_denied" if reason_code == "permission_denied" else "unsupported" if reason_code in {"unsupported", "not_present"} else "transient_failure" if reason_code in {"collection_failed", "provider_timeout"} else "unavailable"
    support = "unsupported" if status == "unsupported" else "supported"
    return _observation(
        metric,
        status=status,
        source=source,
        observed_at=observed_at,
        reason_code=reason_code,
        support_state=support,
    )


def _read_text(path: Path, *, limit: int = _MAX_TEXT_BYTES) -> tuple[str | None, str | None]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            value = handle.read(limit + 1)
    except PermissionError:
        return None, "permission_denied"
    except FileNotFoundError:
        return None, "not_present"
    except OSError:
        return None, "collection_failed"
    if len(value) > limit:
        return None, "output_too_large"
    return value, None


def _memory(observed_at: str) -> dict[str, Any]:
    text, error = _read_text(Path("/proc/meminfo"))
    if error:
        return _failure("memory", source="proc_meminfo", observed_at=observed_at, reason_code=error)
    values: dict[str, int] = {}
    for line in (text or "").splitlines()[:256]:
        parts = line.split()
        if len(parts) < 2 or not parts[0].endswith(":"):
            continue
        try:
            values[parts[0][:-1]] = int(parts[1])
        except (TypeError, ValueError):
            continue
    total_kib = values.get("MemTotal")
    available_kib = values.get("MemAvailable", values.get("MemFree"))
    if not total_kib or available_kib is None or total_kib <= 0 or available_kib < 0:
        return _failure("memory", source="proc_meminfo", observed_at=observed_at, reason_code="malformed_value")
    total_mb = int(total_kib // 1024)
    free_mb = int(min(total_kib, available_kib) // 1024)
    return _observation(
        "memory",
        value={"total_mb": total_mb, "free_mb": free_mb, "used_mb": max(0, total_mb - free_mb)},
        unit="MB",
        status="available",
        source="proc_meminfo",
        observed_at=observed_at,
        reason_code="collected",
    )


def _storage(observed_at: str, root: Path) -> dict[str, Any]:
    try:
        stat = os.statvfs(str(root))
        total_mb = int((stat.f_blocks * stat.f_frsize) // (1024 * 1024))
        free_mb = int((stat.f_bavail * stat.f_frsize) // (1024 * 1024))
    except PermissionError:
        return _failure("storage", source="statvfs", observed_at=observed_at, reason_code="permission_denied")
    except OSError:
        return _failure("storage", source="statvfs", observed_at=observed_at, reason_code="collection_failed")
    if total_mb <= 0 or free_mb < 0 or free_mb > total_mb:
        return _failure("storage", source="statvfs", observed_at=observed_at, reason_code="malformed_value")
    return _observation(
        "storage",
        value={"total_mb": total_mb, "free_mb": free_mb},
        unit="MB",
        status="available",
        source="statvfs",
        observed_at=observed_at,
        reason_code="collected",
    )


def _read_proc_stat() -> tuple[tuple[int, int] | None, str | None]:
    text, error = _read_text(Path("/proc/stat"), limit=8192)
    if error:
        return None, error
    first = (text or "").splitlines()[0:1]
    if not first or not first[0].startswith("cpu "):
        return None, "malformed_value"
    try:
        values = [int(value) for value in first[0].split()[1:11]]
    except ValueError:
        return None, "malformed_value"
    if len(values) < 4:
        return None, "malformed_value"
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return (total, idle), None


def _cpu_usage(observed_at: str) -> dict[str, Any]:
    global _CPU_PREVIOUS
    current, error = _read_proc_stat()
    if error:
        return _failure("cpu_usage", source="proc_stat", observed_at=observed_at, reason_code=error)
    if current is None:
        return _failure("cpu_usage", source="proc_stat", observed_at=observed_at, reason_code="malformed_value")
    previous = _CPU_PREVIOUS
    _CPU_PREVIOUS = current
    if previous is None:
        return _observation(
            "cpu_usage",
            status="verification_pending",
            source="proc_stat",
            observed_at=observed_at,
            reason_code="baseline_required",
        )
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0 or idle_delta < 0:
        return _failure("cpu_usage", source="proc_stat", observed_at=observed_at, reason_code="malformed_value")
    percent = max(0.0, min(100.0, ((total_delta - idle_delta) / total_delta) * 100.0))
    return _observation(
        "cpu_usage",
        value={"usage_percent": round(percent, 1)},
        unit="percent",
        status="available",
        source="proc_stat",
        observed_at=observed_at,
        reason_code="collected",
    )


def _load_average(observed_at: str) -> dict[str, Any]:
    try:
        values = os.getloadavg()
    except PermissionError:
        return _failure("load_average", source="platform_loadavg", observed_at=observed_at, reason_code="permission_denied")
    except (AttributeError, OSError):
        return _failure("load_average", source="platform_loadavg", observed_at=observed_at, reason_code="unsupported")
    normalized = [round(float(value), 3) for value in values[:3]]
    if len(normalized) != 3 or any(value < 0 or value > 100_000 for value in normalized):
        return _failure("load_average", source="platform_loadavg", observed_at=observed_at, reason_code="malformed_value")
    return _observation(
        "load_average",
        value={"one_minute": normalized[0], "five_minute": normalized[1], "fifteen_minute": normalized[2]},
        status="available",
        source="platform_loadavg",
        observed_at=observed_at,
        reason_code="collected",
    )


def _uptime(observed_at: str) -> dict[str, Any]:
    if hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_BOOTTIME"):
        try:
            seconds = float(time.clock_gettime(time.CLOCK_BOOTTIME))
            if 0 <= seconds <= 20 * 365 * 86400:
                return _observation(
                    "uptime",
                    value={"seconds": int(seconds)},
                    unit="seconds",
                    status="available",
                    source="monotonic_boot_clock",
                    observed_at=observed_at,
                    reason_code="collected",
                )
        except OSError:
            pass
    text, error = _read_text(Path("/proc/uptime"), limit=1024)
    if error:
        return _failure("uptime", source="proc_uptime", observed_at=observed_at, reason_code=error)
    try:
        seconds = float((text or "").split()[0])
    except (IndexError, TypeError, ValueError):
        return _failure("uptime", source="proc_uptime", observed_at=observed_at, reason_code="malformed_value")
    if not (0 <= seconds <= 20 * 365 * 86400):
        return _failure("uptime", source="proc_uptime", observed_at=observed_at, reason_code="malformed_value")
    return _observation(
        "uptime",
        value={"seconds": int(seconds)},
        unit="seconds",
        status="available",
        source="proc_uptime",
        observed_at=observed_at,
        reason_code="collected",
    )


_THERMAL_POSITIVE = ("cpu", "soc", "ap", "package", "processor", "cluster")
_THERMAL_NEGATIVE = ("modem", "camera", "charger", "bcl", "pa_", "pa-", "battery", "usb", "wifi", "wlan")


def _thermal_score(sensor_type: str) -> int:
    value = sensor_type.lower()
    if any(term in value for term in _THERMAL_NEGATIVE):
        return -100
    score = 0
    for index, term in enumerate(_THERMAL_POSITIVE):
        if term in value:
            score = max(score, 20 - index)
    return score


def _temperature(observed_at: str) -> dict[str, Any]:
    candidates: list[tuple[int, float, str]] = []
    saw_zone = False
    saw_permission = False
    saw_invalid = False
    for raw_path in sorted(glob.glob("/sys/class/thermal/thermal_zone*"))[:_MAX_THERMAL_ZONES]:
        saw_zone = True
        zone = Path(raw_path)
        sensor_type_text, type_error = _read_text(zone / "type", limit=256)
        temp_text, temp_error = _read_text(zone / "temp", limit=256)
        if type_error == "permission_denied" or temp_error == "permission_denied":
            saw_permission = True
            continue
        if type_error or temp_error:
            continue
        sensor_type = _safe_source((sensor_type_text or "").strip(), "thermal")
        score = _thermal_score(sensor_type)
        if score <= 0:
            continue
        try:
            raw = float((temp_text or "").strip())
        except ValueError:
            saw_invalid = True
            continue
        celsius = raw / 1000.0 if abs(raw) >= 1000 else raw
        # Android thermal sysfs frequently exposes disabled/sentinel values such
        # as -273000, -40000 and 0.  None of those is a usable device temperature.
        if not (1.0 <= celsius <= 150.0):
            saw_invalid = True
            continue
        candidates.append((score, round(celsius, 1), sensor_type))
    if candidates:
        candidates.sort(key=lambda item: (-item[0], item[2]))
        score = candidates[0][0]
        peers = [item[1] for item in candidates if item[0] == score][:8]
        # Median of semantically equivalent CPU/SoC sensors avoids selecting an
        # arbitrary hot peripheral while still tolerating multi-cluster devices.
        peers.sort()
        middle = len(peers) // 2
        value = peers[middle] if len(peers) % 2 else round((peers[middle - 1] + peers[middle]) / 2.0, 1)
        sensor_type = candidates[0][2]
        return _observation(
            "temperature",
            value={"celsius": value},
            unit="celsius",
            status="available",
            source=f"sysfs_thermal:{sensor_type}",
            observed_at=observed_at,
            reason_code="collected",
        )
    if saw_permission:
        return _failure("temperature", source="sysfs_thermal", observed_at=observed_at, reason_code="permission_denied")
    if saw_invalid:
        return _failure("temperature", source="sysfs_thermal", observed_at=observed_at, reason_code="invalid_sensor_value")
    return _failure("temperature", source="sysfs_thermal", observed_at=observed_at, reason_code="unsupported" if saw_zone else "not_present")


RESOURCE_PROVIDERS: tuple[ResourceProvider, ...] = (
    ResourceProvider("memory", "proc_meminfo", _memory, 200.0),
    ResourceProvider("storage", "statvfs", _storage, 250.0),
    ResourceProvider("cpu_usage", "proc_stat", _cpu_usage, 200.0),
    ResourceProvider("load_average", "platform_loadavg", _load_average, 100.0),
    ResourceProvider("uptime", "boot_clock", _uptime, 150.0),
    ResourceProvider("temperature", "sysfs_thermal", _temperature, 350.0),
)


def collect_resource_telemetry(storage_root: str | os.PathLike[str]) -> dict[str, Any]:
    """Collect one bounded multi-provider sample without throwing per-metric errors."""
    observed_at = _iso_now()
    root = Path(storage_root)
    observations: dict[str, dict[str, Any]] = {}
    for provider in RESOURCE_PROVIDERS:
        args = (root,) if provider.metric == "storage" else ()
        observations[provider.metric] = _run_provider(provider, observed_at, *args)
    payload: dict[str, Any] = {
        "timestamp": observed_at,
        "sampled_at": observed_at,
        "schema_version": RESOURCE_OBSERVATION_SCHEMA_VERSION,
        "resource_observations": observations,
        "error": None,
    }

    memory = observations["memory"]
    if memory.get("status") == "available" and isinstance(memory.get("value"), dict):
        value = memory["value"]
        payload.update({
            "memory_total_mb": value.get("total_mb"),
            "memory_free_mb": value.get("free_mb"),
            "memory_usage_mb": value.get("used_mb"),
            "memoryTotalMB": value.get("total_mb"),
            "memoryFreeMB": value.get("free_mb"),
        })
    storage = observations["storage"]
    if storage.get("status") == "available" and isinstance(storage.get("value"), dict):
        value = storage["value"]
        payload.update({
            "free_space_mb": value.get("free_mb"),
            "total_space_mb": value.get("total_mb"),
            "freeSpaceMB": value.get("free_mb"),
            "totalSpaceMB": value.get("total_mb"),
        })
    cpu = observations["cpu_usage"]
    if cpu.get("status") == "available" and isinstance(cpu.get("value"), dict):
        payload["cpu_usage_percent"] = cpu["value"].get("usage_percent")
    temperature = observations["temperature"]
    if temperature.get("status") == "available" and isinstance(temperature.get("value"), dict):
        value = temperature["value"].get("celsius")
        payload["cpu_temp_c"] = value
        payload["cpuTemp"] = value
    return payload
