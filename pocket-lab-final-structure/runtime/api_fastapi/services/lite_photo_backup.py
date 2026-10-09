from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shlex
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from cryptography.fernet import Fernet, InvalidToken

from .. import deps
from . import fleet_registry, lite_app_runtime, lite_catalog, lite_photo_backup_destinations
from .nats_bus import BUS

PHOTO_BACKUP_START_SUBJECT = "pocketlab.commands.lite.media_backup.start"
PHOTO_BACKUP_CANCEL_SUBJECT = "pocketlab.commands.lite.media_backup.cancel"
PHOTO_BACKUP_REPAIR_SUBJECT = "pocketlab.commands.lite.media_backup.repair"
NODE_START_COMMAND = "media.backup.photoprism.start"
NODE_CANCEL_COMMAND = "media.backup.photoprism.cancel"
NODE_REPAIR_COMMAND = "media.backup.tools.repair"
SUPPORTED_COLLECTIONS = ("camera", "pictures", "videos")
TERMINAL_STATES = {
    "completed",
    "partial_storage_limit",
    "cancelled",
    "failed",
    "interrupted",
    "source_offline",
    "destination_unavailable",
}
ACTIVE_STATES = {"queued", "planning", "waiting_for_credentials", "starting", "transferring", "cancelling"}
HARD_RESERVE_FRACTION = 0.10
PLANNING_RESERVE_FRACTION = 0.15
PLANNING_RESERVE_MIN_BYTES = 2 * 1024 * 1024 * 1024
CREDENTIAL_TTL_SECONDS = max(
    3600,
    min(
        7200,
        int(os.environ.get("POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS", "5400")),
    ),
)
PHOTOPRISM_COMMAND_TIMEOUT_SECONDS = max(
    30,
    min(
        120,
        int(os.environ.get("POCKETLAB_PHOTOPRISM_COMMAND_TIMEOUT_SECONDS", "60")),
    ),
)
STATE_SCHEMA_VERSION = 1
_PROVIDER_ID = "photoprism_webdav"
_LOCK = threading.RLock()
_PREFLIGHT_LOCK = threading.RLock()
_PREFLIGHT_CACHE: dict[str, Any] = {}
_PREFLIGHT_TTL_SECONDS = 20

_SECRET_KEYS = {"password", "token", "secret", "credential", "authorization", "api_key"}
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])"
)
_PHOTOPRISM_TABLE_TRANSLATION = str.maketrans(
    {
        "│": "|",
        "┃": "|",
        "╎": "|",
        "╏": "|",
    }
)


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _epoch() -> float:
    return time.time()


def _state_path() -> Path:
    return deps.settings().state_dir / "lite_photo_backup.json"


def _credential_dir() -> Path:
    return (
        deps.settings().state_dir
        / "ephemeral"
        / "photo-backup-credentials"
    )


def _credential_key_path() -> Path:
    return (
        deps.settings().state_dir
        / "runtime-secrets"
        / "photo-backup-credential.key"
    )


def _credential_cipher() -> Fernet:
    path = _credential_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass

    try:
        key = path.read_bytes().strip()
    except FileNotFoundError:
        candidate = Fernet.generate_key()
        try:
            fd = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                os.write(fd, candidate + b"\n")
                os.fsync(fd)
            finally:
                os.close(fd)
            key = candidate
        except FileExistsError:
            key = path.read_bytes().strip()

    try:
        path.chmod(0o600)
    except OSError:
        pass
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "photo_backup_credential_store_unavailable"
        ) from exc


def _write_private_bytes(
    path: Path,
    payload: bytes,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    temp = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    )
    with open(temp, "wb") as handle:
        os.chmod(temp, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _evidence_path() -> Path:
    return deps.settings().state_dir / "lite_photo_backup_evidence.json"


def _originals_path() -> Path:
    return (
        Path.home()
        / ".pocket_lab"
        / "lite"
        / "apps"
        / "photoprism"
        / "originals"
    )


def _env_file() -> Path:
    return (
        Path.home()
        / ".pocket_lab"
        / "lite"
        / "apps"
        / "photoprism"
        / "config"
        / "photoprism.env"
    )


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, payload: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        temp.chmod(mode)
    except OSError:
        pass
    temp.replace(path)
    try:
        path.chmod(mode)
    except OSError:
        pass


def _state() -> dict[str, Any]:
    payload = _read_json(_state_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema_version", STATE_SCHEMA_VERSION)
    payload.setdefault("jobs", {})
    payload.setdefault("latest_by_node", {})
    payload.setdefault("placements", {})
    payload.setdefault("updated_at", None)
    if not isinstance(payload["jobs"], dict):
        payload["jobs"] = {}
    if not isinstance(payload["latest_by_node"], dict):
        payload["latest_by_node"] = {}
    if not isinstance(payload["placements"], dict):
        payload["placements"] = {}
    return payload


def _save_state(payload: dict[str, Any]) -> None:
    payload["schema_version"] = STATE_SCHEMA_VERSION
    payload["updated_at"] = _now()
    _write_json(_state_path(), payload)


def _safe_text(
    value: Any,
    fallback: str = "Available",
    limit: int = 220,
) -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_KEYS):
        return fallback
    if text.startswith("/") or text.startswith("~"):
        return fallback
    return text[:limit]


def _safe_node_id(value: Any) -> str:
    node_id = fleet_registry.normalize_node_id(str(value or ""))
    if not node_id or node_id == "unknown-node":
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_device",
                "summary": "Choose an enrolled device.",
            },
        )
    return node_id


def _collections(value: Any) -> list[str]:
    supplied = value if isinstance(value, list) else list(SUPPORTED_COLLECTIONS)
    normalized: list[str] = []
    for item in supplied:
        collection = (
            str(item or "")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if collection not in SUPPORTED_COLLECTIONS:
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "invalid_collection",
                    "summary": "Choose Camera, Pictures, or Videos.",
                },
            )
        if collection not in normalized:
            normalized.append(collection)
    return normalized or list(SUPPORTED_COLLECTIONS)


def _public_job(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(job, dict):
        return None
    allowed = (
        "backup_id",
        "node_id",
        "node_label",
        "provider",
        "status",
        "summary",
        "collections",
        "items_total",
        "items_transferred",
        "items_skipped",
        "items_remaining",
        "conflicts",
        "oversized_items",
        "bytes_total",
        "bytes_total_planned",
        "bytes_total_required",
        "bytes_transferred",
        "bytes_remaining",
        "photo_processing_state",
        "retry_count",
        "destination_id",
        "destination_contract_version",
        "reserve_policy",
        "server_storage_before",
        "server_storage_after",
        "partial",
        "started_at",
        "updated_at",
        "completed_at",
        "last_success_at",
        "retryable",
        "reason_code",
        "credential_expires_at",
        "credential_revoke_status",
        "destination_ready",
        "rclone_available",
        "photo_storage_access",
        "storage",
        "progress",
        "sanitized",
    )
    result = {
        key: job.get(key)
        for key in allowed
        if key in job
    }
    result["credential_revoke_status"] = str(job.get("credential_revoke_status_internal") or "none") if str(job.get("credential_revoke_status_internal") or "") in {"pending", "revoked"} else "none"
    result["sanitized"] = True
    return result


def _find_job(
    backup_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _state()
    job = payload["jobs"].get(str(backup_id or ""))
    if not isinstance(job, dict):
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_found",
                "summary": "Photo backup was not found.",
            },
        )
    return payload, job


def _agent(node_id: str) -> dict[str, Any]:
    agent = fleet_registry.get_agent(node_id)
    if not isinstance(agent, dict):
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_found",
                "summary": "Device was not found.",
            },
        )
    return agent


