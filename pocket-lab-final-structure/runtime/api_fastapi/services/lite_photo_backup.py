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
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from .. import deps
from . import fleet_registry, lite_app_runtime, lite_catalog
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
STATE_SCHEMA_VERSION = 1
_PROVIDER_ID = "photoprism_webdav"
_LOCK = threading.RLock()
_SECRET_KEYS = {"password", "token", "secret", "credential", "authorization", "api_key"}


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
    payload.setdefault("updated_at", None)
    if not isinstance(payload["jobs"], dict):
        payload["jobs"] = {}
    if not isinstance(payload["latest_by_node"], dict):
        payload["latest_by_node"] = {}
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
        "bytes_total",
        "bytes_transferred",
        "partial",
        "started_at",
        "updated_at",
        "completed_at",
        "last_success_at",
        "retryable",
        "reason_code",
        "credential_expires_at",
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


def server_capacity() -> dict[str, Any]:
    root = _originals_path()
    try:
        root.mkdir(parents=True, exist_ok=True)
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
        "sanitized": True,
    }


def readiness(
    node_id: str,
    request: Request | None = None,
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
    runtime = lite_app_runtime.probe_app_runtime("photoprism")
    origin = _secure_origin(request)
    capacity = server_capacity()
    blockers: list[str] = []
    if not _agent_online(agent):
        blockers.append("source_offline")
    if not cap["rclone_available"]:
        blockers.append("rclone_unavailable")
    if not cap["photo_storage_access"]:
        blockers.append("photo_storage_access_missing")
    if not (
        runtime.get("running")
        and runtime.get("reachable")
    ):
        blockers.append("photoprism_unavailable")
    if not origin:
        blockers.append("secure_route_unavailable")
    if (
        capacity.get("status") != "ready"
        or int(
            capacity.get("hard_upload_budget_bytes") or 0
        )
        <= 0
    ):
        blockers.append("destination_storage_full")

    if "photo_storage_access_missing" in blockers:
        summary = "Allow photo access on this device."
    elif "rclone_unavailable" in blockers:
        summary = "Photo backup tools are not ready on this device."
    elif "source_offline" in blockers:
        summary = "This device is offline."
    elif "secure_route_unavailable" in blockers:
        summary = "Remote access not ready."
    elif "photoprism_unavailable" in blockers:
        summary = "PhotoPrism is not ready for photo backup."
    elif "destination_storage_full" in blockers:
        summary = (
            "Not enough protected space is available "
            "on the Server Phone."
        )
    else:
        summary = "Ready to back up photos."

    return {
        "status": "ready" if not blockers else "not_ready",
        "ready": not blockers,
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
        "photo_storage_access": cap["photo_storage_access"],
        "collections": cap["collections"],
        "destination_ready": bool(
            runtime.get("running")
            and runtime.get("reachable")
            and origin
        ),
        "storage": capacity,
        "sanitized": True,
    }


def reconcile_stale_jobs() -> int:
    stale_after = CREDENTIAL_TTL_SECONDS + 15 * 60
    changed = 0
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
            _revoke_job_credential(job)
            job["status"] = "interrupted"
            job["summary"] = "Photo backup was interrupted. You can retry safely."
            job["retryable"] = True
            job["reason_code"] = "timeout"
            job["completed_at"] = _now()
            job["updated_at"] = _now()
            changed += 1
        if changed:
            _save_state(payload)
    return changed


def status(
    node_id: str,
    request: Request | None = None,
) -> dict[str, Any]:
    reconcile_stale_jobs()
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
    current = status(node_id, request)
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
    if not current.get("ready"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "not_ready",
                "summary": current.get("summary"),
                "blockers": current.get("blockers") or [],
                "sanitized": True,
            },
        )

    backup_id = f"photo-{uuid.uuid4().hex[:20]}"
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
        "requested_by": "lite-api",
        "requested_at": _now(),
    }
    with _LOCK:
        payload = _state()
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
            "status": "queued",
            "summary": "Photo backup request queued.",
            "collections": command["collections"],
            "items_total": 0,
            "items_transferred": 0,
            "items_skipped": 0,
            "items_remaining": 0,
            "bytes_total": 0,
            "bytes_transferred": 0,
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
        timeout=timeout,
    )


def _parse_app_password(output: str) -> str:
    for line in str(output or "").splitlines():
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
    for line in str(output or "").splitlines():
        if (
            auth_name.lower() not in line.lower()
            or "|" not in line
        ):
            continue
        cells = [
            cell.strip()
            for cell in line.split("|")
            if cell.strip()
        ]
        for cell in cells:
            if (
                re.fullmatch(
                    r"[A-Za-z0-9_-]{8,80}",
                    cell,
                )
                and cell.lower()
                not in {"webdav", "admin"}
            ):
                return cell
    return ""


