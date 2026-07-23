from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

PROFILE_SCHEMA_VERSION = 1
DEFAULT_COMMAND_TIMEOUT_SECONDS = 2.0
MAX_COMMAND_OUTPUT_BYTES = 1024
MAX_PROFILE_TEXT = 160

_PROPERTY_COMMANDS: dict[str, tuple[str, ...]] = {
    "os_version": ("getprop", "ro.build.version.release"),
    "android_api_level": ("getprop", "ro.build.version.sdk"),
    "security_patch": ("getprop", "ro.build.version.security_patch"),
    "manufacturer": ("getprop", "ro.product.manufacturer"),
    "technical_model": ("getprop", "ro.product.model"),
    "device_codename": ("getprop", "ro.product.device"),
    "android_abi": ("getprop", "ro.product.cpu.abi"),
}
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SECURITY_PATCH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOAD_RE = re.compile(
    r"load averages?:\s*([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_public_text(value: Any, *, limit: int = MAX_PROFILE_TEXT) -> str:
    text = str(value or "").replace("\ufffd", " ")
    text = _CONTROL_RE.sub(" ", text)
    text = " ".join(text.strip().split())
    return text[: max(1, int(limit))]


def run_bounded_command(
    command: Sequence[str],
    *,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    max_output_bytes: int = MAX_COMMAND_OUTPUT_BYTES,
) -> dict[str, Any]:
    safe_command = tuple(str(part) for part in command)
    try:
        result = subprocess.run(
            safe_command,
            check=False,
            capture_output=True,
            timeout=max(0.25, min(float(timeout_seconds), 5.0)),
        )
    except FileNotFoundError:
        return {"status": "unavailable", "value": "", "failure_code": "command_unavailable"}
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "value": "", "failure_code": "command_timeout"}
    except OSError:
        return {"status": "unavailable", "value": "", "failure_code": "command_failed"}

    stdout = bytes(result.stdout or b"")[: max(1, int(max_output_bytes))]
    value = sanitize_public_text(stdout.decode("utf-8", errors="replace"))
    if result.returncode != 0:
        return {"status": "unavailable", "value": "", "failure_code": "command_failed"}
    if not value:
        return {"status": "empty", "value": "", "failure_code": "empty_value"}
    return {"status": "available", "value": value, "failure_code": ""}