def _is_protected_server(agent: dict[str, Any]) -> bool:
    role = (
        str(agent.get("role") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    return bool(
        agent.get("is_current")
        or agent.get("isCurrent")
        or role
        in {
            "server",
            "server_host",
            "control_plane",
            "control_plane_host",
        }
    )


def _agent_online(agent: dict[str, Any]) -> bool:
    return (
        str(agent.get("connection") or "").lower() == "online"
        or str(agent.get("status") or "").lower()
        in {"active", "healthy", "online", "ready"}
    )


def _photo_capability(agent: dict[str, Any]) -> dict[str, Any]:
    raw = (
        agent.get("photo_backup")
        if isinstance(agent.get("photo_backup"), dict)
        else {}
    )
    caps = {
        str(item)
        for item in (
            agent.get("advertised_capabilities")
            or agent.get("capabilities")
            or []
        )
        if item
    }
    rclone_available = (
        bool(raw.get("rclone_available"))
        or "rclone_available" in caps
    )
    storage_access = (
        bool(raw.get("photo_storage_access"))
        or "photo_storage_access" in caps
    )
    collections = (
        [
            item
            for item in raw.get("collections", [])
            if item in SUPPORTED_COLLECTIONS
        ][:3]
        if isinstance(raw.get("collections"), list)
        else []
    )
    return {
        "rclone_available": rclone_available,
        "photo_storage_access": storage_access,
        "media_backup_source": (
            storage_access or "media_backup_source" in caps
        ),
        "photoprism_webdav_upload": (
            rclone_available
            and (
                storage_access
                or "photoprism_webdav_upload" in caps
            )
        ),
        "rclone_version": _safe_text(
            raw.get("rclone_version"),
            "Unavailable",
            80,
        ),
        "collections": collections,
        "repair": _safe_repair_projection(raw.get("repair")),
    }


def _safe_repair_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "unknown", "reason_code": None, "sanitized": True}
    allowed = {"installing", "verifying", "completed", "failed", "already_installed",
               "interrupted", "unsupported_platform", "unavailable", "not_requested"}
    status = str(value.get("status") or "")
    reason = str(value.get("reason_code") or "")
    return {
        "status": status if status in allowed else "unknown",
        "reason_code": reason if reason in P0_REASONS or reason in {
            "rclone_repair_interrupted", "rclone_repair_in_progress",
            "rclone_unsupported_platform", "rclone_repair_state_unavailable"} else None,
        "checked_at": _safe_text(value.get("checked_at"), "", 32),
        "sanitized": True,
    }


def _secure_origin(request: Request | None = None) -> str | None:
    access = lite_catalog.access_status(request)
    origin = str(
        access.get("secure_origin") or ""
    ).strip().rstrip("/")
    return (
        origin
        if origin.startswith("https://")
        else None
    )


def _destination_identity(root: Path, stat: os.statvfs_result) -> str | None:
    """Bind the current originals volume to a private, server-owned identity.

    No raw path or device number is surfaced. An existing identity is NEVER
    rewritten after a mismatch; explicit operator recovery is required.
    """
    try:
        real = root.resolve(strict=True)
        if real.is_symlink() or root.is_symlink():
            return "destination_identity_mismatch"
        disk = os.stat(real)
        fingerprint = hashlib.sha256(
            f"photoprism-originals:v1:{real}:{disk.st_dev}:{stat.f_fsid}".encode()
        ).hexdigest()
        path = deps.settings().state_dir / "lite_photo_backup_destination_identity.json"
        with _LOCK:
            record = _read_json(path, {})
            if record:
                if (not isinstance(record, dict)
                    or record.get("schema_version") != 1
                    or record.get("destination_id") != lite_photo_backup_destinations.CURRENT_DESTINATION_ID
                    or not secrets.compare_digest(str(record.get("fingerprint") or ""), fingerprint)):
                    return "destination_identity_mismatch"
            else:
                if not root.is_dir() or not os.access(root, os.R_OK | os.W_OK | os.X_OK):
                    return "destination_storage_unavailable"
                _write_json(path, {
                    "schema_version": 1,
                    "destination_id": lite_photo_backup_destinations.CURRENT_DESTINATION_ID,
                    "fingerprint": fingerprint,
                    "enrolled_at": _now(),
                })
        return None
    except (OSError, ValueError, TypeError):
        return "destination_storage_unavailable"


def _current_volume_fingerprint() -> str:
    """Read only the existing private anchor; never expose it to a device."""
    record = _read_json(
        deps.settings().state_dir / "lite_photo_backup_destination_identity.json", {}
    )
    value = str(record.get("fingerprint") or "") if isinstance(record, dict) else ""
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("destination_identity_unavailable")
    return value


def _ensure_placement(backup_id: str, node_id: str) -> dict[str, Any]:
    """Persist immutable destination placement before credential issuance."""
    with _LOCK:
        state, job = _find_job(backup_id)
        if str(job.get("node_id") or "") != node_id:
            raise ValueError("placement_identity_mismatch")
        target = lite_photo_backup_destinations.placement(
            str(job.get("destination_id") or lite_photo_backup_destinations.CURRENT_DESTINATION_ID),
            node_id, backup_id, _current_volume_fingerprint(),
        )
        previous = state["placements"].get(backup_id)
        if previous is not None and previous != target:
            raise ValueError("destination_identity_mismatch")
        if previous is None:
            state["placements"][backup_id] = target
            _save_state(state)
        return target


def _verified_placement(backup_id: str, node_id: str) -> dict[str, Any]:
    state, job = _find_job(backup_id)
    if str(job.get("node_id") or "") != node_id:
        raise ValueError("placement_identity_mismatch")
    entry = state.get("placements", {}).get(backup_id)
    if not isinstance(entry, dict) or entry.get("schema_version") != lite_photo_backup_destinations.SCHEMA_VERSION:
        raise ValueError("destination_placement_missing")
    target = lite_photo_backup_destinations.placement(
        str(job.get("destination_id") or lite_photo_backup_destinations.CURRENT_DESTINATION_ID),
        node_id, backup_id, _current_volume_fingerprint(),
    )
    if entry != target:
        raise ValueError("destination_identity_mismatch")
    return target


def server_capacity() -> dict[str, Any]:
    root = _originals_path()
    if not root.is_dir():
        return {
            "status": "unavailable",
            "hard_reserve_bytes": 0,
            "planning_reserve_bytes": 0,
            "safe_upload_budget_bytes": 0,
            "hard_upload_budget_bytes": 0,
            "hard_reserve_fraction": HARD_RESERVE_FRACTION,
            "planning_reserve_fraction": PLANNING_RESERVE_FRACTION,
            "planning_reserve_min_bytes": PLANNING_RESERVE_MIN_BYTES,
            "sanitized": True,
        }
    if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        return {"status": "unavailable", "read_only": True,
                "hard_upload_budget_bytes": 0, "safe_upload_budget_bytes": 0,
                "sanitized": True}
    try:
        stat = os.statvfs(root)
        total = int(stat.f_blocks * stat.f_frsize)
        free = int(stat.f_bavail * stat.f_frsize)
    except OSError:
        return {
            "status": "unavailable",
            "hard_reserve_bytes": 0,
            "planning_reserve_bytes": 0,
            "safe_upload_budget_bytes": 0,
            "hard_upload_budget_bytes": 0,
            "sanitized": True,
        }
    identity_issue = _destination_identity(root, stat)
    if identity_issue:
        return {"status": "unavailable", "reason_code": identity_issue,
                "identity_mismatch": identity_issue == "destination_identity_mismatch",
                "hard_upload_budget_bytes": 0, "safe_upload_budget_bytes": 0,
                "sanitized": True}
    if total <= 0 or free < 0 or free > total or total > (1 << 63) - 1:
        return {"status": "unavailable", "hard_upload_budget_bytes": 0,
                "safe_upload_budget_bytes": 0, "sanitized": True}
    hard = int(total * HARD_RESERVE_FRACTION)
    planning = max(
        int(total * PLANNING_RESERVE_FRACTION),
        hard,
        PLANNING_RESERVE_MIN_BYTES,
    )
    return {
        "status": "ready" if free > hard else "storage_full",
        "total_bytes": total,
        "free_bytes": free,
        "hard_reserve_bytes": hard,
        "planning_reserve_bytes": planning,
        "safe_upload_budget_bytes": max(0, free - planning),
        "hard_upload_budget_bytes": max(0, free - hard),
        "hard_reserve_fraction": HARD_RESERVE_FRACTION,
        "planning_reserve_fraction": PLANNING_RESERVE_FRACTION,
        "planning_reserve_min_bytes": PLANNING_RESERVE_MIN_BYTES,
        "sanitized": True,
    }


# Stable, public reason codes. Do not emit backend paths or upstream response bodies.
P0_REASONS = frozenset({
    "source_offline", "source_agent_unavailable", "source_capabilities_stale",
    "rclone_unavailable", "rclone_install_failed", "rclone_install_timeout",
    "rclone_verification_failed", "photo_storage_access_missing",
    "photoprism_not_running", "photoprism_unreachable", "secure_route_unavailable",
    "webdav_probe_failed", "webdav_auth_failed", "destination_unavailable",
    "destination_mount_missing", "destination_identity_mismatch",
    "destination_read_only", "destination_storage_unavailable",
    "storage_below_planning_reserve", "storage_below_hard_reserve",
    "storage_reservation_conflict", "insufficient_space_for_selected_media",
    "network_interrupted", "credential_expired", "credential_identity_mismatch", "credential_revocation_pending",
    "agent_command_undeliverable", "worker_unavailable", "cancelled",
    "unknown_internal_error", "rclone_repair_interrupted",
    "rclone_repair_in_progress", "rclone_unsupported_platform",
    "rclone_repair_state_unavailable",
})
_P0_REMEDIATION = {
    "source_offline": "device", "source_agent_unavailable": "device",
    "source_capabilities_stale": "device", "rclone_unavailable": "repair",
    "photo_storage_access_missing": "permissions",
    "photoprism_not_running": "app", "photoprism_unreachable": "app",
    "secure_route_unavailable": "remote_access",
    "webdav_probe_failed": "destination", "webdav_auth_failed": "credentials",
    "destination_mount_missing": "storage", "destination_read_only": "storage",
    "destination_storage_unavailable": "storage",
    "storage_below_planning_reserve": "space",
    "storage_below_hard_reserve": "space", "storage_reservation_conflict": "space",
}


def _source_fresh(agent: dict[str, Any]) -> bool:
    """Respect the fleet registry's authoritative heartbeat epoch.

    Timestamp-free legacy snapshots are *unknown*, never assumed fresh.
    """
    candidate = (agent.get("last_seen_epoch")
                 or agent.get("last_heartbeat_at")
                 or agent.get("last_seen")
                 or agent.get("last_heartbeat")
                 or agent.get("last_seen_at")
                 or agent.get("heartbeat_at"))
    if not candidate:
        return False
    try:
        if isinstance(candidate, (int, float)) or str(candidate).replace(".", "", 1).isdigit():
            epoch = float(candidate)
            if epoch > 10**12:
                epoch /= 1000
        else:
            epoch = datetime.fromisoformat(str(candidate).replace("Z", "+00:00")).timestamp()
        age = _epoch() - epoch
        return -15 <= age <= 180
    except (ValueError, TypeError, OverflowError):
        return False


def _webdav_route_probe(origin: str | None, *, force: bool = False) -> str | None:
    """Bounded unauthenticated route probe; never claims authentication worked.

    A 401/403 from the fixed WebDAV route proves it is responding, not that
    a temporary backup credential is valid. Auth is verified separately when
    the worker creates its one-use app password.
    """
    if not origin:
        return "secure_route_unavailable"
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        return "secure_route_unavailable"
    with _PREFLIGHT_LOCK:
        record = _PREFLIGHT_CACHE.get(origin)
        if not force and record and _epoch() - record["epoch"] < _PREFLIGHT_TTL_SECONDS:
            return record["reason"]
    reason = "webdav_probe_failed"
    url = origin + "/apps/photoprism/originals/"
    try:
        request = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(request, timeout=3) as response:
            code = int(getattr(response, "status", 0) or 0)
            if code in (200, 204, 207, 401, 403):
                reason = None
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            reason = None
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    with _PREFLIGHT_LOCK:
        if len(_PREFLIGHT_CACHE) > 12:
            _PREFLIGHT_CACHE.clear()
        _PREFLIGHT_CACHE[origin] = {"epoch": _epoch(), "reason": reason}
    return reason


def _capacity_diagnostic(capacity: dict[str, Any]) -> str | None:
    if capacity.get("identity_mismatch"):
        return "destination_identity_mismatch"
    if capacity.get("read_only"):
        return "destination_read_only"
    if capacity.get("status") == "unavailable":
        return str(capacity.get("reason_code") or "destination_storage_unavailable")
    if capacity.get("mount_missing"):
        return "destination_mount_missing"
    if capacity.get("identity_mismatch"):
        return "destination_identity_mismatch"
    if int(capacity.get("hard_upload_budget_bytes") or 0) <= 0:
        return "storage_below_hard_reserve"
    if int(capacity.get("safe_upload_budget_bytes") or 0) <= 0:
        return "storage_below_planning_reserve"
    return None


def readiness(
    node_id: str,
    request: Request | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    agent = _agent(node_id)
    if _is_protected_server(agent):
        return {
            "status": "not_eligible",
            "ready": False,
            "node_id": node_id,
            "summary": "Choose an enrolled secondary device.",
            "sanitized": True,
        }
    cap = _photo_capability(agent)
    runtime = lite_app_runtime.probe_app_runtime("photoprism", force=force)
    origin = _secure_origin(request)
    capacity = server_capacity()
    blockers: list[str] = []
    if not _agent_online(agent):
        blockers.append("source_offline")
    elif not _source_fresh(agent):
        blockers.append("source_capabilities_stale")
    if not cap["rclone_available"]:
        blockers.append("rclone_unavailable")
    if cap["repair"]["status"] in {"installing", "verifying"}:
        blockers.append("rclone_repair_in_progress")
    if not cap["photo_storage_access"]:
        blockers.append("photo_storage_access_missing")
    if not runtime.get("running"):
        blockers.append("photoprism_not_running")
    elif not runtime.get("reachable"):
        blockers.append("photoprism_unreachable")
    route_reason = _webdav_route_probe(origin, force=force) if runtime.get("running") and runtime.get("reachable") else ("secure_route_unavailable" if not origin else None)
    if route_reason:
        blockers.append(route_reason)
    capacity_reason = _capacity_diagnostic(capacity)
    if capacity_reason:
        blockers.append(capacity_reason)

    if "rclone_repair_in_progress" in blockers:
        summary = "Photo backup tools repair is in progress."
    elif "photo_storage_access_missing" in blockers:
        summary = "Allow photo access on this device."
    elif "rclone_unavailable" in blockers:
        summary = "Photo backup tools are not ready on this device."
    elif "source_offline" in blockers:
        summary = "This device is offline."
    elif "source_capabilities_stale" in blockers:
        summary = "Waiting for a fresh device heartbeat."
    elif "secure_route_unavailable" in blockers:
        summary = "Remote access not ready."
    elif "webdav_probe_failed" in blockers:
        summary = "PhotoPrism photo backup connection is not responding."
    elif ("photoprism_not_running" in blockers or "photoprism_unreachable" in blockers):
        summary = "PhotoPrism is not ready for photo backup."
    elif ("storage_below_hard_reserve" in blockers or "storage_below_planning_reserve" in blockers):
        summary = (
            "Not enough protected space is available "
            "on the Server Phone."
        )
    else:
        summary = "Ready to back up photos."

    checked_at = _now()
    destination_operational = bool(runtime.get("running") and runtime.get("reachable") and origin and not route_reason)
    source_ready = bool(_agent_online(agent) and _source_fresh(agent) and cap["rclone_available"] and cap["photo_storage_access"])
    return {
        "schema_version": 3,
        "status": "ready" if not blockers else "not_ready",
        "ready": not blockers,
        "source_ready": source_ready,
        "destination_operational": destination_operational,
        "safe_capacity_available": int(capacity.get("safe_upload_budget_bytes") or 0) > 0,
        "backup_admissible": not blockers,
        "checked_at": checked_at,
        "reason_code": blockers[0] if blockers else None,
        "diagnostics": [
            {"reason_code": code, "status": "blocked", "checked_at": checked_at,
             "remediation_category": _P0_REMEDIATION.get(code, "review"), "sanitized": True}
            for code in blockers
        ],
        "webdav_route_responding": bool(origin and not route_reason and destination_operational),
        "webdav_authenticated": None,  # Verified only with scoped worker credential.
        "reason_schema_version": 1,
        "node_id": node_id,
        "node_label": _safe_text(
            agent.get("name")
            or agent.get("hostname")
            or node_id,
            "Device",
            80,
        ),
        "provider": _PROVIDER_ID,
        "summary": summary,
        "blockers": blockers,
        "rclone_available": cap["rclone_available"],
        "rclone_version": cap["rclone_version"],
        "tool_repair": cap["repair"],
        "photo_storage_access": cap["photo_storage_access"],
        "collections": cap["collections"],
        "destination_ready": destination_operational,
        "storage": capacity,
        "destinations": lite_photo_backup_destinations.destinations(
            capacity, operational=destination_operational
        ),
        "selected_destination_id": lite_photo_backup_destinations.CURRENT_DESTINATION_ID,
        "sanitized": True,
    }


def reconcile_stale_jobs() -> int:
    stale_after = CREDENTIAL_TTL_SECONDS + 15 * 60
    changed = 0
    evidence_jobs: list[dict[str, Any]] = []
    with _LOCK:
        payload = _state()
        now_epoch = _epoch()
        for job in payload["jobs"].values():
            if not isinstance(job, dict):
                continue
            if str(job.get("status") or "") not in ACTIVE_STATES:
                continue
            started = str(job.get("started_at") or "")
            try:
                started_epoch = datetime.fromisoformat(
                    started.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, TypeError):
                started_epoch = now_epoch
            if now_epoch - started_epoch <= stale_after:
                continue
            credential_revoked = (
                _revoke_job_credential(job)
            )
            job[
                "credential_revoke_status_internal"
            ] = (
                "revoked"
                if credential_revoked
                else "pending"
            )
            job["status"] = "interrupted"
            job["summary"] = "Photo backup was interrupted. You can retry safely."
            job["retryable"] = True
            job["reason_code"] = "timeout"
            job["completed_at"] = _now()
            job["updated_at"] = _now()
            evidence_jobs.append(dict(job))
            changed += 1
        if changed:
            _save_state(payload)
    for job in evidence_jobs:
        _append_evidence(
            job,
            "lite.photo_backup.interrupted",
        )
        _append_evidence(
            job,
            (
                "lite.photo_backup.credential_revoked"
                if str(
                    job.get(
                        "credential_revoke_status_internal"
                    )
                    or ""
                )
                == "revoked"
                else (
                    "lite.photo_backup."
                    "credential_revoke_pending"
                )
            ),
        )
    return changed


def status(
    node_id: str,
    request: Request | None = None,
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    ready = readiness(node_id, request)
    payload = _state()
    latest_id = str(
        payload["latest_by_node"].get(node_id) or ""
    )
    latest = (
        _public_job(
            payload["jobs"].get(latest_id)
        )
        if latest_id
        else None
    )
    return {
        **ready,
        "latest_backup": latest,
        "last_backup_retryable": bool(latest and latest.get("retryable")),
        "credential_revocation_pending": bool(latest and latest.get("credential_revoke_status") == "pending"),
        "updated_at": payload.get("updated_at") or _now(),
    }


def fleet_status(
    request: Request | None = None,
) -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    for agent in fleet_registry.list_agents(
        include_stale=True
    ):
        if (
            not isinstance(agent, dict)
            or _is_protected_server(agent)
        ):
            continue
        node_id = fleet_registry.normalize_node_id(
            str(
                agent.get("node_id")
                or agent.get("id")
                or agent.get("name")
                or ""
            )
        )
        if not node_id or node_id == "unknown-node":
            continue
        try:
            devices.append(
                status(node_id, request)
            )
        except HTTPException:
            continue
    return {
        "status": "ok",
        "provider": _PROVIDER_ID,
        "devices": devices,
        "updated_at": _now(),
        "sanitized": True,
    }


def make_start_command(
    node_id: str,
    collections: Any,
    *,
    reason: str = "manual photo backup",
    request: Request | None = None,
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    current = {**status(node_id, request), **readiness(node_id, request, force=True)}
    latest = (
        current.get("latest_backup")
        if isinstance(
            current.get("latest_backup"),
            dict,
        )
        else None
    )
    if (
        latest
        and str(latest.get("status") or "")
        in ACTIVE_STATES
    ):
        return {
            "idempotent": True,
            "command_id": str(
                latest.get("backup_id") or ""
            ),
            "backup_id": str(
                latest.get("backup_id") or ""
            ),
            "node_id": node_id,
            "collections": (
                latest.get("collections")
                or _collections(collections)
            ),
            "reason": (
                "Existing photo backup is still active."
            ),
        }

    # Server Phone PhotoPrism originals are a shared low-power destination.
    # Admit only one photo-backup transfer at a time across the fleet.
    state_snapshot = _state()
    other_active = next(
        (
            job
            for job in state_snapshot["jobs"].values()
            if isinstance(job, dict)
            and str(job.get("status") or "") in ACTIVE_STATES
            and str(job.get("node_id") or "") != node_id
        ),
        None,
    )
    if other_active:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "photo_backup_busy",
                "reason_code": "storage_reservation_conflict",
                "summary": (
                    "Another device is backing up photos. "
                    "Try again when it finishes."
                ),
                "retryable": True,
                "sanitized": True,
            },
        )
    if not current.get("backup_admissible"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "not_ready",
                "summary": current.get("summary"),
                "blockers": current.get("blockers") or [],
                "reason_code": current.get("reason_code"),
                "sanitized": True,
            },
        )

    backup_id = f"photo-{uuid.uuid4().hex[:20]}"
    retry_count = (
        max(
            0,
            int(latest.get("retry_count") or 0),
        )
        + 1
        if (
            isinstance(latest, dict)
            and bool(latest.get("retryable"))
        )
        else 0
    )
    server_storage_before = (
        current.get("storage")
        if isinstance(current.get("storage"), dict)
        else server_capacity()
    )
    command = {
        "command_id": backup_id,
        "backup_id": backup_id,
        "node_id": node_id,
        "collections": _collections(collections),
        "reason": _safe_text(
            reason,
            "manual photo backup",
            100,
        ),
        "provider": _PROVIDER_ID,
        "destination_id": lite_photo_backup_destinations.CURRENT_DESTINATION_ID,
        "requested_by": "lite-api",
        "requested_at": _now(),
    }
    with _LOCK:
        payload = _state()
        locked_active = next(
            (
                job
                for job in payload["jobs"].values()
                if isinstance(job, dict)
                and str(job.get("status") or "") in ACTIVE_STATES
            ),
            None,
        )
        if locked_active:
            if str(locked_active.get("node_id") or "") == node_id:
                existing_id = str(
                    locked_active.get("backup_id") or ""
                )
                return {
                    "idempotent": True,
                    "command_id": existing_id,
                    "backup_id": existing_id,
                    "node_id": node_id,
                    "collections": (
                        locked_active.get("collections")
                        or command["collections"]
                    ),
                    "reason": (
                        "Existing photo backup is still active."
                    ),
                }
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "photo_backup_busy",
                    "reason_code": "storage_reservation_conflict",
                    "summary": (
                        "Another device is backing up photos. "
                        "Try again when it finishes."
                    ),
                    "retryable": True,
                    "sanitized": True,
                },
            )
        agent = _agent(node_id)
        payload["jobs"][backup_id] = {
            "backup_id": backup_id,
            "node_id": node_id,
            "node_label": _safe_text(
                agent.get("name")
                or agent.get("hostname")
                or node_id,
                "Device",
                80,
            ),
            "provider": _PROVIDER_ID,
            "destination_id": lite_photo_backup_destinations.CURRENT_DESTINATION_ID,
            "destination_contract_version": lite_photo_backup_destinations.SCHEMA_VERSION,
            "status": "queued",
            "summary": "Photo backup request queued.",
            "collections": command["collections"],
            "items_total": 0,
            "items_transferred": 0,
            "items_skipped": 0,
            "items_remaining": 0,
            "conflicts": 0,
            "bytes_total": 0,
            "bytes_total_planned": 0,
            "bytes_total_required": 0,
            "bytes_transferred": 0,
            "bytes_remaining": 0,
            "photo_processing_state": "",
            "retry_count": retry_count,
            "reserve_policy": {
                "hard_reserve_fraction": HARD_RESERVE_FRACTION,
                "planning_reserve_fraction": PLANNING_RESERVE_FRACTION,
                "planning_reserve_min_bytes": PLANNING_RESERVE_MIN_BYTES,
            },
            "server_storage_before": server_storage_before,
            "partial": False,
            "retryable": True,
            "destination_ready": True,
            "rclone_available": True,
            "photo_storage_access": True,
            "storage": server_capacity(),
            "progress": {
                "phase": "queued",
                "percent": 0,
                "step": "Backup queued.",
            },
            "started_at": _now(),
            "updated_at": _now(),
            "sanitized": True,
        }
        payload["latest_by_node"][node_id] = backup_id
        _save_state(payload)
    return command


def mark_submission_failed(
    backup_id: str,
) -> dict[str, Any]:
    _, job = _find_job(backup_id)
    if str(job.get("status") or "") in TERMINAL_STATES:
        return _public_job(job) or {}
    updated = _update_job(
        backup_id,
        status="failed",
        summary=(
            "Photo backup could not be queued. "
            "You can try again."
        ),
        retryable=True,
        reason_code="command_submission_failed",
        completed_at=_now(),
    )
    _append_evidence(
        updated,
        "lite.photo_backup.failed",
    )
    return _public_job(updated) or {}


def make_cancel_command(
    node_id: str,
    *,
    reason: str = "manual cancel",
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    payload = _state()
    backup_id = str(
        payload["latest_by_node"].get(node_id) or ""
    )
    job = (
        payload["jobs"].get(backup_id)
        if backup_id
        else None
    )
    if (
        not isinstance(job, dict)
        or str(job.get("status") or "")
        not in ACTIVE_STATES
    ):
        return {
            "command_id": (
                f"cancel-{uuid.uuid4().hex[:18]}"
            ),
            "backup_id": backup_id,
            "node_id": node_id,
            "idle": True,
            "reason": _safe_text(
                reason,
                "manual cancel",
                100,
            ),
        }
    return {
        "command_id": (
            f"cancel-{uuid.uuid4().hex[:18]}"
        ),
        "backup_id": backup_id,
        "node_id": node_id,
        "idle": False,
        "reason": _safe_text(
            reason,
            "manual cancel",
            100,
        ),
    }


def make_repair_command(
    node_id: str,
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    agent = _agent(node_id)
    if _is_protected_server(agent):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "not_allowed",
                "summary": (
                    "Choose a secondary device."
                ),
            },
        )
    return {
        "command_id": (
            f"repair-{uuid.uuid4().hex[:18]}"
        ),
        "node_id": node_id,
        "tool": "rclone",
        "requested_by": "lite-api",
    }


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _photoprism_command(
    args: list[str],
    *,
    timeout: int = 20,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if (
        not _env_file().is_file()
        or not shutil_which("proot-distro")
    ):
        raise RuntimeError(
            "photoprism_runtime_unavailable"
        )
    fixed = " ".join(
        shlex.quote(str(item))
        for item in args
    )
    script = (
        "set -Eeuo pipefail; "
        f"set -a; source {shlex.quote(str(_env_file()))}; "
        "set +a; "
        f"exec photoprism {fixed}"
    )
    return subprocess.run(
        [
            "proot-distro",
            "login",
            "ubuntu",
            "--",
            "bash",
            "-lc",
            script,
        ],
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )


def _parse_app_password(output: str) -> str:
    for raw_line in str(output or "").splitlines():
        line = _ANSI_ESCAPE_RE.sub("", raw_line).translate(
            _PHOTOPRISM_TABLE_TRANSLATION
        )
        line = "".join(
            character
            for character in line
            if unicodedata.category(character)
            not in {"Cc", "Cf"}
        )
        if (
            "webdav" not in line.lower()
            or "|" not in line
        ):
            continue
        cells = [
            cell.strip()
            for cell in line.split("|")
            if cell.strip()
        ]
        if (
            len(cells) >= 2
            and cells[-1].lower() == "webdav"
            and cells[0].lower() != "app password"
        ):
            candidate = cells[0]
            if re.fullmatch(
                r"[A-Za-z0-9_-]{8,}(?:-[A-Za-z0-9_-]{3,})+",
                candidate,
            ):
                return candidate
    return ""


def _parse_auth_id(
    output: str,
    auth_name: str,
) -> str:
    text = str(output or "").strip()
    # Current PhotoPrism auth ls --json exports canonical field names,
    # including session_id and client. Prefer that machine-readable contract.
    try:
        rows = json.loads(text)
    except json.JSONDecodeError:
        rows = None
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            session_id = str(
                row.get("session_id") or ""
            ).strip()
            client = str(
                row.get("client") or ""
            ).strip()
            scope = str(
                row.get("scope") or ""
            ).strip()
            if (
                session_id
                and re.fullmatch(
                    r"[A-Za-z0-9_-]{8,80}",
                    session_id,
                )
                and (
                    not client
                    or client.casefold()
                    == auth_name.casefold()
                )
                and (
                    not scope
                    or "webdav"
                    in scope.casefold()
                )
            ):
                return session_id

    # Narrow compatibility fallback for older PhotoPrism table output:
    # the first data column is Session ID and the matching client name must
    # appear in the same row. Never accept the client name itself as an ID.
    for line in text.splitlines():
        if (
            auth_name.casefold()
            not in line.casefold()
            or "|" not in line
        ):
            continue
        cells = [
            cell.strip()
            for cell in line.split("|")
            if cell.strip()
        ]
        if not cells:
            continue
        candidate = cells[0]
        if (
            candidate.casefold()
            != auth_name.casefold()
            and candidate.casefold()
            not in {"session id", "session_id"}
            and re.fullmatch(
                r"[A-Za-z0-9_-]{8,80}",
                candidate,
            )
        ):
            return candidate
    return ""


def _auth_name(
    node_id: str,
    backup_id: str,
) -> str:
    return (
        f"PocketLab-{node_id[:24]}-"
        f"{backup_id[-8:]}"
    )


def _find_auth_id(auth_name: str) -> str:
    # Search with the client name first, then fall back to unfiltered output.
    # All identifiers used here are non-secret session metadata; the generated
    # app password is never placed in a subprocess argument.
    attempts = (
        ["auth", "ls", "--json", auth_name],
        ["auth", "ls", auth_name],
        ["auth", "ls", "--json"],
        ["auth", "ls"],
    )
    for args in attempts:
        listed = _photoprism_command(
            args,
            timeout=PHOTOPRISM_COMMAND_TIMEOUT_SECONDS,
        )
        if listed.returncode != 0:
            continue
        auth_id = _parse_auth_id(
            listed.stdout or "",
            auth_name,
        )
        if auth_id:
            return auth_id
    return ""


def _create_app_password(
    node_id: str,
    backup_id: str,
) -> tuple[str, str, str]:
    scopes = _photoprism_command(
        ["show", "scopes"],
        timeout=PHOTOPRISM_COMMAND_TIMEOUT_SECONDS,
    )
    if (
        scopes.returncode != 0
        or "webdav"
        not in (scopes.stdout or "").lower()
    ):
        raise RuntimeError(
            "webdav_scope_unavailable"
        )
    auth_name = _auth_name(
        node_id,
        backup_id,
    )
    existing_auth_id = _find_auth_id(
        auth_name
    )
    if (
        existing_auth_id
        and not _revoke_auth_id(
            existing_auth_id
        )
    ):
        raise RuntimeError(
            "webdav_credential_revoke_failed"
        )
    created = _photoprism_command(
        [
            "auth",
            "add",
            "-n",
            auth_name,
            "-s",
            "webdav",
            "-e",
            str(CREDENTIAL_TTL_SECONDS),
            "admin",
        ],
        timeout=PHOTOPRISM_COMMAND_TIMEOUT_SECONDS,
    )
    if created.returncode != 0:
        raise RuntimeError(
            "webdav_credential_creation_failed"
        )
    password = _parse_app_password(
        created.stdout or ""
    )
    auth_id = _find_auth_id(
        auth_name
    )
    if not password or not auth_id:
        # Never pass the generated app password to a process argument. If a
        # revocable session id cannot be recovered from PhotoPrism metadata,
        # fail closed; the short-lived app password remains bounded by its
        # configured expiration instead of being exposed via argv.
        if auth_id:
            _revoke_auth_id(
                auth_id
            )
        raise RuntimeError(
            "webdav_credential_parse_failed"
        )
    return password, auth_name, auth_id


def _revoke_auth_id(auth_id: str) -> bool:
    safe = str(auth_id or "").strip()
    if (
        not safe
        or not re.fullmatch(
            r"[A-Za-z0-9_-]{8,80}",
            safe,
        )
    ):
        return False
    try:
        result = _photoprism_command(
            ["auth", "rm", safe],
            timeout=PHOTOPRISM_COMMAND_TIMEOUT_SECONDS,
            input_text="y\n",
        )
        return result.returncode in {0, 3}
    except Exception:
        return False


def _credential_path(
    credential_ref: str,
) -> Path:
    if not re.fullmatch(
        r"cred-[a-f0-9]{32}",
        str(credential_ref or ""),
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_found",
                "summary": (
                    "Credential reference "
                    "was not found."
                ),
            },
        )
    return (
        _credential_dir()
        / f"{credential_ref}.bin"
    )