def _create_app_password(
    node_id: str,
    backup_id: str,
) -> tuple[str, str, str]:
    scopes = _photoprism_command(
        ["show", "scopes"],
        timeout=15,
    )
    if (
        scopes.returncode != 0
        or "webdav"
        not in (scopes.stdout or "").lower()
    ):
        raise RuntimeError(
            "webdav_scope_unavailable"
        )
    auth_name = (
        f"PocketLab-{node_id[:24]}-"
        f"{backup_id[-8:]}"
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
        timeout=20,
    )
    if created.returncode != 0:
        raise RuntimeError(
            "webdav_credential_creation_failed"
        )
    password = _parse_app_password(
        created.stdout or ""
    )
    listed = _photoprism_command(
        ["auth", "ls", auth_name],
        timeout=15,
    )
    auth_id = (
        _parse_auth_id(
            listed.stdout or "",
            auth_name,
        )
        if listed.returncode == 0
        else ""
    )
    if not password:
        if auth_id:
            _revoke_auth_id(auth_id)
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
            timeout=15,
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
        / f"{credential_ref}.json"
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
    _write_json(
        _credential_path(credential_ref),
        payload,
        mode=0o600,
    )


def _load_credential(
    credential_ref: str,
) -> dict[str, Any] | None:
    path = _credential_path(credential_ref)
    data = _read_json(path, None)
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


def _probe_webdav(
    url: str,
    username: str,
    password: str,
) -> bool:
    if not str(url).startswith("https://"):
        return False
    request = urllib.request.Request(
        url,
        method="PROPFIND",
    )
    request.add_header("Depth", "0")
    request.add_header(
        "Authorization",
        "Basic "
        + base64.b64encode(
            f"{username}:{password}".encode(
                "utf-8"
            )
        ).decode("ascii"),
    )
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
            ) in {200, 207}
    except urllib.error.HTTPError as exc:
        return int(exc.code or 0) == 207
    except Exception:
        return False


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
) -> None:
    ref = _credential_ref_for_job(job)
    if ref:
        data = None
        try:
            data = _load_credential(ref)
        except HTTPException:
            data = None
        if isinstance(data, dict):
            _revoke_auth_id(
                str(data.get("auth_id") or "")
            )
        _delete_credential(ref)
    auth_id = _credential_auth_id_for_job(
        job
    )
    if auth_id:
        _revoke_auth_id(auth_id)


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
                "summary": (
                    "Credential reference does "
                    "not match this backup."
                ),
            },
        )
    capacity = server_capacity()
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
        "destination_prefix": (
            f"PocketLab/{node_id}"
        ),
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
    return server_capacity()


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
        "bytes_total": max(
            0,
            int(
                progress.get("bytes_total")
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
        "storage": server_capacity(),
    }
    if status_value in TERMINAL_STATES:
        bounded["completed_at"] = _now()
        if status_value in {
            "completed",
            "partial_storage_limit",
        }:
            bounded["last_success_at"] = _now()
        _revoke_job_credential(job)
    updated = _update_job(
        backup_id,
        **bounded,
    )
    if status_value in TERMINAL_STATES:
        _append_evidence(
            updated,
            f"lite.photo_backup.{status_value}",
        )
    return _public_job(updated) or {}


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
    if (
        not origin
        or not (
            runtime.get("running")
            and runtime.get("reachable")
        )
        or int(
            capacity.get(
                "hard_upload_budget_bytes"
            )
            or 0
        )
        <= 0
    ):
        failed = _update_job(
            backup_id,
            status="destination_unavailable",
            summary=(
                "PhotoPrism backup destination "
                "is not ready."
            ),
            retryable=True,
            reason_code=(
                "destination_unavailable"
            ),
            completed_at=_now(),
            storage=capacity,
        )
        _append_evidence(
            failed,
            "lite.photo_backup."
            "destination_unavailable",
        )
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
                "webdav_readiness_failed"
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

        await BUS.publish_json(
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
                "sanitized": True,
            },
            trace_id=backup_id,
        )
        return _public_job(job) or {}
    except Exception:
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
                "destination_unavailable"
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
    _revoke_job_credential(job)
    _update_job(
        backup_id,
        status="cancelling",
        summary=(
            "Stopping photo backup safely."
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
                _revoke_job_credential(job)
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
                count += 1
        _save_state(payload)
    return count


def cleanup_expired_credentials() -> int:
    root = _credential_dir()
    if not root.exists():
        return 0
    removed = 0
    for path in root.glob(
        "cred-*.json"
    ):
        data = _read_json(path, {})
        if (
            not isinstance(data, dict)
            or float(
                data.get(
                    "expires_at_epoch"
                )
                or 0
            )
            <= _epoch()
        ):
            if isinstance(data, dict):
                _revoke_auth_id(
                    str(
                        data.get(
                            "auth_id"
                        )
                        or ""
                    )
                )
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed
