"""Prepared, sanitized runtime-service evidence for Pocket Lab Lite devices.

This module deliberately owns *discovery semantics*, not execution.  It may be
used by background projection builders, never by request-path React/FastAPI
reads.  PM2 rows are reduced to bounded service facts; environment values,
commands and filesystem paths never leave this module.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

_MAX_SERVICES = 128
_MAX_STDOUT_BYTES = 256 * 1024
_CURRENT_SECONDS = 180
_SAFE_ID = re.compile(r"[^a-z0-9_.-]+")
_SECRETISH = re.compile(
    r"(?:token|password|passwd|secret|credential|api[_-]?key|private[_-]?key|"
    r"authorization|bearer\s+|nats://|https?://[^\s/@]+:[^\s/@]+@|"
    r"/data/data/|/storage/emulated/|/home/|/mnt/|/root/|~[/\\])",
    re.IGNORECASE,
)
_ALLOWED_CATEGORIES = {
    "api", "control", "worker", "messaging", "agent", "supervisor",
    "proxy", "application", "storage", "database", "security", "service",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 120, fallback: str = "") -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if not text or _SECRETISH.search(text):
        return fallback
    return text[:limit]


def _service_id(value: Any) -> str:
    text = _safe_text(value, 96).lower()
    return _SAFE_ID.sub("-", text).strip("-._")[:80]


def _category(env: dict[str, Any]) -> str:
    for key in ("POCKETLAB_SERVICE_CATEGORY", "POCKETLAB_COMPONENT_ROLE", "POCKETLAB_PROCESS_ROLE"):
        value = _safe_text(env.get(key), 32).lower().replace("-", "_")
        if value in _ALLOWED_CATEGORIES:
            return value
    return "service"


def _managed(env: dict[str, Any]) -> bool:
    # Environment *keys* are inspected only to identify Pocket Lab ownership.
    # Values are never returned, logged or copied into evidence.
    return any(str(key).startswith("POCKETLAB_") for key in env)


def _freshness(reported_at: Any, *, now_epoch: float | None = None) -> str:
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    text = _safe_text(reported_at, 64)
    if not text:
        return "missing"
    try:
        observed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = max(0.0, now_epoch - observed.astimezone(timezone.utc).timestamp())
    except (TypeError, ValueError):
        return "missing"
    return "current" if age <= _CURRENT_SECONDS else "stale"


def sanitize_runtime_service(
    item: dict[str, Any],
    *,
    reported_at: Any = None,
    source: str = "prepared_process_snapshot",
    now_epoch: float | None = None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    identifier = _service_id(item.get("service_id") or item.get("name") or item.get("id"))
    if not identifier:
        return None
    label = _safe_text(item.get("label") or item.get("name"), 96, identifier.replace("-", " ").title())
    state = _safe_text(item.get("state") or item.get("status"), 32, "unknown").lower().replace(" ", "_")
    manager = _safe_text(item.get("manager"), 32, "process_manager").lower()
    category = _safe_text(item.get("category"), 32, "service").lower().replace("-", "_")
    if category not in _ALLOWED_CATEGORIES:
        category = "service"
    observed = _safe_text(item.get("reported_at") or reported_at, 64) or None
    return {
        "service_id": identifier,
        "label": label,
        "category": category,
        "manager": manager,
        "state": state,
        "reported_at": observed,
        "freshness": _freshness(observed, now_epoch=now_epoch),
        "restart_supported": bool(item.get("restart_supported") is True),
        "restart_reason": _safe_text(item.get("restart_reason"), 80, "backend_guard_required"),
        "source": _safe_text(item.get("source"), 80, source),
        "schema_version": 1,
        "sanitized": True,
    }


def runtime_services_from_snapshot(snapshot: Any, *, now_epoch: float | None = None) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    reported_at = snapshot.get("updated_at") or snapshot.get("observed_at") or snapshot.get("checked_at")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in (snapshot.get("items") if isinstance(snapshot.get("items"), list) else [])[:_MAX_SERVICES]:
        service = sanitize_runtime_service(raw, reported_at=reported_at, now_epoch=now_epoch)
        if not service or service["service_id"] in seen:
            continue
        seen.add(service["service_id"])
        output.append(service)
    return output


def collect_process_state() -> dict[str, Any]:
    """Background-only dynamic PM2 service snapshot with no topology assumptions."""
    started = time.monotonic()
    reported_at = _now_iso()
    pm2 = shutil.which("pm2")
    if not pm2:
        return {
            "status": "unknown",
            "summary": "Process manager status is not available.",
            "items": [],
            "item_count": 0,
            "manager": "pm2",
            "manager_available": False,
            "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
            "observed_at": reported_at,
            "sanitized": True,
        }
    try:
        result = subprocess.run(
            [pm2, "jlist"],
            check=False,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        stdout = result.stdout or ""
        if len(stdout.encode("utf-8", errors="ignore")) > _MAX_STDOUT_BYTES:
            raise ValueError("process_snapshot_too_large")
        rows = json.loads(stdout) if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
        rows = []

    items: list[dict[str, Any]] = []
    managed_states: list[str] = []
    all_states: list[str] = []
    for raw in rows[:_MAX_SERVICES] if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        env = raw.get("pm2_env") if isinstance(raw.get("pm2_env"), dict) else {}
        identifier = _service_id(raw.get("name"))
        if not identifier:
            continue
        status = _safe_text(env.get("status"), 24, "unknown").lower()
        managed = _managed(env)
        all_states.append(status)
        if managed:
            managed_states.append(status)
        items.append({
            "service_id": identifier,
            "name": _safe_text(raw.get("name"), 96, identifier),
            "label": _safe_text(raw.get("name"), 96, identifier.replace("-", " ").title()),
            "category": _category(env),
            "manager": "pm2",
            "state": status,
            "status": status,
            "running": status == "online",
            "managed": managed,
            "reported_at": reported_at,
            "freshness": "current",
            "restart_supported": False,
            "restart_reason": "backend_guard_required",
            "source": "pm2_prepared_projection",
            "schema_version": 1,
            "sanitized": True,
        })

    evaluated_states = managed_states or all_states
    if not evaluated_states:
        overall = "unknown"
    elif all(state == "online" for state in evaluated_states):
        overall = "healthy"
    else:
        overall = "degraded"
    return {
        "status": overall,
        "summary": "Observed runtime services are online." if overall == "healthy" else "One or more observed runtime services need attention." if overall == "degraded" else "No runtime services are currently reported.",
        "items": items,
        "item_count": len(items),
        "manager": "pm2",
        "manager_available": True,
        "observed_at": reported_at,
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def process_source_revision(snapshot: dict[str, Any] | None = None) -> int:
    payload = snapshot if isinstance(snapshot, dict) else {}
    material = [
        {
            "service_id": item.get("service_id") or item.get("name"),
            "category": item.get("category"),
            "state": item.get("state") or item.get("status"),
            "managed": bool(item.get("managed")),
        }
        for item in (payload.get("items") if isinstance(payload.get("items"), list) else [])[:_MAX_SERVICES]
        if isinstance(item, dict)
    ]
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return max(1, int.from_bytes(hashlib.sha256(encoded.encode("utf-8")).digest()[:8], "big") & ((1 << 63) - 1))


def install_phase3b_runtime_service_extension() -> None:
    """Replace fixed-topology Phase3B process collection before scheduler start."""
    from . import lite_phase3b_projections as phase3b

    if getattr(phase3b, "_pocketlab_dynamic_runtime_services_v1", False):
        return

    phase3b.collect_process_state = collect_process_state

    def source_revision() -> int:
        return process_source_revision(phase3b.snapshot("system.processes") or {})

    phase3b.process_source_revision = source_revision
    setattr(phase3b, "_pocketlab_dynamic_runtime_services_v1", True)