def _store_credential(
    *,
    credential_ref: str,
    backup_id: str,
    node_id: str,
    password: str,
    auth_name: str,
    auth_id: str,
    webdav_url: str,
) -> None:
    expires_at = _epoch() + CREDENTIAL_TTL_SECONDS
    payload = {
        "credential_ref": credential_ref,
        "backup_id": backup_id,
        "node_id": node_id,
        "username": "admin",
        "password": password,
        "auth_name": auth_name,
        "auth_id": auth_id,
        "webdav_url": webdav_url,
        "expires_at_epoch": expires_at,
        "created_at": _now(),
    }
    plaintext = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encrypted = _credential_cipher().encrypt(
        plaintext
    )
    _write_private_bytes(
        _credential_path(credential_ref),
        encrypted,
    )


def _load_credential(
    credential_ref: str,
) -> dict[str, Any] | None:
    path = _credential_path(credential_ref)
    try:
        encrypted = path.read_bytes()
    except (FileNotFoundError, OSError):
        return None
    try:
        plaintext = _credential_cipher().decrypt(
            encrypted
        )
        data = json.loads(
            plaintext.decode("utf-8")
        )
    except (
        InvalidToken,
        UnicodeDecodeError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    if not isinstance(data, dict):
        return None
    if float(
        data.get("expires_at_epoch") or 0
    ) <= _epoch():
        _revoke_auth_id(
            str(data.get("auth_id") or "")
        )
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return data


def _delete_credential(
    credential_ref: str,
) -> None:
    try:
        _credential_path(
            credential_ref
        ).unlink()
    except (OSError, HTTPException):
        pass


def _revoke_credentials_for_backup(
    backup_id: str,
    node_id: str,
) -> int:
    root = _credential_dir()
    if not root.exists():
        return 0
    revoked = 0
    for path in root.glob("cred-*.bin"):
        try:
            data = _load_credential(path.stem)
        except HTTPException:
            data = None
        if not isinstance(data, dict):
            continue
        if (
            str(data.get("backup_id") or "") != backup_id
            or str(data.get("node_id") or "") != node_id
        ):
            continue
        _revoke_auth_id(
            str(data.get("auth_id") or "")
        )
        _delete_credential(path.stem)
        revoked += 1
    return revoked


def _probe_webdav(
    url: str,
    username: str,
    password: str,
) -> bool:
    if not str(url).startswith("https://"):
        return False
    authorization = (
        "Basic "
        + base64.b64encode(
            f"{username}:{password}".encode(
                "utf-8"
            )
        ).decode("ascii")
    )

    def probe(
        method: str,
        allowed: set[int],
    ) -> bool:
        request = urllib.request.Request(
            url,
            method=method,
        )
        request.add_header(
            "Authorization",
            authorization,
        )
        if method == "PROPFIND":
            request.add_header("Depth", "0")
        try:
            with urllib.request.urlopen(
                request,
                timeout=8,
            ) as response:
                return int(
                    getattr(
                        response,
                        "status",
                        0,
                    )
                    or 0
                ) in allowed
        except urllib.error.HTTPError as exc:
            return int(exc.code or 0) in allowed
        except Exception:
            return False

    # Validate both route reachability/method handling and authenticated
    # WebDAV collection access before any node transfer is admitted.
    return (
        probe("OPTIONS", {200, 204})
        and probe("PROPFIND", {200, 207})
    )


def _update_job(
    backup_id: str,
    **changes: Any,
) -> dict[str, Any]:
    with _LOCK:
        payload, job = _find_job(backup_id)
        for key, value in changes.items():
            if key in {
                "password",
                "token",
                "secret",
                "webdav_url",
                "auth_id",
                "auth_name",
            }:
                continue
            job[key] = value
        job["updated_at"] = _now()
        payload["jobs"][backup_id] = job
        _save_state(payload)
        return job


def _credential_ref_for_job(
    job: dict[str, Any],
) -> str:
    return str(
        job.get("credential_ref_internal")
        or ""
    )


def _credential_auth_id_for_job(
    job: dict[str, Any],
) -> str:
    return str(
        job.get("auth_id_internal")
        or ""
    )


def _revoke_job_credential(
    job: dict[str, Any],
) -> bool:
    auth_ids: set[str] = set()
    ref = _credential_ref_for_job(job)
    if ref:
        data = None
        try:
            data = _load_credential(ref)
        except HTTPException:
            data = None
        if isinstance(data, dict):
            candidate = str(
                data.get("auth_id") or ""
            )
            if candidate:
                auth_ids.add(candidate)
        _delete_credential(ref)
    auth_id = _credential_auth_id_for_job(
        job
    )
    if auth_id:
        auth_ids.add(auth_id)

    if not auth_ids:
        return not bool(
            job.get("credential_expires_at")
        )

    revoked = True
    for candidate in auth_ids:
        revoked = (
            _revoke_auth_id(candidate)
            and revoked
        )
    return revoked


async def _publish_audit(
    subject: str,
    event_type: str,
    data: dict[str, Any],
    *,
    trace_id: str,
) -> None:
    """Best-effort sanitized audit; local evidence remains authoritative."""
    try:
        await BUS.publish_json(
            subject,
            event_type,
            {**data, "sanitized": True},
            trace_id=trace_id,
        )
    except Exception:
        # A transient audit transport outage must not expose a credential or
        # leave a prepared transfer half-admitted. The same lifecycle event is
        # retained in the bounded local evidence log.
        return


def _append_evidence(
    job: dict[str, Any],
    event_type: str,
) -> None:
    payload = _read_json(
        _evidence_path(),
        {"events": []},
    )
    if not isinstance(payload, dict):
        payload = {"events": []}
    events = (
        payload.get("events")
        if isinstance(
            payload.get("events"),
            list,
        )
        else []
    )
    public = _public_job(job) or {}
    events.insert(
        0,
        {
            "event_type": event_type,
            "captured_at": _now(),
            **public,
        },
    )
    payload["events"] = events[:200]
    payload["updated_at"] = _now()
    _write_json(_evidence_path(), payload)


def authenticate_agent(
    node_id: str,
    token: str,
) -> dict[str, Any]:
    node_id = _safe_node_id(node_id)
    token = str(token or "")
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "unauthorized",
                "summary": (
                    "Device authentication "
                    "is required."
                ),
            },
        )
    agent = _agent(node_id)
    expected = str(
        agent.get("auth_token_hash") or ""
    )
    actual = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()[:16]
    if (
        not expected
        or not secrets.compare_digest(
            expected,
            actual,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "forbidden",
                "summary": (
                    "Device authentication "
                    "was rejected."
                ),
            },
        )
    return agent