def detect_runtime_type(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    prefix = str(values.get("PREFIX") or "")
    if values.get("TERMUX_VERSION") or "com.termux" in prefix or prefix.endswith("/com.termux/files/usr"):
        return "termux"
    if values.get("container") or values.get("CONTAINER"):
        return "container"
    if values.get("PROOT_DISTRO") or values.get("PROOT_LOADER"):
        return "proot"
    if platform.system().lower() == "windows":
        return "windows_agent"
    if platform.system().lower() == "linux":
        return "native_linux"
    return "unknown"


def _duration_seconds(duration_text: str) -> int | None:
    text = sanitize_public_text(duration_text, limit=120).lower()
    if not text:
        return None
    total = 0
    day_match = re.search(r"(\d+)\s+days?", text)
    if day_match:
        total += int(day_match.group(1)) * 86400
    hour_match = re.search(r"(\d+)\s+(?:hrs?|hours?)", text)
    if hour_match:
        total += int(hour_match.group(1)) * 3600
    minute_match = re.search(r"(\d+)\s+(?:mins?|minutes?)", text)
    if minute_match:
        total += int(minute_match.group(1)) * 60

    colon_match = re.search(r"(?:^|,\s*)(\d+):(\d{1,2})(?=\s*$|,)", text)
    if colon_match:
        total += int(colon_match.group(1)) * 3600 + int(colon_match.group(2)) * 60

    if total <= 0:
        return None
    return total


def parse_uptime_output(value: str) -> dict[str, Any]:
    text = sanitize_public_text(value, limit=512)
    match = _LOAD_RE.search(text)
    if not match:
        return {"uptime_status": "unavailable", "failure_code": "uptime_parse_failed"}
    prefix = text[: match.start()].rstrip(" ,")
    up_match = re.search(r"\bup\s+(.+)$", prefix, re.IGNORECASE)
    if not up_match:
        return {"uptime_status": "unavailable", "failure_code": "uptime_parse_failed"}
    seconds = _duration_seconds(up_match.group(1))
    if seconds is None:
        return {"uptime_status": "unavailable", "failure_code": "uptime_parse_failed"}
    try:
        loads = [round(float(match.group(index)), 3) for index in (1, 2, 3)]
    except (TypeError, ValueError):
        return {"uptime_status": "unavailable", "failure_code": "load_parse_failed"}
    return {
        "uptime_status": "available",
        "uptime_seconds": seconds,
        "load_average_1m": loads[0],
        "load_average_5m": loads[1],
        "load_average_15m": loads[2],
        "failure_code": "",
    }


def _bounded_api_level(value: str) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 1 <= parsed <= 999 else None


def _profile_fingerprint(profile: Mapping[str, Any]) -> str:
    material = {
        key: profile.get(key)
        for key in (
            "schema_version",
            "os_family",
            "os_name",
            "os_version",
            "android_api_level",
            "security_patch",
            "manufacturer",
            "technical_model",
            "device_codename",
            "architecture",
            "android_abi",
            "kernel",
            "runtime_type",
            "termux_version",
            "python_version",
            "agent_version",
        )
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _termux_version(
    env: Mapping[str, str],
    command_runner: Callable[[Sequence[str]], Mapping[str, Any]],
) -> str:
    configured = sanitize_public_text(env.get("TERMUX_VERSION"), limit=80)
    if configured:
        return configured
    result = dict(command_runner(("termux-info",)))
    if result.get("status") != "available":
        return ""
    text = sanitize_public_text(result.get("value"), limit=1024)
    match = re.search(r"(?:TERMUX_VERSION|Termux version)\s*(?:=|:)\s*([^\s,;]+)", text, re.IGNORECASE)
    return sanitize_public_text(match.group(1), limit=80) if match else ""


def collect_system_profile(
    *,
    agent_version: str,
    command_runner: Callable[[Sequence[str]], Mapping[str, Any]] = run_bounded_command,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ or os.environ
    runtime_type = detect_runtime_type(env)
    values: dict[str, str] = {}
    unavailable: list[str] = []
    android_runtime = runtime_type == "termux" or bool(env.get("ANDROID_ROOT") or env.get("ANDROID_DATA"))
    if android_runtime:
        for field, command in _PROPERTY_COMMANDS.items():
            result = dict(command_runner(command))
            values[field] = sanitize_public_text(result.get("value"))
            if result.get("status") != "available":
                unavailable.append(field)

    for field, command in {
        "architecture": ("uname", "-m"),
        "kernel": ("uname", "-r"),
    }.items():
        result = dict(command_runner(command))
        values[field] = sanitize_public_text(result.get("value"))
        if result.get("status") != "available":
            unavailable.append(field)

    android = android_runtime or any(values.get(key) for key in _PROPERTY_COMMANDS)
    security_patch = values.get("security_patch", "")
    if security_patch and not _SECURITY_PATCH_RE.fullmatch(security_patch):
        security_patch = ""
        unavailable.append("security_patch")

    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "os_family": "android" if android else sanitize_public_text(platform.system().lower(), limit=32) or "unknown",
        "os_name": "Android" if android else sanitize_public_text(platform.system(), limit=64) or "Unknown",
        "os_version": values.get("os_version", "") if android else sanitize_public_text(platform.release()),
        "android_api_level": _bounded_api_level(values.get("android_api_level", "")) if android else None,
        "security_patch": security_patch if android else "",
        "manufacturer": values.get("manufacturer", ""),
        "technical_model": values.get("technical_model", ""),
        "device_codename": values.get("device_codename", ""),
        "architecture": values.get("architecture", "") or sanitize_public_text(platform.machine()),
        "android_abi": values.get("android_abi", ""),
        "kernel": values.get("kernel", "") or sanitize_public_text(platform.release()),
        "runtime_type": runtime_type,
        "termux_version": _termux_version(env, command_runner) if runtime_type == "termux" else "",
        "python_version": sanitize_public_text(platform.python_version(), limit=40),
        "agent_version": sanitize_public_text(agent_version, limit=80),
        "collection_status": "current" if not unavailable else "partial",
        "unavailable_fields": sorted(set(unavailable))[:16],
        "collected_at": now_iso(),
    }
    profile["profile_fingerprint"] = _profile_fingerprint(profile)
    return profile


def collect_system_health(
    *,
    command_runner: Callable[[Sequence[str]], Mapping[str, Any]] = run_bounded_command,
) -> dict[str, Any]:
    result = dict(command_runner(("uptime",)))
    collected_at = now_iso()
    if result.get("status") != "available":
        return {
            "uptime_status": "unavailable",
            "failure_code": sanitize_public_text(result.get("failure_code"), limit=48) or "uptime_unavailable",
            "collected_at": collected_at,
        }
    parsed = parse_uptime_output(str(result.get("value") or ""))
    load_1m = parsed.get("load_average_1m")
    cpu_count = max(1, int(os.cpu_count() or 1))
    if isinstance(load_1m, (int, float)):
        parsed["load_status"] = "normal" if load_1m <= cpu_count else "elevated" if load_1m <= cpu_count * 2 else "high"
    else:
        parsed["load_status"] = "unavailable"
    return {**parsed, "collected_at": collected_at}