def consume_credential(
    *,
    credential_ref: str,
    node_id: str,
    backup_id: str,
) -> dict[str, Any]:
    data = _load_credential(
        credential_ref
    )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=410,
            detail={
                "status": "expired",
                "reason_code": "credential_expired",
                "summary": (
                    "Photo backup credential "
                    "expired. Start the backup "
                    "again."
                ),
            },
        )
    if (
        str(data.get("node_id") or "")
        != node_id
        or str(data.get("backup_id") or "")
        != backup_id
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "forbidden",
                "reason_code": "credential_identity_mismatch",
                "summary": (
                    "Credential reference does "
                    "not match this backup."
                ),
            },
        )
    capacity = server_capacity()
    reason = _capacity_diagnostic(capacity)
    if reason:
        raise HTTPException(status_code=409, detail={
            "status": reason,
            "reason_code": reason,
            "summary": "Not enough protected destination space is available.",
            "sanitized": True})
    try:
        placement = _verified_placement(backup_id, node_id)
    except ValueError:
        raise HTTPException(status_code=409, detail={
            "status": "destination_identity_mismatch",
            "reason_code": "destination_identity_mismatch",
            "summary": "Destination placement no longer matches this backup.",
            "sanitized": True}) from None
    response = {
        "credential_ref": credential_ref,
        "backup_id": backup_id,
        "username": str(
            data.get("username") or "admin"
        ),
        "password": str(
            data.get("password") or ""
        ),
        "webdav_url": str(
            data.get("webdav_url") or ""
        ),
        "destination_prefix": placement["prefix"],
        "expires_at_epoch": float(
            data.get("expires_at_epoch") or 0
        ),
        "capacity": capacity,
    }
    _delete_credential(credential_ref)
    return response


def capacity_for_agent(
    backup_id: str,
    node_id: str,
) -> dict[str, Any]:
    _, job = _find_job(backup_id)
    if str(job.get("node_id") or "") != node_id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "forbidden",
                "summary": "Backup does not belong to this device.",
            },
        )
    capacity = server_capacity()
    try:
        _verified_placement(backup_id, node_id)
    except ValueError:
        return {"status": "unavailable", "reason_code": "destination_identity_mismatch",
                "hard_upload_budget_bytes": 0, "safe_upload_budget_bytes": 0,
                "sanitized": True}
    return capacity


def record_agent_progress(
    backup_id: str,
    node_id: str,
    progress: dict[str, Any],
) -> dict[str, Any]:
    _, job = _find_job(backup_id)
    if (
        str(job.get("node_id") or "")
        != node_id
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "forbidden",
                "summary": (
                    "Backup does not belong "
                    "to this device."
                ),
            },
        )
    current_status = str(
        job.get("status") or ""
    ).strip().lower()
    if current_status in TERMINAL_STATES:
        return _public_job(job) or {}
    status_value = str(
        progress.get("status")
        or job.get("status")
        or "transferring"
    ).strip().lower()
    if (
        status_value
        not in ACTIVE_STATES | TERMINAL_STATES
    ):
        status_value = "transferring"

    progress_payload = (
        progress.get("progress")
        if isinstance(
            progress.get("progress"),
            dict,
        )
        else {}
    )
    capacity_snapshot = server_capacity()
    bounded = {
        "status": status_value,
        "summary": _safe_text(
            progress.get("summary"),
            (
                "Photo backup is running."
                if status_value
                not in TERMINAL_STATES
                else "Photo backup finished."
            ),
        ),
        "items_total": max(
            0,
            int(
                progress.get("items_total")
                or job.get("items_total")
                or 0
            ),
        ),
        "items_transferred": max(
            0,
            int(
                progress.get("items_transferred")
                or job.get(
                    "items_transferred"
                )
                or 0
            ),
        ),
        "items_skipped": max(
            0,
            int(
                progress.get("items_skipped")
                or job.get("items_skipped")
                or 0
            ),
        ),
        "items_remaining": max(
            0,
            int(
                progress.get("items_remaining")
                or job.get("items_remaining")
                or 0
            ),
        ),
        "conflicts": max(
            0,
            int(
                progress.get("conflicts")
                or job.get("conflicts")
                or 0
            ),
        ),
        "bytes_total": max(
            0,
            int(
                progress.get("bytes_total")
                or job.get("bytes_total")
                or 0
            ),
        ),
        "bytes_total_planned": max(
            0,
            int(
                progress.get("bytes_total_planned")
                or job.get("bytes_total_planned")
                or 0
            ),
        ),
        "bytes_total_required": max(
            0,
            int(
                progress.get("bytes_total_required")
                or job.get("bytes_total_required")
                or progress.get("bytes_total")
                or job.get("bytes_total")
                or 0
            ),
        ),
        "bytes_transferred": max(
            0,
            int(
                progress.get(
                    "bytes_transferred"
                )
                or job.get(
                    "bytes_transferred"
                )
                or 0
            ),
        ),
        "bytes_remaining": max(
            0,
            int(
                progress.get("bytes_remaining")
                or job.get("bytes_remaining")
                or 0
            ),
        ),
        "photo_processing_state": (
            _safe_text(
                progress.get("photo_processing_state"),
                "",
                64,
            )
            if progress.get("photo_processing_state")
            else str(job.get("photo_processing_state") or "")
        ),
        "partial": bool(
            progress.get("partial")
            or status_value
            == "partial_storage_limit"
        ),
        "retryable": bool(
            progress.get(
                "retryable",
                status_value
                in {
                    "failed",
                    "interrupted",
                    "source_offline",
                    "destination_unavailable",
                    "partial_storage_limit",
                },
            )
        ),
        "reason_code": (
            _safe_text(
                progress.get("reason_code"),
                "",
                64,
            )
            if progress.get("reason_code")
            else ""
        ),
        "progress": {
            "phase": _safe_text(
                progress_payload.get(
                    "phase"
                )
                or status_value,
                status_value,
                64,
            ),
            "percent": max(
                0,
                min(
                    100,
                    int(
                        progress_payload.get(
                            "percent"
                        )
                        or progress.get(
                            "percent"
                        )
                        or 0
                    ),
                ),
            ),
            "step": _safe_text(
                progress_payload.get("step")
                or progress.get("summary"),
                "Photo backup is running.",
            ),
        },
        "storage": capacity_snapshot,
    }
    credential_revoked = True
    if status_value in TERMINAL_STATES:
        bounded["completed_at"] = _now()
        bounded["server_storage_after"] = (
            capacity_snapshot
        )
        if status_value in {
            "completed",
            "partial_storage_limit",
        }:
            bounded["last_success_at"] = _now()
        credential_revoked = (
            _revoke_job_credential(job)
        )
        bounded[
            "credential_revoke_status_internal"
        ] = (
            "revoked"
            if credential_revoked
            else "pending"
        )
    updated = _update_job(
        backup_id,
        **bounded,
    )
    if status_value in TERMINAL_STATES:
        _append_evidence(
            updated,
            f"lite.photo_backup.{status_value}",
        )
        _append_evidence(
            updated,
            (
                "lite.photo_backup.credential_revoked"
                if credential_revoked
                else (
                    "lite.photo_backup."
                    "credential_revoke_pending"
                )
            ),
        )
    return _public_job(updated) or {}


def claim_progress_audit_events(
    backup_id: str,
    node_id: str,
) -> list[dict[str, Any]]:
    with _LOCK:
        state, job = _find_job(backup_id)
        if str(job.get("node_id") or "") != node_id:
            return []
        status_value = str(
            job.get("status") or ""
        ).strip().lower()
        now_epoch = _epoch()
        event_type = ""
        if status_value == "transferring":
            last_epoch = float(
                job.get(
                    "progress_audit_epoch_internal"
                )
                or 0
            )
            if now_epoch - last_epoch < 60:
                return []
            job[
                "progress_audit_epoch_internal"
            ] = now_epoch
            event_type = "lite.photo_backup.progress"
        elif status_value in TERMINAL_STATES:
            if (
                str(
                    job.get(
                        "terminal_audit_status_internal"
                    )
                    or ""
                )
                == status_value
            ):
                return []
            job[
                "terminal_audit_status_internal"
            ] = status_value
            event_type = {
                "completed": "lite.photo_backup.completed",
                "partial_storage_limit": "lite.photo_backup.partial",
                "cancelled": "lite.photo_backup.cancelled",
            }.get(
                status_value,
                "lite.photo_backup.failed",
            )
        else:
            return []
        state["jobs"][backup_id] = job
        _save_state(state)

    data = {
        "backup_id": backup_id,
        "node_id": node_id,
        "provider": _PROVIDER_ID,
        "status": status_value,
        "items_total": max(
            0,
            int(job.get("items_total") or 0),
        ),
        "items_transferred": max(
            0,
            int(job.get("items_transferred") or 0),
        ),
        "items_remaining": max(
            0,
            int(job.get("items_remaining") or 0),
        ),
        "conflicts": max(
            0,
            int(job.get("conflicts") or 0),
        ),
        "bytes_total_required": max(
            0,
            int(job.get("bytes_total_required") or 0),
        ),
        "bytes_transferred": max(
            0,
            int(job.get("bytes_transferred") or 0),
        ),
        "bytes_remaining": max(
            0,
            int(job.get("bytes_remaining") or 0),
        ),
        "partial": bool(job.get("partial")),
        "reason_code": _safe_text(
            job.get("reason_code"),
            "",
            64,
        ) if job.get("reason_code") else "",
        "photo_processing_state": _safe_text(
            job.get("photo_processing_state"),
            "",
            64,
        ) if job.get("photo_processing_state") else "",
    }
    events = [{
        "subject": (
            "pocketlab.audit."
            + event_type
        ),
        "event_type": event_type,
        "data": data,
        "trace_id": backup_id,
    }]
    if status_value in TERMINAL_STATES:
        revoke_status = str(
            job.get(
                "credential_revoke_status_internal"
            )
            or ""
        )
        credential_event = (
            "lite.photo_backup.credential_revoked"
            if revoke_status == "revoked"
            else (
                "lite.photo_backup."
                "credential_revoke_pending"
            )
        )
        events.append({
            "subject": (
                "pocketlab.audit."
                + credential_event
            ),
            "event_type": credential_event,
            "data": {
                "backup_id": backup_id,
                "node_id": node_id,
                "provider": _PROVIDER_ID,
                "status": revoke_status or "pending",
            },
            "trace_id": backup_id,
        })
    return events


async def publish_audit_events(
    events: list[dict[str, Any]],
) -> None:
    for event in events:
        await _publish_audit(
            str(event.get("subject") or ""),
            str(event.get("event_type") or ""),
            (
                event.get("data")
                if isinstance(
                    event.get("data"),
                    dict,
                )
                else {}
            ),
            trace_id=str(
                event.get("trace_id") or ""
            ),
        )


async def _publish_node_command(
    node_id: str,
    command: str,
    payload: dict[str, Any],
    *,
    requested_by: str = "photo-backup",
) -> dict[str, Any]:
    item = fleet_registry.create_node_command(
        node_id,
        command,
        payload,
        requested_by=requested_by,
    )
    subject = (
        f"pocketlab.commands.node."
        f"{node_id}.{command}"
    )
    await BUS.publish_json(
        subject,
        "fleet.node_command_requested",
        {
            **item,
            "command_subject": subject,
        },
        trace_id=item["command_id"],
    )
    await BUS.publish_json(
        "pocketlab.events.fleet."
        "node_command_queued",
        "fleet.node_command_queued",
        {
            "node_id": node_id,
            "command_id": item["command_id"],
            "command": command,
            "requested_from": "photo-backup",
        },
        trace_id=item["command_id"],
    )
    return item


async def execute_start(
    command: dict[str, Any],
) -> dict[str, Any]:
    if command.get("idempotent"):
        return {
            "status": "already_running",
            "backup_id": command.get(
                "backup_id"
            ),
            "node_id": command.get(
                "node_id"
            ),
            "sanitized": True,
        }
    backup_id = str(
        command.get("backup_id")
        or command.get("command_id")
        or ""
    )
    node_id = _safe_node_id(
        command.get("node_id")
    )
    _, existing_job = _find_job(
        backup_id
    )
    existing_status = str(
        existing_job.get("status") or ""
    ).lower()
    if existing_status in TERMINAL_STATES:
        return _public_job(existing_job) or {}
    if (
        existing_status
        in {
            "starting",
            "transferring",
            "cancelling",
        }
        or _credential_ref_for_job(existing_job)
        or _credential_auth_id_for_job(existing_job)
    ):
        # JetStream may redeliver after a worker restart or an ACK race.
        # Never rotate credentials or republish the node start command for an
        # already-admitted transfer.
        return _public_job(existing_job) or {}
    if existing_status not in {
        "queued",
        "planning",
        "waiting_for_credentials",
    }:
        return _public_job(existing_job) or {}
    _revoke_credentials_for_backup(
        backup_id,
        node_id,
    )
    _update_job(
        backup_id,
        status="planning",
        summary=(
            "Checking protected "
            "destination space."
        ),
        progress={
            "phase": "planning",
            "percent": 5,
            "step": (
                "Checking destination."
            ),
        },
        storage=server_capacity(),
    )
    origin = _secure_origin(None)
    runtime = lite_app_runtime.probe_app_runtime(
        "photoprism",
        force=True,
    )
    capacity = server_capacity()
    preflight_reason = _capacity_diagnostic(capacity)
    route_reason = (_webdav_route_probe(origin, force=True)
                    if runtime.get("running") and runtime.get("reachable")
                    else ("secure_route_unavailable" if not origin else None))
    if (
        preflight_reason or route_reason or not origin
        or not (
            runtime.get("running")
            and runtime.get("reachable")
        )
    ):
        failed = _update_job(
            backup_id,
            status="destination_unavailable",
            summary=(
                "PhotoPrism backup destination "
                "is not ready."
            ),
            retryable=True,
            reason_code=(preflight_reason or route_reason or
                         ("photoprism_not_running" if not runtime.get("running") else
                          "photoprism_unreachable" if not runtime.get("reachable") else
                          "destination_unavailable")),
            completed_at=_now(),
            storage=capacity,
        )
        _append_evidence(
            failed,
            "lite.photo_backup."
            "destination_unavailable",
        )
        return _public_job(failed) or {}

    try:
        placement = _ensure_placement(backup_id, node_id)
    except ValueError:
        failed = _update_job(backup_id, status="destination_unavailable",
                             reason_code="destination_identity_mismatch",
                             summary="Backup destination identity could not be verified.",
                             retryable=True, completed_at=_now())
        _append_evidence(failed, "lite.photo_backup.destination_unavailable")
        return _public_job(failed) or {}

    password = ""
    auth_name = ""
    auth_id = ""
    credential_ref = (
        f"cred-{uuid.uuid4().hex}"
    )
    webdav_url = (
        f"{origin}/apps/photoprism/"
        "originals/"
    )
    try:
        (
            password,
            auth_name,
            auth_id,
        ) = _create_app_password(
            node_id,
            backup_id,
        )
        if not _probe_webdav(
            webdav_url,
            "admin",
            password,
        ):
            raise RuntimeError(
                "webdav_auth_failed"
            )
        _store_credential(
            credential_ref=credential_ref,
            backup_id=backup_id,
            node_id=node_id,
            password=password,
            auth_name=auth_name,
            auth_id=auth_id,
            webdav_url=webdav_url,
        )
        job = _update_job(
            backup_id,
            status="starting",
            summary=(
                "Starting protected photo "
                "backup on the device."
            ),
            progress={
                "phase": "starting",
                "percent": 10,
                "step": (
                    "Starting on device."
                ),
            },
            credential_expires_at=(
                datetime.fromtimestamp(
                    _epoch()
                    + CREDENTIAL_TTL_SECONDS,
                    timezone.utc,
                )
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        )
        with _LOCK:
            state, stored = _find_job(
                backup_id
            )
            stored[
                "credential_ref_internal"
            ] = credential_ref
            stored[
                "auth_id_internal"
            ] = auth_id
            state["jobs"][
                backup_id
            ] = stored
            _save_state(state)

        _append_evidence(
            job,
            "lite.photo_backup.credential_created",
        )
        await _publish_audit(
            "pocketlab.audit.lite.photo_backup.credential_created",
            "lite.photo_backup.credential_created",
            {
                "backup_id": backup_id,
                "node_id": node_id,
                "provider": _PROVIDER_ID,
                "expires_in_seconds": CREDENTIAL_TTL_SECONDS,
            },
            trace_id=backup_id,
        )

        node_command = (
            await _publish_node_command(
                node_id,
                NODE_START_COMMAND,
                {
                    "backup_id": backup_id,
                    "credential_ref": (
                        credential_ref
                    ),
                    "collections": (
                        command.get(
                            "collections"
                        )
                        or list(
                            SUPPORTED_COLLECTIONS
                        )
                    ),
                },
            )
        )
        with _LOCK:
            state, stored = _find_job(
                backup_id
            )
            stored[
                "node_command_id_internal"
            ] = node_command.get(
                "command_id"
            )
            state["jobs"][
                backup_id
            ] = stored
            _save_state(state)

        await _publish_audit(
            "pocketlab.audit.lite."
            "photo_backup.started",
            "lite.photo_backup.started",
            {
                "backup_id": backup_id,
                "node_id": node_id,
                "provider": _PROVIDER_ID,
                "collections": (
                    command.get(
                        "collections"
                    )
                    or []
                ),
            },
            trace_id=backup_id,
        )
        return _public_job(job) or {}
    except Exception as exc:
        if auth_id:
            _revoke_auth_id(auth_id)
        _delete_credential(
            credential_ref
        )
        failed = _update_job(
            backup_id,
            status="destination_unavailable",
            summary=(
                "Photo backup could not "
                "start safely."
            ),
            retryable=True,
            reason_code=(
                "webdav_auth_failed" if str(exc) == "webdav_auth_failed"
                else "destination_unavailable"
            ),
            completed_at=_now(),
        )
        _append_evidence(
            failed,
            "lite.photo_backup."
            "destination_unavailable",
        )
        return _public_job(failed) or {}


async def execute_cancel(
    command: dict[str, Any],
) -> dict[str, Any]:
    node_id = _safe_node_id(
        command.get("node_id")
    )
    backup_id = str(
        command.get("backup_id") or ""
    )
    if (
        command.get("idle")
        or not backup_id
    ):
        return {
            "status": "idle",
            "node_id": node_id,
            "summary": (
                "No photo backup is running."
            ),
            "sanitized": True,
        }
    _, job = _find_job(backup_id)
    credential_revoked = (
        _revoke_job_credential(job)
    )
    credential_event = (
        "lite.photo_backup.credential_revoked"
        if credential_revoked
        else (
            "lite.photo_backup."
            "credential_revoke_pending"
        )
    )
    _append_evidence(
        job,
        credential_event,
    )
    await _publish_audit(
        "pocketlab.audit."
        + credential_event,
        credential_event,
        {
            "backup_id": backup_id,
            "node_id": node_id,
            "provider": _PROVIDER_ID,
            "status": (
                "revoked"
                if credential_revoked
                else "pending"
            ),
        },
        trace_id=backup_id,
    )
    _update_job(
        backup_id,
        status="cancelling",
        summary=(
            "Stopping photo backup safely."
        ),
        reason_code=("credential_revocation_pending" if not credential_revoked else "cancelled"),
        credential_revoke_status_internal=(
            "revoked"
            if credential_revoked
            else "pending"
        ),
        progress={
            "phase": "cancelling",
            "percent": int(
                (job.get("progress") or {}).get(
                    "percent"
                )
                or 0
            ),
            "step": (
                "Stopping after the "
                "current file."
            ),
        },
    )
    await _publish_node_command(
        node_id,
        NODE_CANCEL_COMMAND,
        {"backup_id": backup_id},
    )
    return {
        "status": "cancelling",
        "backup_id": backup_id,
        "node_id": node_id,
        "summary": (
            "Stopping photo backup safely."
        ),
        "sanitized": True,
    }


async def execute_repair(
    command: dict[str, Any],
) -> dict[str, Any]:
    node_id = _safe_node_id(
        command.get("node_id")
    )
    item = await _publish_node_command(
        node_id,
        NODE_REPAIR_COMMAND,
        {"tool": "rclone"},
    )
    return {
        "status": "queued",
        "node_id": node_id,
        "command_id": item.get(
            "command_id"
        ),
        "summary": (
            "Photo backup tools repair "
            "requested."
        ),
        "sanitized": True,
    }


def revoke_for_node(node_id: str) -> int:
    node_id = fleet_registry.normalize_node_id(
        node_id
    )
    count = 0
    evidence_jobs: list[dict[str, Any]] = []
    with _LOCK:
        payload = _state()
        for job in payload["jobs"].values():
            if (
                not isinstance(job, dict)
                or str(
                    job.get("node_id") or ""
                )
                != node_id
            ):
                continue
            if str(
                job.get("status") or ""
            ) in ACTIVE_STATES:
                credential_revoked = (
                    _revoke_job_credential(job)
                )
                job[
                    "credential_revoke_status_internal"
                ] = (
                    "revoked"
                    if credential_revoked
                    else "pending"
                )
                job["status"] = "cancelled"
                job["summary"] = (
                    "Photo backup stopped "
                    "because the device was "
                    "removed. Existing backup "
                    "files were preserved."
                )
                job[
                    "completed_at"
                ] = _now()
                job[
                    "updated_at"
                ] = _now()
                evidence_jobs.append(dict(job))
                count += 1
        _save_state(payload)
    for job in evidence_jobs:
        _append_evidence(
            job,
            "lite.photo_backup.cancelled",
        )
        _append_evidence(
            job,
            (
                "lite.photo_backup.credential_revoked"
                if str(
                    job.get(
                        "credential_revoke_status_internal"
                    )
                    or ""
                )
                == "revoked"
                else (
                    "lite.photo_backup."
                    "credential_revoke_pending"
                )
            ),
        )
    return count


def reconcile_pending_credential_revocations() -> int:
    reconciled = 0
    evidence_jobs: list[dict[str, Any]] = []
    with _LOCK:
        payload = _state()
        for job in payload["jobs"].values():
            if not isinstance(job, dict):
                continue
            if str(job.get("status") or "") not in TERMINAL_STATES:
                continue
            if (
                str(
                    job.get(
                        "credential_revoke_status_internal"
                    )
                    or ""
                )
                == "revoked"
            ):
                continue
            if not (
                _credential_ref_for_job(job)
                or _credential_auth_id_for_job(job)
            ):
                continue
            if not _revoke_job_credential(job):
                continue
            job[
                "credential_revoke_status_internal"
            ] = "revoked"
            job["updated_at"] = _now()
            evidence_jobs.append(dict(job))
            reconciled += 1
        if reconciled:
            _save_state(payload)
    for job in evidence_jobs:
        _append_evidence(
            job,
            "lite.photo_backup.credential_revoked",
        )
    return reconciled


def cleanup_expired_credentials() -> int:
    root = _credential_dir()
    if not root.exists():
        return 0
    removed = 0
    for path in root.glob(
        "cred-*.bin"
    ):
        before = path.exists()
        try:
            data = _load_credential(
                path.stem
            )
        except HTTPException:
            data = None
        if data is None:
            if before and not path.exists():
                removed += 1
            continue
        if float(
            data.get("expires_at_epoch") or 0
        ) <= _epoch():
            _revoke_auth_id(
                str(data.get("auth_id") or "")
            )
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed
