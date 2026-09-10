from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import deps
from . import lite_backup_manifest
from .lite_backup_policy import (
    backup_layout,
    backup_scope,
    iter_state_sources,
    is_excluded_media_path,
    public_repository_label,
)

_BACKUP_OPERATION_LOCK = threading.Lock()
_SAFE_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_MAX_PREVIEW_CHANGE_SAMPLE = 500


@dataclass(frozen=True)
class _StagingInventory:
    records_path: Path
    source_count: int
    file_count: int
    size_bytes: int
    included_sets: frozenset[str]

    def load_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self.records_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise RuntimeError("Backup staging inventory is invalid") from exc
                if not isinstance(item, dict):
                    raise RuntimeError("Backup staging inventory is invalid")
                records.append(item)
        if len(records) != self.file_count:
            raise RuntimeError("Backup staging inventory count does not match its records")
        return records


def _safe_restore_validation_checks(
    service_restart: dict[str, Any],
    health_validation: dict[str, Any],
    application_validation: dict[str, Any],
) -> dict[str, Any]:
    """Return bounded post-restore checks without URLs, paths or raw errors."""
    return {
        "service_restart_status": str(service_restart.get("status") or "unknown")[:40],
        "health_status": str(health_validation.get("status") or "unknown")[:40],
        "health_http_status": int(health_validation.get("http_status") or 0),
        "health_read_degraded": bool(health_validation.get("read_degraded")),
        "health_degraded_reason": str(health_validation.get("degraded_reason") or "")[:80],
        "application_status": str(application_validation.get("status") or "unknown")[:40],
        "application_running": bool(application_validation.get("running")),
        "application_reachable": bool(application_validation.get("reachable")),
        "application_attempt_count": int(application_validation.get("attempt_count") or 0),
        "sanitized": True,
    }


class RestoreValidationError(RuntimeError):
    """A post-restore validation failure with safe diagnostic checks."""

    def __init__(self, checks: dict[str, Any]):
        super().__init__("Post-restore health validation failed")
        self.safe_checks = _safe_restore_validation_checks(
            checks.get("service_restart") or {},
            checks.get("health_validation") or {},
            checks.get("application_validation") or {},
        )


def _preview_checksum(preview: dict[str, Any]) -> str:
    payload = {key: value for key, value in preview.items() if key != "preview_checksum"}
    return lite_backup_manifest.canonical_checksum(payload)


def _utc() -> str:
    return deps.now_utc_iso()


def _state_file() -> Path:
    return deps.settings().state_dir / "backup_state.json"


def _read_backup_state() -> dict[str, Any]:
    try:
        payload = deps.core.read_json_file(_state_file(), {})
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _write_backup_state(payload: dict[str, Any]) -> None:
    current = _read_backup_state()
    current.update(payload)
    current["updated_at"] = _utc()
    deps.core.write_json_file(_state_file(), current)
    _touch_recovery_projection()


def _touch_recovery_projection() -> None:
    """Wake prepared Recovery projections after a backend-owned transition."""
    try:
        from . import lite_recovery_subprojections

        lite_recovery_subprojections.invalidate_recovery_subprojections()
    except Exception:
        pass
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        CONTROL_PLANE.invalidate_domain("recovery")
    except Exception:
        pass


def record_backup_request(command: dict[str, Any]) -> dict[str, Any]:
    backup_id = _command_id(command)
    requested_at = _utc()
    pending = {
        "backup_id": backup_id,
        "status": "queued",
        "requested_at": requested_at,
        "reason": command.get("reason") or "manual backup",
        "include_app_data": bool(command.get("include_app_data", True)),
        "include_event_journal": bool(command.get("include_event_journal", True)),
        "summary": "Backup request queued. The worker will initialize the encrypted repository if needed and then create the backup.",
    }
    _write_backup_state({"pending_backup": pending})
    return pending


def pending_backup() -> dict[str, Any] | None:
    pending = _read_backup_state().get("pending_backup")
    return pending if isinstance(pending, dict) else None


def _api_pending_backup(pending: dict[str, Any]) -> dict[str, Any]:
    return {
        "backup_id": pending.get("backup_id"),
        "status": pending.get("status") or "queued",
        "created_at": pending.get("requested_at"),
        "engine": "restic",
        "verification_status": "not_verified",
        "risk_level": "low",
        "included_sets": [],
        "included_file_count": 0,
        "summary": pending.get("summary") or "Backup request queued.",
        "pending": True,
    }


def _command_id(command: dict[str, Any]) -> str:
    value = str(
        command.get("command_id")
        or command.get("job_id")
        or command.get("trace_id")
        or uuid.uuid4().hex
    ).strip()
    if not _SAFE_OPERATION_ID.fullmatch(value):
        raise RuntimeError("Recovery operation identifier is invalid")
    return value


def _existing_backup_result(backup_id: str) -> dict[str, Any] | None:
    """Return a completed restore point for an idempotent command retry.

    JetStream may redeliver a command after the domain work completed but
    before the acknowledgement was durably observed.  A manifest is written
    only after the encrypted restic snapshot and all required component
    staging have completed, so it is the durable completion marker for backup
    creation.  Reusing it prevents a retry from creating a second snapshot
    under the same public backup id.
    """
    manifest = lite_backup_manifest.read_manifest(backup_id)
    if not isinstance(manifest, dict) or not str(manifest.get("snapshot_id") or ""):
        return None
    if str(manifest.get("status") or "").strip().lower() not in {"created", "verified"}:
        return None
    receipt = lite_backup_manifest.read_receipt(backup_id) or {
        "backup_id": backup_id,
        "created_at": manifest.get("created_at"),
        "status": "succeeded",
        "summary": "Evidence saved",
        "engine": manifest.get("engine") or "restic",
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest_checksum": manifest.get("manifest_checksum"),
        "evidence_saved": True,
    }
    return {
        "status": "succeeded",
        "backup_id": backup_id,
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest": lite_backup_manifest.api_manifest(manifest),
        "receipt": lite_backup_manifest.api_receipt(receipt),
        "summary": manifest.get("summary") or "Existing backup restore point reused.",
        "idempotent_replay": True,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _restic_binary() -> str | None:
    return shutil.which(os.environ.get("POCKETLAB_RESTIC_BIN", "restic"))


def _run_restic(
    args: list[str],
    *,
    env: dict[str, str],
    timeout: int = 180,
    cwd: Path | None = None,
    capture_stdout: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def _ensure_password_file(password_file: Path) -> None:
    if password_file.exists():
        try:
            password_file.chmod(0o600)
        except Exception:
            pass
        return
    password_file.parent.mkdir(parents=True, exist_ok=True)
    password_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    try:
        password_file.chmod(0o600)
    except Exception:
        pass


def _restic_env(layout: Any) -> dict[str, str]:
    env = dict(os.environ)
    env["RESTIC_REPOSITORY"] = str(layout.repository)
    env["RESTIC_PASSWORD_FILE"] = str(layout.password_file)
    return env


def _restic_repo_initialized(layout: Any) -> bool:
    return (layout.repository / "config").exists()


def repository_readiness() -> dict[str, Any]:
    layout = backup_layout()
    layout.ensure()
    restic = _restic_binary()
    initialized = _restic_repo_initialized(layout)
    latest = lite_backup_manifest.latest_manifest()
    ready = bool(restic and initialized)
    if ready:
        status = "healthy"
        summary = "Recovery Ready"
    elif restic and not initialized:
        status = "degraded"
        summary = "Backup folder is ready, but the encrypted repository has not been initialized yet."
    else:
        status = "unavailable"
        summary = "Restic is not installed yet. Install restic to create encrypted local backups."
    return {
        "status": status,
        "ready": ready,
        "summary": summary,
        "engine": "restic",
        "restic_available": bool(restic),
        "repository_initialized": initialized,
        "repository": {
            "type": "local",
            "engine": "restic",
            "encrypted": True,
            "ready": ready,
            "location": public_repository_label(layout),
            "details": {"label": "Backend-managed encrypted repository"},
        },
        "latest_backup_id": latest.get("backup_id") if latest else None,
        "checked_at": _utc(),
    }


def recovery_status(*, history_limit: int = 25) -> dict[str, Any]:
    readiness = repository_readiness()
    backups = [
        lite_backup_manifest.api_manifest(item)
        for item in lite_backup_manifest.list_manifests(limit=max(1, min(int(history_limit or 1), 25)))
    ]
    latest = backups[0] if backups else None
    pending = pending_backup() if not latest else None
    scope = backup_scope()
    status = readiness["status"]
    if latest and readiness.get("restic_available"):
        status = "healthy"
    elif pending:
        status = "degraded"
    summary = (
        "Recovery Ready"
        if latest
        else (pending.get("summary") if pending else readiness.get("summary"))
        or "Needs Attention"
    )
    state = _read_backup_state()
    return {
        "status": status,
        "summary": summary,
        "repository": readiness["repository"],
        "repository_readiness": readiness,
        "what_will_be_backed_up": scope["included"],
        "what_will_not_be_backed_up": scope["excluded_sensitive"]
        + scope["excluded_runtime"],
        "conditional_items": scope["conditional"],
        "last_backup": latest,
        "last_backup_time": latest.get("created_at") if latest else None,
        "last_verification_result": (latest or {}).get("verification_status")
        or "not_verified",
        "available_restore_points": backups,
        "backup_history": backups,
        "pending_backup": _api_pending_backup(pending) if pending else None,
        "restore_risk": "low" if latest else "none",
        "pre_restore_checkpoint": state.get("pre_restore_checkpoint")
        or {
            "status": "not_created",
            "summary": "A checkpoint will be created automatically before restore changes local state.",
        },
        "latest_restore_preview": state.get("latest_restore_preview"),
        "last_restore": state.get("last_restore"),
        "actions": ["backup_now"]
        + (["verify_backup", "preview_restore"] if latest else [])
        + (["restore_latest"] if state.get("latest_restore_preview", {}).get("status") == "ready" else []),
        "planned_actions": [],
        "updated_at": _utc(),
    }


def _compact_backup_summary(backup: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(backup, dict):
        return None
    allowed = (
        "backup_id",
        "created_at",
        "engine",
        "included_file_count",
        "verification_status",
        "verified_at",
        "risk_level",
        "summary",
        "pending",
        "status",
        "size_bytes",
    )
    return {key: backup.get(key) for key in allowed if backup.get(key) is not None}


def _compact_restore_preview(preview: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(preview, dict):
        return None
    allowed = (
        "preview_id",
        "backup_id",
        "status",
        "created_at",
        "change_count",
        "included_components",
        "excluded_components",
        "restore_allowed",
        "requires_confirmation",
        "destructive_changes_applied",
        "summary",
    )
    return {key: preview.get(key) for key in allowed if preview.get(key) is not None}


def _safe_preview_scope_labels(value: Any) -> list[str]:
    """Return bounded, manifest-owned labels for the operator preview."""
    if not isinstance(value, list):
        return []
    return [
        label
        for item in value[:64]
        if isinstance(item, str)
        for label in [item.strip()[:200]]
        if label
    ]


def _compact_restore_summary(restore: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(restore, dict):
        return None
    allowed = (
        "restore_id",
        "backup_id",
        "preview_id",
        "status",
        "state",
        "phase",
        "created_at",
        "updated_at",
        "completed_at",
        "restored_file_count",
        "rollback_available",
        "summary",
    )
    return {key: restore.get(key) for key in allowed if restore.get(key) is not None}


def recovery_summary() -> dict[str, Any]:
    readiness = repository_readiness()
    latest_manifest = lite_backup_manifest.latest_manifest()
    latest = lite_backup_manifest.api_manifest(latest_manifest) if latest_manifest else None
    pending = pending_backup()
    current = _compact_backup_summary(latest)
    current_operation = _compact_backup_summary(_api_pending_backup(pending)) if pending else None
    state = _read_backup_state()
    latest_preview = _compact_restore_preview(state.get("latest_restore_preview"))
    checkpoint = state.get("pre_restore_checkpoint") if isinstance(state.get("pre_restore_checkpoint"), dict) else None
    last_restore = _compact_restore_summary(state.get("last_restore"))
    latest_verified = str((current or {}).get("verification_status") or "") == "verified"
    status = "healthy" if current and readiness.get("restic_available") else readiness.get("status", "degraded")
    if pending:
        status = str(current_operation.get("status") or "working")
    recommended_action = (
        "manage_recovery"
        if pending
        else "preview_restore"
        if latest_verified and not latest_preview
        else "verify_backup"
        if current and not latest_verified
        else "backup_now"
        if not current
        else "manage_recovery"
    )
    recent_activity = []
    if current:
        recent_activity.append({
            "id": current.get("backup_id"),
            "kind": "backup",
            "status": current.get("verification_status") or current.get("status") or "saved",
            "summary": "Backup verified" if latest_verified else current.get("summary") or "Backup saved",
            "occurred_at": current.get("verified_at") or current.get("created_at"),
        })
    if last_restore:
        recent_activity.append({
            "id": last_restore.get("restore_id"),
            "kind": "restore",
            "status": last_restore.get("status") or last_restore.get("state") or "recorded",
            "summary": last_restore.get("summary") or "Restore recorded",
            "occurred_at": last_restore.get("completed_at") or last_restore.get("updated_at"),
        })
    return {
        "view_model": "recovery-summary-r3-v1",
        "status": status,
        "summary": (current_operation or {}).get("summary") if pending else "Recovery Ready" if current else readiness.get("summary") or "Needs Attention",
        "repository": {
            "type": readiness.get("repository", {}).get("type"),
            "engine": readiness.get("repository", {}).get("engine"),
            "encrypted": bool(readiness.get("repository", {}).get("encrypted")),
            "ready": bool(readiness.get("repository", {}).get("ready")),
            "location": readiness.get("repository", {}).get("location"),
        },
        "last_backup": current,
        "latest_backup": current,
        "last_verification_result": (current or {}).get("verification_status") or "not_verified",
        "latest_restore_preview": latest_preview,
        "pre_restore_checkpoint": checkpoint,
        "last_restore": last_restore,
        "current_operation": current_operation,
        "recommended_action": recommended_action,
        "recent_activity": recent_activity[:3],
        "live": bool(pending),
        "updated_at": str(
            state.get("updated_at")
            or (last_restore or {}).get("updated_at")
            or (last_restore or {}).get("completed_at")
            or (latest_preview or {}).get("created_at")
            or (current or {}).get("verified_at")
            or (current or {}).get("created_at")
            or ""
        ),
        "sanitized": True,
    }


def recovery_details() -> dict[str, Any]:
    return recovery_status(history_limit=3)


def _copy_sources_to_staging(
    backup_id: str,
    staging_root: Path,
    *,
    include_event_journal: bool = True,
) -> _StagingInventory:
    inventory_path = staging_root / "backup-metadata" / "included-files.jsonl"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    source_count = 0
    file_count = 0
    size_bytes = 0
    included_sets: set[str] = set()

    def write_record(handle: Any, item: dict[str, Any]) -> None:
        handle.write(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n")

    with inventory_path.open("w", encoding="utf-8") as inventory:
        for item in iter_state_sources(include_event_journal=include_event_journal):
            src = Path(item["path"])
            state_dir = deps.settings().state_dir
            if src.is_symlink() or not src.is_file() or not _is_within_path(src, state_dir) or is_excluded_media_path(src):
                raise RuntimeError("Backup source is not a registered safe application state path")
            rel = Path(str(item["relative_path"]).lstrip("/"))
            dest = staging_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            record = {
                "set": item.get("set") or "Lite runtime state",
                "source": str(item.get("relative_path") or rel),
                "relative_path": str(rel),
                "size_bytes": dest.stat().st_size,
                "sha256": _sha256(dest),
            }
            write_record(inventory, record)
            source_count += 1
            file_count += 1
            size_bytes += int(record["size_bytes"])
            included_sets.add(str(record["set"]))
    metadata_path = staging_root / "backup-metadata" / "scope.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "backup_id": backup_id,
        "created_at": _utc(),
        "source_count": source_count,
        "include_event_journal": include_event_journal,
        "scope": backup_scope(include_event_journal=include_event_journal),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    metadata_record = {
        "set": "Backup metadata",
        "source": "backup-metadata/scope.json",
        "relative_path": "backup-metadata/scope.json",
        "size_bytes": metadata_path.stat().st_size,
        "sha256": _sha256(metadata_path),
    }
    with inventory_path.open("a", encoding="utf-8") as inventory:
        write_record(inventory, metadata_record)
    file_count += 1
    size_bytes += int(metadata_record["size_bytes"])
    included_sets.add("Backup metadata")
    return _StagingInventory(
        records_path=inventory_path,
        source_count=source_count,
        file_count=file_count,
        size_bytes=size_bytes,
        included_sets=frozenset(included_sets),
    )


def _copy_database_backup_to_staging(
    database_backup_id: str, staging_root: Path
) -> list[dict[str, Any]]:
    from . import lite_database_recovery

    package = lite_database_recovery.database_backup_package(database_backup_id)
    if not package.is_dir():
        raise RuntimeError("Verified database backup package was not created")
    copied: list[dict[str, Any]] = []
    for source in sorted(package.rglob("*")):
        if not source.is_file():
            continue
        relative = Path("database-backup") / source.relative_to(package)
        target = staging_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(
            {
                "set": "Pocket Lab database",
                "source": str(relative),
                "relative_path": str(relative),
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )
    return copied


def _copy_application_backup_to_staging(staging_root: Path) -> dict[str, Any]:
    """Stage registered application metadata through its service adapter."""
    from . import lite_photoprism_backup

    result = lite_photoprism_backup.create_application_backup(staging_root)
    records = result.get("records") if isinstance(result.get("records"), list) else []
    return {
        "status": str(result.get("status") or "not_present"),
        "records": [item for item in records if isinstance(item, dict)],
        "components": result.get("components") if isinstance(result.get("components"), dict) else {},
        "summary": str(result.get("summary") or "Application metadata was not present.")[:240],
    }


def _record_backup_failure(
    backup_id: str,
    *,
    reason: str,
    include_app_data: bool,
    include_event_journal: bool = True,
    error: str,
) -> None:
    safe_error = _safe_backend_error(error)
    failed_at = _utc()
    _write_backup_state(
        {
            "pending_backup": {
                "backup_id": backup_id,
                "status": "failed",
                "requested_at": _read_backup_state().get("pending_backup", {}).get("requested_at") or failed_at,
                "completed_at": failed_at,
                "reason": reason,
                "include_app_data": include_app_data,
                "include_event_journal": include_event_journal,
                "summary": "Backup failed. See recovery details and worker evidence for the exact error.",
                "error": safe_error,
            },
            "last_backup_error": {
                "backup_id": backup_id,
                "status": "failed",
                "failed_at": failed_at,
                "error": safe_error,
            },
            "updated_at": failed_at,
        }
    )


def _parse_snapshot_id(stdout: str) -> str | None:
    snapshot_id: str | None = None
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            value = payload.get("snapshot_id") or payload.get("id")
            if value:
                snapshot_id = str(value)
        elif "snapshot" in text.lower():
            parts = text.replace(".", " ").split()
            for part in parts:
                if len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
                    snapshot_id = part
                    break
    return snapshot_id


def _restic_snapshot_id_for_backup(
    restic: str,
    backup_id: str,
    env: dict[str, str],
) -> str:
    """Resolve the committed snapshot without buffering backup progress output."""
    result = _run_restic(
        [restic, "snapshots", "--json", "--tag", f"backup-id={backup_id}"],
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"restic snapshot lookup failed: {_safe_restic_error(result)}")
    try:
        payload = json.loads(str(result.stdout or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("restic snapshot lookup returned invalid metadata") from exc
    if not isinstance(payload, list):
        raise RuntimeError("restic snapshot lookup returned invalid metadata")
    for item in payload:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags")
        if isinstance(tags, list) and f"backup-id={backup_id}" not in {str(tag) for tag in tags}:
            continue
        snapshot_id = str(item.get("id") or "").strip()
        if snapshot_id:
            return snapshot_id
    raise RuntimeError("restic backup completed without a committed snapshot id")



def _safe_restic_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (str(result.stderr or "").strip() or str(result.stdout or "").strip() or "restic command failed").strip()
    return _safe_backend_error(text)


def _safe_backend_error(error: Exception | str) -> str:
    text = str(error or "protected backend operation failed").strip()
    lowered = text.lower()
    if any(marker in lowered for marker in (
        "/data/", "/storage/", "/home/", "password", "token", "secret", "private key",
        "nats://", "--repository", "--password-file", "restic_password", "mysql_pwd",
    )):
        return "Protected backend operation failed. Review Recovery diagnostics."
    return text[:240] + ("..." if len(text) > 240 else "")


def _load_verified_manifest(backup_id: str) -> tuple[str, dict[str, Any]]:
    resolved = lite_backup_manifest.resolve_backup_id(backup_id)
    if not resolved:
        raise FileNotFoundError("Backup was not found.")
    manifest = lite_backup_manifest.read_manifest(resolved)
    if not manifest:
        raise FileNotFoundError("Backup manifest was not found.")
    format_version = int(manifest.get("format_version") or 1)
    if format_version < 1 or format_version > 2:
        raise RuntimeError("Backup manifest format is not supported by this Pocket Lab version.")
    return resolved, manifest


def _current_recovery_target_revision() -> int:
    try:
        from .lite_semantic_revisions import recovery_target_revision

        return int(recovery_target_revision())
    except Exception:
        return 0


def _restic_snapshot_exists(restic: str, snapshot_id: str, env: dict[str, str]) -> dict[str, Any]:
    result = _run_restic([restic, "snapshots", "--json", snapshot_id], env=env, timeout=120)
    if result.returncode != 0:
        return {"name": "restic snapshot lookup", "status": "failed", "summary": _safe_restic_error(result)}
    try:
        payload = json.loads(result.stdout or "[]")
    except Exception:
        payload = []
    found = False
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and str(item.get("id") or item.get("short_id") or "").startswith(snapshot_id[:8]):
                found = True
                break
    return {
        "name": "restic snapshot lookup",
        "status": "passed" if found else "failed",
        "summary": "Snapshot is present in the encrypted repository." if found else "Snapshot was not found in the encrypted repository.",
    }


def _restic_repository_check(restic: str, env: dict[str, str]) -> dict[str, Any]:
    result = _run_restic([restic, "check", "--json"], env=env, timeout=300)
    return {
        "name": "restic repository check",
        "status": "passed" if result.returncode == 0 else "failed",
        "summary": "Repository metadata check passed." if result.returncode == 0 else _safe_restic_error(result),
    }


def _manifest_component_check(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate the safe component contract without exposing staged paths."""
    components = manifest.get("component_results")
    if not isinstance(components, dict):
        return {
            "name": "component validation",
            "status": "failed" if int(manifest.get("format_version") or 1) >= 2 else "passed",
            "summary": "Required component validation metadata is missing." if int(manifest.get("format_version") or 1) >= 2 else "Legacy backup has no component validation metadata.",
        }
    failures = [
        name
        for name, result in components.items()
        if isinstance(result, dict)
        # ``repository_integrity`` is derived by this verifier after the
        # component checks run.  It may contain the previous verification
        # result, so treating it as an input component makes a failed
        # verification permanently non-retryable.
        and name != "repository_integrity"
        and result.get("required") is True
        and result.get("status") not in {"validated", "not_present"}
    ]
    safe_files = True
    for item in manifest.get("included_files") or []:
        if not isinstance(item, dict):
            safe_files = False
            break
        relative = str(item.get("relative_path") or item.get("source") or "").lstrip("/")
        if relative.startswith("application/"):
            safe_files = relative in {
                "application/photoprism/metadata.sqlite3",
                "application/photoprism/configuration.json",
            } and bool(re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256") or "")))
            if not safe_files:
                break
    return {
        "name": "component validation",
        "status": "passed" if not failures and safe_files else "failed",
        "summary": "Required backup components and safe artifact records are validated." if not failures and safe_files else "A required backup component or artifact record is invalid.",
    }


def verify_backup(backup_id: str = "latest", *, reason: str | None = None) -> dict[str, Any]:
    resolved, manifest = _load_verified_manifest(backup_id)
    layout = backup_layout()
    layout.ensure()
    restic = _restic_binary()
    if not restic:
        raise RuntimeError("restic is required for backup verification but was not found in PATH")
    snapshot_id = str(manifest.get("snapshot_id") or "").strip()
    if not snapshot_id:
        raise RuntimeError("Backup manifest does not include a restic snapshot id")
    stored_checksum = str(manifest.get("manifest_checksum") or "")
    computed_checksum = lite_backup_manifest.canonical_checksum(manifest)
    checksum_ok = bool(stored_checksum and computed_checksum == stored_checksum)
    env = _restic_env(layout)
    checks = [
        {
            "name": "manifest checksum",
            "status": "passed" if checksum_ok else "failed",
            "summary": "Manifest checksum matches the saved evidence." if checksum_ok else "Manifest checksum does not match the saved evidence.",
        },
        _restic_snapshot_exists(restic, snapshot_id, env),
        _restic_repository_check(restic, env),
        _manifest_component_check(manifest),
    ]
    status = "verified" if all(check.get("status") == "passed" for check in checks) else "failed"
    verified_at = _utc()
    manifest = dict(manifest)
    manifest["verification_status"] = status
    manifest["status"] = status
    manifest["restorable"] = status == "verified"
    manifest["verified_at"] = verified_at if status == "verified" else None
    manifest["verification"] = {
        "status": status,
        "checked_at": verified_at,
        "reason": reason or "manual verification",
        "checks": checks,
        "previous_manifest_checksum": stored_checksum,
    }
    components = dict(manifest.get("component_results") or {})
    components["repository_integrity"] = {"status": "validated" if status == "verified" else "failed", "required": True}
    manifest["component_results"] = components
    manifest["summary"] = "Backup verified and ready for restore preview." if status == "verified" else "Backup verification failed. Review checks before restore."
    manifest = lite_backup_manifest.write_manifest(manifest)
    receipt = lite_backup_manifest.read_receipt(resolved) or {"backup_id": resolved}
    receipt.update(
        {
            "backup_id": resolved,
            "verification_status": status,
            "verified_at": verified_at if status == "verified" else None,
            "verification_checks": checks,
            "manifest_checksum": manifest.get("manifest_checksum"),
        }
    )
    lite_backup_manifest.write_receipt(resolved, receipt)
    _write_backup_state({
            "latest_backup_id": resolved,
            "latest_snapshot_id": snapshot_id,
            "pending_backup": None,
            "last_verification": {
                "backup_id": resolved,
                "status": status,
                "checked_at": verified_at,
                "checks": checks,
            },
            "updated_at": verified_at,
            "manifest": str(lite_backup_manifest.manifest_path(resolved)),
            "receipt": str(lite_backup_manifest.receipt_path(resolved)),
        })
    return {
        "status": status,
        "backup_id": resolved,
        "snapshot_id": snapshot_id,
        "verified_at": verified_at if status == "verified" else None,
        "checks": checks,
        "manifest_checksum": manifest.get("manifest_checksum"),
        "summary": manifest.get("summary"),
    }


def _parse_restic_ls(stdout: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("struct_type") == "node" or payload.get("type") in {"file", "dir"}:
            path = str(payload.get("path") or "").lstrip("/")
            if path:
                items.append(
                    {
                        "path": path,
                        "type": payload.get("type") or "unknown",
                        "size_bytes": payload.get("size"),
                    }
                )
    return items


def _count_restic_ls_items(stdout: str) -> int:
    """Count restic's newline-delimited listing without hydrating every item."""
    if not stdout:
        return 0
    return stdout.count("\n") + (0 if stdout.endswith("\n") else 1)


def _target_for_backup_path(relative_path: str) -> Path | None:
    rel = Path(str(relative_path or "").lstrip("/"))
    parts = rel.parts
    if not parts:
        return None
    if parts[0] == "state":
        return deps.settings().state_dir.joinpath(*parts[1:]) if len(parts) > 1 else deps.settings().state_dir
    if str(relative_path).lstrip("/") in {
        "application/photoprism/metadata.sqlite3",
        "application/photoprism/configuration.json",
    }:
        from . import lite_photoprism_backup

        try:
            _root, config, database = lite_photoprism_backup._registered_paths()
        except Exception:
            return None
        return database if rel.name == "metadata.sqlite3" else config
    return None


def _friendly_backup_target(relative_path: str, target: Path | None) -> str:
    rel = str(relative_path or "").lstrip("/")
    if rel == "application/photoprism/metadata.sqlite3":
        return "PhotoPrism application metadata"
    if rel == "application/photoprism/configuration.json":
        return "PhotoPrism safe configuration"
    if rel.startswith("state/"):
        return "Pocket Lab settings"
    if rel.startswith("backup-metadata/"):
        return "Backup metadata"
    return "Registered application state" if target else "Backup metadata"


def restore_preview_path(preview_id: str) -> Path:
    return backup_layout().restore_previews / f"{preview_id}.json"


def get_restore_preview(preview_id: str) -> dict[str, Any] | None:
    path = restore_preview_path(preview_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def validate_restore_preview_binding(preview: dict[str, Any]) -> dict[str, Any]:
    """Validate the immutable manifest/target revision binding before mutation."""
    backup_id = str(preview.get("backup_id") or "").strip()
    if not backup_id:
        raise RuntimeError("Restore preview does not identify a backup")
    resolved, manifest = _load_verified_manifest(backup_id)
    if manifest.get("verification_status") != "verified" or not manifest.get("restorable", True):
        raise RuntimeError("Backup must be verified before restore")
    if str(preview.get("backup_manifest_checksum") or "") != str(manifest.get("manifest_checksum") or ""):
        raise RuntimeError("Restore preview is bound to a different backup manifest")
    if str(preview.get("snapshot_id") or "") != str(manifest.get("snapshot_id") or ""):
        raise RuntimeError("Restore preview snapshot does not match the backup manifest")
    expected_checksum = str(preview.get("preview_checksum") or "")
    if expected_checksum and _preview_checksum(preview) != expected_checksum:
        raise RuntimeError("Restore preview checksum does not match the saved preview")
    if int(preview.get("target_revision") or 0) != _current_recovery_target_revision():
        raise RuntimeError("Restore preview is stale. Create a new preview before restoring.")
    return {"backup_id": resolved, "manifest": manifest}


def create_restore_preview(backup_id: str = "latest", *, reason: str | None = None) -> dict[str, Any]:
    resolved, manifest = _load_verified_manifest(backup_id)
    snapshot_id = str(manifest.get("snapshot_id") or "").strip()
    if not snapshot_id:
        raise RuntimeError("Backup manifest does not include a restic snapshot id")
    layout = backup_layout()
    layout.ensure()
    restic = _restic_binary()
    if not restic:
        raise RuntimeError("restic is required for restore preview but was not found in PATH")
    result = _run_restic([restic, "ls", snapshot_id, "--json"], env=_restic_env(layout), timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"restic restore preview failed: {_safe_restic_error(result)}")
    restic_item_count = _count_restic_ls_items(result.stdout)
    included = manifest.get("included_files") or []
    changes: list[dict[str, Any]] = []
    # Preview is an operator-facing diff, not a second full restore walk. A
    # full restore point may contain thousands of registered state files; on
    # Termux, checking every target path here can monopolize the worker for
    # minutes. Preserve the total count while inspecting only a bounded,
    # representative sample for friendly UI details.
    for item in included[:_MAX_PREVIEW_CHANGE_SAMPLE]:
        rel = str(item.get("relative_path") or item.get("source") or "")
        target = _target_for_backup_path(rel)
        current_exists = bool(target and target.exists())
        action = "would_overwrite" if current_exists else "would_create"
        if rel.startswith("backup-metadata/"):
            action = "metadata_only"
        changes.append(
            {
                "relative_path": rel,
                "set": item.get("set") or "Lite runtime state",
                "action": action,
                "current_exists": current_exists,
                "target": _friendly_backup_target(rel, target),
                "backup_size_bytes": item.get("size_bytes"),
            }
        )
    preview_id = f"preview-{resolved}-{uuid.uuid4().hex[:12]}"
    created_at = _utc()
    verified = manifest.get("verification_status") == "verified"
    included_components = _safe_preview_scope_labels(
        manifest.get("included_components") or manifest.get("included_sets")
    )
    excluded_components = _safe_preview_scope_labels(
        manifest.get("excluded_components") or manifest.get("excluded_runtime_items")
    )
    preview = {
        "preview_id": preview_id,
        "backup_id": resolved,
        "snapshot_id": snapshot_id,
        "format_version": 2,
        "backup_manifest_checksum": manifest.get("manifest_checksum"),
        "target_revision": 0,
        "created_at": created_at,
        "status": "ready" if verified else "needs_verification",
        "restore_allowed": bool(verified),
        "restore_supported": True,
        "verification_status": manifest.get("verification_status", "not_verified"),
        "reason": reason or "manual restore preview",
        "summary": "Preview ready. Restore can run only after explicit confirmation and an automatic checkpoint." if verified else "Preview created, but backup must be verified before restore can be enabled.",
        "change_count": len(included),
        "changes": changes,
        "changes_truncated": len(included) > len(changes),
        "change_sample_limit": _MAX_PREVIEW_CHANGE_SAMPLE,
        "restic_item_count": restic_item_count,
        "included_components": included_components,
        "excluded_components": excluded_components,
        "sensitive_items_excluded": manifest.get("excluded_sensitive_items", []),
        "warnings": [
            "Restore execution is not performed by this preview.",
            "A pre-restore checkpoint will be created before any state file is changed.",
            "Raw secrets remain excluded from this restore point.",
        ],
    }
    preview["preview_checksum"] = _preview_checksum(preview)
    path = restore_preview_path(preview_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    _write_backup_state({
            "latest_backup_id": resolved,
            "latest_snapshot_id": snapshot_id,
            "pending_backup": None,
            "latest_restore_preview": {
                "preview_id": preview_id,
                "backup_id": resolved,
                "status": preview["status"],
                "created_at": created_at,
                "change_count": len(included),
                "included_components": included_components,
                "excluded_components": excluded_components,
            },
            "updated_at": created_at,
            "manifest": str(lite_backup_manifest.manifest_path(resolved)),
            "restore_preview": str(path),
        })
    # The preview record itself is a Recovery lifecycle event. Bind after that
    # commit so a freshly-created preview is not stale immediately.
    preview["target_revision"] = _current_recovery_target_revision()
    preview["preview_checksum"] = _preview_checksum(preview)
    path.write_text(json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return preview


def restore_checkpoint_path(checkpoint_id: str) -> Path:
    if not _SAFE_OPERATION_ID.fullmatch(str(checkpoint_id or "")):
        raise ValueError("invalid checkpoint id")
    return backup_layout().restore_checkpoints / f"{checkpoint_id}.json"


def restore_run_path(restore_id: str) -> Path:
    if not _SAFE_OPERATION_ID.fullmatch(str(restore_id or "")):
        raise ValueError("invalid restore id")
    return backup_layout().restore_runs / f"{restore_id}.json"


def get_restore_checkpoint(checkpoint_id: str) -> dict[str, Any] | None:
    path = restore_checkpoint_path(checkpoint_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def get_restore_run(restore_id: str) -> dict[str, Any] | None:
    path = restore_run_path(restore_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _is_within_path(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _safe_restore_error(error: Exception | str) -> str:
    return _safe_backend_error(error).replace("Protected backend operation failed. Review Recovery diagnostics.", "Restore failed during a protected backend operation.")


def _manifest_file_by_relative_path(manifest: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
    wanted = str(relative_path or "").lstrip("/")
    for item in manifest.get("included_files") or []:
        if str(item.get("relative_path") or item.get("source") or "").lstrip("/") == wanted:
            return item
    return None


def _prepare_full_restore_inputs(
    manifest: dict[str, Any], restore_root: Path
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]:
    """Bind a format-2 restore to its staged canonical database package.

    The selected full restore is complete only when the database package and
    every registered state file are present in the same restic snapshot.  The
    database recovery service performs the final path, checksum, schema, and
    transaction validation; this helper only constructs its backend-owned
    staging input and never exposes it to the browser.
    """
    if int(manifest.get("format_version") or 1) < 2:
        raise RuntimeError("Selected restore point uses an unsupported incomplete restore format")
    database_component = manifest.get("database_backup")
    if not isinstance(database_component, dict) or not database_component.get("backup_id"):
        raise RuntimeError("Selected restore point does not contain the canonical database backup")
    raw_package = restore_root / "database-backup"
    if raw_package.is_symlink():
        raise RuntimeError("Selected restore point contains an unsafe database package symlink")
    package = raw_package.resolve()
    staging_root = backup_layout().staging.resolve()
    try:
        package.relative_to(staging_root)
    except ValueError as exc:
        raise RuntimeError("Selected restore staging path is outside the registered backup staging root") from exc
    if package.name != "database-backup" or not package.is_dir():
        raise RuntimeError("Selected restore point database package is missing")

    state_files: list[dict[str, Any]] = []
    application_records: list[dict[str, Any]] = []
    for item in manifest.get("included_files") or []:
        if not isinstance(item, dict):
            raise RuntimeError("Selected restore manifest contains an invalid file record")
        relative = str(item.get("relative_path") or item.get("source") or "").lstrip("/")
        if relative.startswith("application/"):
            application_records.append(item)
            continue
        if not relative.startswith("state/"):
            continue
        raw_source = restore_root / Path(relative)
        if raw_source.is_symlink():
            raise RuntimeError("Selected restore point contains an unsafe state symlink")
        source = raw_source.resolve()
        try:
            source.relative_to(restore_root.resolve())
        except ValueError as exc:
            raise RuntimeError("Selected restore file escapes the isolated staging root") from exc
        if not source.is_file() or source.is_symlink():
            raise RuntimeError("Selected restore point is missing a registered state file")
        expected_sha = str(item.get("sha256") or "")
        if not expected_sha:
            raise RuntimeError("Selected restore state file checksum does not match the manifest")
        # The canonical database recovery service revalidates every staged
        # state-file checksum immediately before it creates the restore
        # journal. Avoid hashing the full registered evidence/history tree a
        # second time in this adapter; the path/symlink/containment checks here
        # still fail closed, while the transaction layer remains the checksum
        # authority at the mutation boundary.
        state_files.append(
            {
                "relative_path": relative,
                "source_path": str(source),
                "sha256": expected_sha,
            }
        )
    from . import lite_photoprism_backup

    application_files = lite_photoprism_backup.validate_staged_application_files(
        restore_root, application_records
    )
    return package, state_files, application_files


def _restored_source_for(restored_root: Path, relative_path: str) -> Path | None:
    rel = Path(str(relative_path or "").lstrip("/"))
    candidate = restored_root / rel
    root = restored_root.resolve()
    if candidate.is_symlink():
        return None
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        return None
    if candidate.exists() and candidate.is_file():
        return candidate
    wanted = rel.parts
    if not wanted:
        return None
    for item in restored_root.rglob(rel.name):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            item.resolve(strict=False).relative_to(root)
        except ValueError:
            continue
        parts = item.relative_to(restored_root).parts
        if len(parts) >= len(wanted) and parts[-len(wanted):] == wanted:
            return item
    return None


def _create_pre_restore_checkpoint(preview: dict[str, Any], *, restore_id: str, reason: str) -> dict[str, Any]:
    checkpoint_id = f"checkpoint-{restore_id}-{uuid.uuid4().hex[:12]}"
    layout = backup_layout()
    checkpoint_dir = layout.restore_checkpoints / checkpoint_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    state_dir = deps.settings().state_dir
    files: list[dict[str, Any]] = []
    skipped = 0
    for change in preview.get("changes") or []:
        rel = str(change.get("relative_path") or "")
        if not rel.startswith("state/"):
            skipped += 1
            continue
        target = _target_for_backup_path(rel)
        if not target or not _is_within_path(target, state_dir):
            skipped += 1
            continue
        entry: dict[str, Any] = {
            "relative_path": rel,
            "target": "Lite state",
            "current_exists": target.exists(),
        }
        if target.exists() and target.is_file():
            checkpoint_file = checkpoint_dir / rel
            checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, checkpoint_file)
            entry.update(
                {
                    "checkpoint_relative_path": str(checkpoint_file.relative_to(checkpoint_dir)),
                    "size_bytes": checkpoint_file.stat().st_size,
                    "sha256": _sha256(checkpoint_file),
                }
            )
        files.append(entry)
    created_at = _utc()
    checkpoint = {
        "checkpoint_id": checkpoint_id,
        "restore_id": restore_id,
        "backup_id": preview.get("backup_id"),
        "preview_id": preview.get("preview_id"),
        "status": "created",
        "created_at": created_at,
        "reason": reason,
        "file_count": len([item for item in files if item.get("checkpoint_relative_path")]),
        "tracked_change_count": len(files),
        "skipped_change_count": skipped,
        "files": files,
        "summary": "Pre-restore checkpoint created before changing Lite state.",
    }
    restore_checkpoint_path(checkpoint_id).write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_backup_state(
        {
            "pre_restore_checkpoint": {
                "status": "created",
                "checkpoint_id": checkpoint_id,
                "restore_id": restore_id,
                "backup_id": preview.get("backup_id"),
                "preview_id": preview.get("preview_id"),
                "created_at": created_at,
                "file_count": checkpoint["file_count"],
                "summary": checkpoint["summary"],
            }
        }
    )
    return checkpoint


def _rollback_pre_restore_checkpoint(checkpoint: dict[str, Any]) -> bool:
    """Restore the exact pre-mutation state, including deletion of new files."""
    state_dir = deps.settings().state_dir
    try:
        for item in checkpoint.get("files") or []:
            rel = str(item.get("relative_path") or "")
            target = _target_for_backup_path(rel)
            if not target or target.is_symlink() or not _is_within_path(target, state_dir):
                continue
            checkpoint_rel = str(item.get("checkpoint_relative_path") or "")
            source = checkpoint.get("checkpoint_directory")
            checkpoint_root = backup_layout().restore_checkpoints / str(checkpoint.get("checkpoint_id") or "")
            saved = checkpoint_root / checkpoint_rel if checkpoint_rel else None
            if item.get("current_exists") and saved and saved.is_file() and _is_within_path(saved, checkpoint_root):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved, target)
            elif not item.get("current_exists") and target.exists() and target.is_file():
                target.unlink()
        return True
    except Exception:
        return False


def _record_restore_run(restore_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    restore_run_path(restore_id).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def _cleanup_restore_staging(restore_root: Path, *, attempts: int = 3) -> dict[str, Any]:
    """Remove a registered restore staging tree with bounded retry evidence.

    Termux can briefly retain a file handle while the worker hands the staged
    snapshot to the database transaction.  A single best-effort ``rmtree``
    therefore left terminal restore trees behind in live qualification.  Keep
    the cleanup bounded and fail closed when the internal staging tree cannot
    be removed; callers persist the result in the journal and restore receipt.
    """
    try:
        max_attempts = max(1, min(int(attempts), 5))
    except (TypeError, ValueError):
        max_attempts = 3
    last_error_type = ""
    for attempt in range(1, max_attempts + 1):
        try:
            if not restore_root.exists():
                return {
                    "status": "not_present",
                    "attempts": attempt,
                    "sanitized": True,
                }
            if restore_root.is_symlink() or not restore_root.is_dir():
                raise RuntimeError("Restore staging directory is not a safe directory")
            shutil.rmtree(restore_root)
            if not restore_root.exists():
                return {
                    "status": "removed",
                    "attempts": attempt,
                    "sanitized": True,
                }
            last_error_type = "DirectoryStillPresent"
        except Exception as exc:
            last_error_type = type(exc).__name__
        if attempt < max_attempts:
            time.sleep(min(0.25 * attempt, 1.0))
    return {
        "status": "failed",
        "attempts": max_attempts,
        "error_type": last_error_type or "CleanupFailed",
        "sanitized": True,
    }


RESTART_RELEVANT_RESTORE_PATHS = {
    "state/release_state.json",
    "state/catalog.json",
    "state/opa.json",
}


def _env_true(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _restore_service_restart_if_needed(restored_files: list[dict[str, Any]]) -> dict[str, Any]:
    impacted = sorted(
        {
            str(item.get("relative_path") or "")
            for item in restored_files
            if str(item.get("relative_path") or "") in RESTART_RELEVANT_RESTORE_PATHS
        }
    )
    if not impacted:
        return {
            "status": "not_required",
            "needed": False,
            "services": [],
            "summary": "Restored Lite state does not require a service restart.",
        }
    if not _env_true("POCKETLAB_LITE_RESTORE_ALLOW_SERVICE_RESTART"):
        return {
            "status": "skipped_requires_opt_in",
            "needed": True,
            "services": ["pocket-api"],
            "impacted_paths": impacted,
            "summary": "Service restart may be useful, but automatic restart is disabled. Set POCKETLAB_LITE_RESTORE_ALLOW_SERVICE_RESTART=1 to enable it.",
        }
    pm2 = shutil.which(os.environ.get("POCKETLAB_PM2_BIN", "pm2"))
    if not pm2:
        return {
            "status": "failed",
            "needed": True,
            "services": ["pocket-api"],
            "impacted_paths": impacted,
            "summary": "Service restart was required but pm2 was not found.",
        }
    api_name = os.environ.get("POCKETLAB_LITE_API_PM2_NAME", "pocket-api")
    result = subprocess.run(
        # This subprocess runs inside the worker.  Passing --update-env would
        # replace the API's saved PM2 environment with the worker's process
        # role/ownership settings and can start two projection owners.
        [pm2, "restart", api_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "status": "succeeded" if result.returncode == 0 else "failed",
        "needed": True,
        "services": [api_name],
        "impacted_paths": impacted,
        "summary": "Service restart completed." if result.returncode == 0 else "Service restart failed.",
        "stderr_present": bool(result.stderr.strip()),
    }


def _validate_lite_api_health() -> dict[str, Any]:
    # The restore transaction holds the projection/database switch fence while
    # active state is being validated.  Prepared Recovery reads are therefore
    # allowed to remain stale until the fence is released and the worker can
    # refresh them.  Use the root FastAPI readiness contract for the in-fence
    # service check; Recovery projection freshness is verified separately after
    # the transaction commits.
    url = os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_URL", "http://127.0.0.1:8443/health")
    try:
        # A controlled API restart on a low-power Termux host can include
        # startup recovery, SQLite reopening, and bounded projection warm-up.
        # Keep the probe finite, but do not turn the expected restart window
        # into a false rollback merely because early Caddy probes see an
        # unavailable upstream.
        # A cold Termux API restart can spend roughly 80 seconds in startup
        # recovery and projection initialization even when the process is
        # already running. Keep the readiness window finite but long enough
        # to cover that measured edge-device restart envelope.
        attempts = max(
            1,
            min(240, int(os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_ATTEMPTS", "180"))),
        )
    except (TypeError, ValueError):
        attempts = 4
    try:
        interval = max(
            0.0,
            min(2.0, float(os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_INTERVAL", "0.5"))),
        )
    except (TypeError, ValueError):
        interval = 0.5
    try:
        timeout = max(
            0.1,
            min(15.0, float(os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_TIMEOUT", "5"))),
        )
    except (TypeError, ValueError):
        timeout = 5.0

    last: dict[str, Any] = {
        "status": "failed",
        "url": url,
        "summary": "Lite API health check did not complete.",
    }
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - local operator-configured URL
                raw = response.read(1024 * 1024).decode("utf-8", errors="replace")
                http_status = int(getattr(response, "status", 200))
        except Exception as exc:
            last = {
                "status": "failed",
                "url": url,
                "attempt_count": attempt,
                "summary": f"Lite API health check failed: {_safe_restore_error(exc)}",
            }
        else:
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}
            health_status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
            read_degraded = bool(payload.get("read_degraded")) if isinstance(payload, dict) else False
            degraded_reason = str(payload.get("degraded_reason") or "").strip() if isinstance(payload, dict) else ""
            passed = http_status == 200 and health_status in {"healthy", "ready", "ok"} and not read_degraded
            last = {
                "status": "passed" if passed else "failed",
                "url": url,
                "http_status": http_status,
                "health_status": health_status or None,
                # Keep the historical field for consumers that already render it, but
                # do not treat a prepared Recovery status as the in-fence readiness
                # authority.
                "recovery_status": health_status or None,
                "read_degraded": read_degraded,
                "degraded_reason": degraded_reason or None,
                "attempt_count": attempt,
                "summary": "FastAPI readiness validated after restore." if passed else "FastAPI responded, but readiness was not acceptable after restore.",
            }
            if passed:
                return last
        if attempt < attempts and interval:
            time.sleep(interval)
    return last


def _apply_full_restore_from_staging(
    *,
    restore_id: str,
    backup_id: str,
    preview_id: str,
    preview: dict[str, Any],
    manifest: dict[str, Any],
    snapshot_id: str,
    restore_root: Path,
    reason: str,
) -> dict[str, Any]:
    """Restore the selected format-2 point through the canonical DB transaction."""
    from . import lite_database_recovery

    package, state_files, application_files = _prepare_full_restore_inputs(manifest, restore_root)

    def validate_after_restore(restored_files: list[dict[str, Any]]) -> dict[str, Any]:
        service_restart = _restore_service_restart_if_needed(restored_files)
        health_validation = _validate_lite_api_health()
        application_validation = {"status": "passed", "state": "not_present", "sanitized": True}
        if application_files:
            from . import lite_photoprism_backup

            application_validation = lite_photoprism_backup.validate_runtime_health()
        passed = (
            health_validation.get("status") == "passed"
            and service_restart.get("status") != "failed"
            and application_validation.get("status") == "passed"
        )
        if not passed:
            raise RestoreValidationError(
                {
                    "service_restart": service_restart,
                    "health_validation": health_validation,
                    "application_validation": application_validation,
                }
            )
        return {
            "status": "passed",
            "service_restart": service_restart,
            "health_validation": health_validation,
            "application_validation": application_validation,
        }

    database_result = lite_database_recovery.restore_database_backup(
        {
            "command_id": restore_id,
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "confirm": True,
            "source_package": str(package),
            "restore_source_root": str(restore_root),
            "restore_state_files": state_files,
            "restore_application_files": application_files,
            "restore_preview": preview,
            "_post_restore_validator": validate_after_restore,
            "reason": reason,
        }
    )
    phase = str(database_result.get("phase") or "")
    status = {
        "committed": "succeeded",
        "rolled_back": "failed_with_rollback",
        "rollback_failed": "failed_rollback_required",
    }.get(phase, "failed_rollback_required")
    restored_files = database_result.get("restored_files")
    if not isinstance(restored_files, list):
        restored_files = []
    application_restored_files = database_result.get("application_files")
    if not isinstance(application_restored_files, list):
        application_restored_files = []
    all_restored_files = [*restored_files, *application_restored_files]
    skipped_changes = [
        {
            "relative_path": str(change.get("relative_path") or ""),
            "reason": "metadata_only",
        }
        for change in preview.get("changes") or []
        if isinstance(change, dict)
        and not str(change.get("relative_path") or "").startswith("state/")
        and not str(change.get("relative_path") or "").startswith("application/")
    ]
    post_validation = database_result.get("post_restore_validation")
    service_restart = post_validation.get("service_restart") if isinstance(post_validation, dict) else None
    health_validation = post_validation.get("health_validation") if isinstance(post_validation, dict) else None
    application_validation = post_validation.get("application_validation") if isinstance(post_validation, dict) else None
    result = {
        "status": status,
        "restore_id": restore_id,
        "backup_id": backup_id,
        "preview_id": preview_id,
        "snapshot_id": snapshot_id,
        "checkpoint_id": f"checkpoint-{restore_id}",
        "started_at": database_result.get("started_at"),
        "completed_at": database_result.get("completed_at"),
        "failed_at": database_result.get("failed_at"),
        "restored_file_count": len(all_restored_files),
        "skipped_change_count": len(skipped_changes),
        "restored_files": all_restored_files[:500],
        "skipped_changes": skipped_changes[:500],
        "service_restart": service_restart,
        "health_validation": health_validation,
        "application_validation": application_validation,
        "database_restore": database_result,
        "verification": database_result.get("verification"),
        "rollback": database_result.get("rollback"),
        "summary": database_result.get("summary") or "Selected restore transaction completed.",
        "evidence_references": [
            "pocketlab.events.lite.restore.started",
            "pocketlab.events.lite.restore.checkpoint_created",
            "pocketlab.events.lite.restore.health_validated",
            "pocketlab.events.lite.restore.completed",
            "pocketlab.audit.lite.restore.completed",
        ],
    }
    _record_restore_run(restore_id, result)
    _write_backup_state(
        {
            "latest_backup_id": backup_id,
            "latest_snapshot_id": snapshot_id,
            "pending_backup": None,
            "pre_restore_checkpoint": {
                "status": "created",
                "checkpoint_id": result["checkpoint_id"],
                "restore_id": restore_id,
                "backup_id": backup_id,
                "preview_id": preview_id,
                "created_at": database_result.get("started_at"),
                "summary": "Pre-restore checkpoint created before changing Lite state.",
            },
            "last_restore": {
                "status": status,
                "restore_id": restore_id,
                "backup_id": backup_id,
                "preview_id": preview_id,
                "checkpoint_id": result["checkpoint_id"],
                "completed_at": result.get("completed_at"),
                "failed_at": result.get("failed_at"),
                "restored_file_count": len(restored_files),
                "summary": result["summary"],
                "rollback": result.get("rollback"),
                "health_validation": health_validation,
            },
            "manifest": str(lite_backup_manifest.manifest_path(backup_id)),
            "restore_preview": str(restore_preview_path(preview_id)),
            "restore_run": str(restore_run_path(restore_id)),
        }
    )
    return result


def apply_restore(command: dict[str, Any]) -> dict[str, Any]:
    restore_id = _command_id(command)
    preview_id = str(command.get("preview_id") or "").strip()
    requested_backup = str(command.get("backup_id") or "").strip()
    reason = str(command.get("reason") or "manual restore")
    if not requested_backup or requested_backup == "latest":
        raise RuntimeError("Restore requires an explicit backup_id")
    if not command.get("confirm"):
        raise RuntimeError("Restore requires explicit confirmation")
    if not preview_id:
        raise RuntimeError("Restore requires a restore preview id")
    preview = get_restore_preview(preview_id)
    if not preview:
        raise RuntimeError("Restore preview was not found")
    if preview.get("status") != "ready" or preview.get("verification_status") != "verified":
        raise RuntimeError("Restore preview is not ready. Verify backup and create Preview Restore first.")
    if not preview.get("restore_allowed") or not preview.get("restore_supported"):
        raise RuntimeError("Restore preview is not marked as restorable. Recreate Preview Restore after Increment 4.")
    backup_id = str(preview.get("backup_id") or "")
    resolved = lite_backup_manifest.resolve_backup_id(requested_backup)
    if resolved != backup_id:
        raise RuntimeError("Restore preview does not match the requested backup id")

    # JetStream delivery is at-least-once.  A worker can finish the governed
    # restore transaction, acknowledge late, and then receive the same command
    # again after a process replacement.  Recreating the already-terminal
    # transaction directory would raise FileExistsError and turn a truthful
    # failed_with_rollback result into an endless retry.  Replay only when the
    # durable result belongs to this exact backup/preview pair; a new command
    # with a different selection still follows the normal binding checks.
    existing_result = get_restore_run(restore_id)
    if (
        isinstance(existing_result, dict)
        and str(existing_result.get("backup_id") or "") == backup_id
        and str(existing_result.get("preview_id") or "") == preview_id
        and str(existing_result.get("status") or "").lower()
        in {"succeeded", "failed_with_rollback", "failed_rollback_required", "failed", "rolled_back"}
    ):
        return existing_result

    # A worker can be replaced after the preflight journal is durably closed
    # but before the outer restore result is written.  Reuse the terminal
    # database-transaction result instead of trying to create the same
    # journal directory again on JetStream redelivery.
    from . import lite_restore_transaction

    terminal_journal = lite_restore_transaction.read_journal(restore_id)
    if (
        isinstance(terminal_journal, dict)
        and str(terminal_journal.get("phase") or "")
        in lite_restore_transaction.TERMINAL_PHASES
    ):
        from . import lite_database_recovery

        durable_result = lite_database_recovery.get_database_restore_run(restore_id)
        if isinstance(durable_result, dict):
            terminal_phase = str(terminal_journal.get("phase") or "")
            terminal_status = {
                "committed": "succeeded",
                "rolled_back": "failed_with_rollback",
                "rollback_failed": "failed_rollback_required",
            }.get(terminal_phase, "failed_rollback_required")
            replay = {
                "status": terminal_status,
                "restore_id": restore_id,
                "backup_id": backup_id,
                "preview_id": preview_id,
                "checkpoint_id": f"checkpoint-{restore_id}",
                "started_at": durable_result.get("started_at"),
                "completed_at": durable_result.get("completed_at"),
                "failed_at": durable_result.get("failed_at"),
                "database_restore": durable_result,
                "verification": durable_result.get("verification"),
                "rollback": durable_result.get("rollback"),
                "summary": durable_result.get("summary") or "Selected restore transaction completed.",
                "idempotent_replay": True,
            }
            return _record_restore_run(restore_id, replay)

    binding = validate_restore_preview_binding(preview)
    manifest = binding["manifest"]
    snapshot_id = str(manifest.get("snapshot_id") or "").strip()
    if snapshot_id != str(preview.get("snapshot_id") or "").strip():
        raise RuntimeError("Restore preview snapshot does not match the backup manifest")
    restic = _restic_binary()
    if not restic:
        raise RuntimeError("restic is required for Lite restore but was not found in PATH")
    snapshot_check = _restic_snapshot_exists(restic, snapshot_id, _restic_env(backup_layout()))
    if snapshot_check.get("status") != "passed":
        raise RuntimeError("Selected restore point is no longer present in the configured encrypted repository")
    if not _BACKUP_OPERATION_LOCK.acquire(blocking=False):
        raise RuntimeError("Another backup or restore operation is already running")

    started_at = _utc()
    layout = backup_layout()
    layout.ensure()
    restore_root = layout.staging / f"restore-{restore_id}"
    if restore_root.exists():
        shutil.rmtree(restore_root)
    checkpoint: dict[str, Any] | None = None
    restored_files: list[dict[str, Any]] = []
    skipped_changes: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    from . import lite_restore_transaction

    try:
        # Persist the governed restore intent before restic starts writing the
        # isolated snapshot tree.  A worker replacement during restic staging
        # must leave a durable journal that startup recovery can close safely;
        # otherwise the selected restore can disappear between acceptance and
        # the existing database transaction boundary.
        lite_restore_transaction.create_journal(
            restore_id=restore_id,
            backup_id=backup_id,
            preview_id=preview_id,
            target_names=[
                str(change.get("relative_path") or "")
                for change in preview.get("changes") or []
                if isinstance(change, dict)
            ],
            preflight=True,
            snapshot_id=snapshot_id,
            manifest_checksum=str(manifest.get("manifest_checksum") or ""),
            staging_key=restore_root.name,
        )
        lite_restore_transaction.update_journal(
            restore_id,
            phase="staging",
            summary="Restore accepted. Materializing the verified snapshot in isolated staging.",
        )
        restore_root.mkdir(parents=True, exist_ok=True)
        restore_result = _run_restic(
            [restic, "restore", snapshot_id, "--target", str(restore_root)],
            env=_restic_env(layout),
            timeout=600,
            capture_stdout=False,
        )
        if restore_result.returncode != 0:
            raise RuntimeError(f"restic restore failed: {_safe_restic_error(restore_result.stderr or restore_result.stdout)}")

        # Format-2 restore points always carry the canonical SQLite package.
        # Route the entire selected restore through the existing guarded
        # database transaction so its checkpoint, writer fencing, validation,
        # and rollback cover both SQLite and registered state files.
        if int(manifest.get("format_version") or 1) >= 2:
            result = _apply_full_restore_from_staging(
                restore_id=restore_id,
                backup_id=backup_id,
                preview_id=preview_id,
                preview=preview,
                manifest=manifest,
                snapshot_id=snapshot_id,
                restore_root=restore_root,
                reason=reason,
            )
            return result

        # Legacy file-only points take over the same preflight journal before
        # their checkpoint begins.  Full format-2 points hand it to the
        # canonical database transaction above.
        lite_restore_transaction.update_journal(
            restore_id,
            phase="checkpointing",
            summary="Creating pre-restore checkpoint.",
            preflight=False,
            restore_stage="database_restore",
        )
        checkpoint = _create_pre_restore_checkpoint(preview, restore_id=restore_id, reason=reason)
        lite_restore_transaction.update_journal(restore_id, phase="checkpoint_ready", summary="Pre-restore checkpoint is ready.")
        lite_restore_transaction.update_journal(restore_id, phase="staging", summary="Restore snapshot staged for validation.")
        state_dir = deps.settings().state_dir
        for change in preview.get("changes") or []:
            rel = str(change.get("relative_path") or "")
            if not rel.startswith("state/"):
                skipped_changes.append({"relative_path": rel, "reason": "metadata_only"})
                continue
            target = _target_for_backup_path(rel)
            if not target or not _is_within_path(target, state_dir):
                skipped_changes.append({"relative_path": rel, "reason": "target_not_allowed"})
                continue
            source = _restored_source_for(restore_root, rel)
            if not source:
                skipped_changes.append({"relative_path": rel, "reason": "not_found_in_restored_snapshot"})
                continue
            manifest_file = _manifest_file_by_relative_path(manifest, rel)
            expected_sha = str((manifest_file or {}).get("sha256") or "")
            source_sha = _sha256(source)
            if expected_sha and source_sha != expected_sha:
                raise RuntimeError(f"Restored file checksum mismatch for {rel}")
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_target = target.with_name(f".{target.name}.restore-{restore_id}.tmp")
            shutil.copy2(source, tmp_target)
            tmp_target.replace(target)
            restored_files.append(
                {
                    "relative_path": rel,
                    "target": "Lite state",
                    "size_bytes": target.stat().st_size,
                    "sha256": _sha256(target),
                    "action": change.get("action") or "restored",
                }
            )
        service_restart = _restore_service_restart_if_needed(restored_files)
        health_validation = _validate_lite_api_health()
        if health_validation.get("status") != "passed" or service_restart.get("status") == "failed":
            raise RuntimeError("Post-restore health validation failed")
        lite_restore_transaction.update_journal(restore_id, phase="validating_active", summary="Post-restore health checks passed.")
        completed_at = _utc()
        final_status = "succeeded"
        result = {
            "status": final_status,
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "snapshot_id": snapshot_id,
            "checkpoint_id": checkpoint.get("checkpoint_id") if checkpoint else None,
            "started_at": started_at,
            "completed_at": completed_at,
            "restored_file_count": len(restored_files),
            "skipped_change_count": len(skipped_changes),
            "restored_files": restored_files[:500],
            "skipped_changes": skipped_changes[:500],
            "service_restart": service_restart,
            "health_validation": health_validation,
            "summary": f"Restore completed. {len(restored_files)} Lite state file(s) restored after checkpoint creation." if final_status == "succeeded" else f"Restore completed with warnings. {len(restored_files)} Lite state file(s) restored after checkpoint creation.",
            "evidence_references": [
                "pocketlab.events.lite.restore.started",
                "pocketlab.events.lite.restore.checkpoint_created",
                "pocketlab.events.lite.restore.service_restart_checked",
                "pocketlab.events.lite.restore.health_validated",
                "pocketlab.events.lite.restore.completed",
                "pocketlab.audit.lite.restore.completed",
            ],
        }
        _record_restore_run(restore_id, result)
        lite_restore_transaction.update_journal(restore_id, phase="committed", summary="Restore transaction committed.", terminal_status="committed", status="succeeded")
        checkpoint_summary = {
            "status": "created",
            "checkpoint_id": result["checkpoint_id"],
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "created_at": checkpoint.get("created_at") if checkpoint else started_at,
            "file_count": checkpoint.get("file_count") if checkpoint else 0,
            "summary": "Pre-restore checkpoint created before changing Lite state.",
        }
        _write_backup_state(
            {
                "latest_backup_id": backup_id,
                "latest_snapshot_id": snapshot_id,
                "pending_backup": None,
                "latest_restore_preview": {
                    "preview_id": preview_id,
                    "backup_id": backup_id,
                    "status": preview.get("status"),
                    "created_at": preview.get("created_at"),
                    "change_count": preview.get("change_count"),
                },
                "pre_restore_checkpoint": checkpoint_summary,
                "last_restore": {
                    "status": final_status,
                    "restore_id": restore_id,
                    "backup_id": backup_id,
                    "preview_id": preview_id,
                    "checkpoint_id": result["checkpoint_id"],
                    "completed_at": completed_at,
                    "restored_file_count": len(restored_files),
                    "summary": result["summary"],
                    "service_restart": service_restart,
                    "health_validation": health_validation,
                },
                "manifest": str(lite_backup_manifest.manifest_path(backup_id)),
                "restore_preview": str(restore_preview_path(preview_id)),
                "restore_run": str(restore_run_path(restore_id)),
            }
        )
        return result
    except Exception as exc:
        failed_at = _utc()
        rolled_back = bool(checkpoint and _rollback_pre_restore_checkpoint(checkpoint))
        preflight_interrupted = False
        try:
            current_journal = lite_restore_transaction.read_journal(restore_id) or {}
            preflight_interrupted = bool(current_journal.get("preflight"))
            lite_restore_transaction.update_journal(
                restore_id,
                phase="rolled_back" if rolled_back or preflight_interrupted else "rollback_failed",
                summary=(
                    "Restore failed before active state mutation while materializing the selected snapshot."
                    if preflight_interrupted
                    else "Restore rolled back after validation failure."
                    if rolled_back
                    else "Rollback requires operator recovery."
                ),
                terminal_status="rolled_back" if rolled_back or preflight_interrupted else "rollback_failed",
                status="failed_with_rollback" if rolled_back or preflight_interrupted else "failed_rollback_required",
                restore_failure_stage="restic_restore" if preflight_interrupted else None,
                restore_failure_category="restore_interrupted" if preflight_interrupted else None,
                failure_category="restore_interrupted" if preflight_interrupted else None,
                api_worker_restart_allowed=True if preflight_interrupted else None,
                rollback={
                    "status": "not_required",
                    "attempted": False,
                    "staging_cleanup": "scheduled",
                }
                if preflight_interrupted
                else None,
            )
        except Exception:
            pass
        failed_with_rollback = rolled_back or preflight_interrupted
        result = {
            "status": "failed_with_rollback" if failed_with_rollback else "failed_rollback_required",
            "restore_id": restore_id,
            "backup_id": preview.get("backup_id"),
            "preview_id": preview_id,
            "checkpoint_id": checkpoint.get("checkpoint_id") if checkpoint else None,
            "started_at": started_at,
            "failed_at": failed_at,
            "error": _safe_restore_error(exc),
            "summary": (
                "Restore failed before active state mutation and the staged snapshot was discarded."
                if preflight_interrupted
                else "Restore failed and was rolled back from the pre-restore checkpoint."
                if rolled_back
                else "Restore failed; operator rollback is required."
                if checkpoint
                else "Restore failed before checkpoint creation."
            ),
        }
        _record_restore_run(restore_id, result)
        state_update: dict[str, Any] = {
            "last_restore": {
                "status": "failed",
                "restore_id": restore_id,
                "backup_id": preview.get("backup_id"),
                "preview_id": preview_id,
                "checkpoint_id": result["checkpoint_id"],
                "failed_at": failed_at,
                "error": result["error"],
                "summary": result["summary"],
            }
        }
        if checkpoint:
            state_update["pre_restore_checkpoint"] = {
                "status": "created",
                "checkpoint_id": checkpoint.get("checkpoint_id"),
                "restore_id": restore_id,
                "backup_id": preview.get("backup_id"),
                "preview_id": preview_id,
                "created_at": checkpoint.get("created_at"),
                "file_count": checkpoint.get("file_count"),
                "summary": checkpoint.get("summary"),
            }
        _write_backup_state(state_update)
        raise
    finally:
        cleanup = _cleanup_restore_staging(restore_root)
        if result is not None:
            result["staging_cleanup"] = cleanup["status"]
            if cleanup["status"] == "failed":
                result["status"] = "failed_rollback_required"
                result["summary"] = "Restore completed its state transaction, but staged snapshot cleanup failed; operator recovery is required."
            try:
                _record_restore_run(restore_id, result)
            except Exception:
                pass
        try:
            current_journal = lite_restore_transaction.read_journal(restore_id)
            if current_journal:
                rollback = dict(current_journal.get("rollback") or {})
                rollback["staging_cleanup"] = cleanup["status"]
                updates: dict[str, Any] = {
                    "staging_cleanup": cleanup["status"],
                    "rollback": rollback,
                }
                if cleanup["status"] == "failed":
                    updates.update(
                        {
                            "phase": "rollback_failed",
                            "status": "failed",
                            "terminal_status": "rollback_failed",
                            "failure_category": "restore_staging_cleanup_failed",
                            "rollback_failure_category": "restore_staging_cleanup_failed",
                            "api_worker_restart_allowed": False,
                            "summary": "Restore state is governed, but its staged snapshot could not be removed safely. Operator recovery is required.",
                        }
                    )
                lite_restore_transaction.update_journal(
                    restore_id,
                    event=False,
                    **updates,
                )
        except Exception:
            pass
        _BACKUP_OPERATION_LOCK.release()


def create_backup(command: dict[str, Any]) -> dict[str, Any]:
    backup_id = _command_id(command)
    include_app_data = bool(command.get("include_app_data", True))
    include_event_journal = bool(command.get("include_event_journal", True))
    reason = str(command.get("reason") or "manual backup")
    existing = _existing_backup_result(backup_id)
    if existing is not None:
        return existing
    if not _BACKUP_OPERATION_LOCK.acquire(blocking=False):
        raise RuntimeError("Another backup or restore operation is already running")
    layout = backup_layout()
    layout.ensure()
    restic = _restic_binary()
    if not restic:
        raise RuntimeError("restic is required for Lite backup creation but was not found in PATH")

    created_at = _utc()
    staging_root = layout.staging / backup_id
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    try:
        _ensure_password_file(layout.password_file)
        env = _restic_env(layout)
        if not _restic_repo_initialized(layout):
            init_result = _run_restic([restic, "init"], env=env, timeout=120)
            if init_result.returncode != 0:
                raise RuntimeError(
                    f"restic init failed: {init_result.stderr.strip() or init_result.stdout.strip()}"
                )

        from . import lite_database_recovery

        database_backup_id = f"{backup_id}-database"
        database_backup = lite_database_recovery.create_database_backup(
            {"backup_id": database_backup_id, "reason": reason}
        )
        state_inventory = _copy_sources_to_staging(
            backup_id,
            staging_root,
            include_event_journal=include_event_journal,
        )
        database_files = _copy_database_backup_to_staging(database_backup_id, staging_root)
        application_backup = {
            "status": "not_requested",
            "records": [],
            "components": {},
            "summary": "Application metadata was not requested.",
        }
        if include_app_data:
            application_backup = _copy_application_backup_to_staging(staging_root)
        database_sets = {
            str(item.get("set") or "Pocket Lab database") for item in database_files
        }
        application_files = [
            item for item in application_backup["records"] if isinstance(item, dict)
        ]
        application_sets = {
            str(item.get("set") or "Application metadata") for item in application_files
        }
        included_sets = sorted(state_inventory.included_sets | database_sets | application_sets)
        size_bytes = state_inventory.size_bytes + sum(
            int(item.get("size_bytes") or 0) for item in database_files + application_files
        )
        backup_args = [
            restic,
            "backup",
            ".",
            "--json",
            "--tag",
            "pocket-lab-lite",
            "--tag",
            f"backup-id={backup_id}",
        ]
        backup_result = _run_restic(
            backup_args,
            env=env,
            timeout=600,
            cwd=staging_root,
            capture_stdout=False,
        )
        if backup_result.returncode != 0:
            raise RuntimeError(
                f"restic backup failed: {_safe_restic_error(backup_result)}"
            )
        snapshot_id = _restic_snapshot_id_for_backup(restic, backup_id, env)
        scope = backup_scope(
            include_app_data=include_app_data,
            include_event_journal=include_event_journal,
        )
        # The complete per-file inventory is deliberately loaded only after the
        # potentially verbose restic backup has committed. During the low-power
        # staging phase it remains on disk as JSONL instead of growing in RAM.
        copied = state_inventory.load_records()
        copied.extend(database_files)
        copied.extend(application_files)
        manifest = {
            "backup_id": backup_id,
            "created_at": created_at,
            "completed_at": _utc(),
            "label": "Pocket Lab Lite restore point",
            "format_version": 2,
            "status": "created",
            "app_version": str(os.environ.get("POCKETLAB_LITE_APP_VERSION") or "unknown")[:80],
            "schema_version": int(database_backup.get("schema_version") or 0),
            "include_event_journal": include_event_journal,
            "engine": "restic",
            "repository": {
                "type": "local",
                "engine": "restic",
                "encrypted": True,
                "location": public_repository_label(layout),
            },
            "snapshot_id": snapshot_id,
            "reason": reason,
            "included_sets": included_sets,
            "included_components": included_sets,
            "included_files": copied,
            "size_bytes": size_bytes,
            "excluded_sensitive_items": scope["excluded_sensitive"],
            "excluded_runtime_items": scope["excluded_runtime"],
            "excluded_components": scope["excluded_sensitive"] + scope["excluded_runtime"],
            "conditional_items": scope["conditional"],
            "verification_status": "not_verified",
            "restorable": False,
            "verified_at": None,
            "risk_level": "low",
            "evidence_references": [
                "pocketlab.events.lite.backup.started",
                "pocketlab.events.lite.backup.snapshot_created",
                "pocketlab.audit.lite.backup.created",
            ],
            "restic": {
                "stdout_summary": "restic backup completed",
                "stderr_present": bool(str(backup_result.stderr or "").strip()),
            },
            "database_backup": database_backup,
            "component_results": {
                "control_plane_database": {"status": "validated", "required": True},
                "lite_runtime_state": {"status": "validated", "required": True},
                "application_metadata": {
                    "status": "failed" if application_backup["status"] == "failed" else application_backup["status"],
                    "required": include_app_data and application_backup["status"] != "not_present",
                },
                "sanitized_evidence": {"status": "validated", "required": True},
                "media_exclusion": {"status": "validated", "required": True},
                **application_backup["components"],
            },
            "summary": f"Backup created with {len(copied)} safe item(s), including a verified Pocket Lab database backup. {application_backup['summary']}",
        }
        manifest = lite_backup_manifest.write_manifest(manifest)
        receipt = lite_backup_manifest.write_receipt(
            backup_id,
            {
                "backup_id": backup_id,
                "created_at": created_at,
                "status": "succeeded",
                "summary": "Evidence saved",
                "engine": "restic",
                "snapshot_id": snapshot_id,
                "manifest_checksum": manifest.get("manifest_checksum"),
                "evidence_saved": True,
                "evidence_references": manifest["evidence_references"],
                "repository": manifest["repository"],
                "included_sets": included_sets,
                "excluded_sensitive_items": manifest["excluded_sensitive_items"],
            },
        )
        _write_backup_state({
                "latest_backup_id": backup_id,
                "latest_snapshot_id": snapshot_id,
                "pending_backup": None,
                "updated_at": _utc(),
                "manifest": str(lite_backup_manifest.manifest_path(backup_id)),
                "receipt": str(lite_backup_manifest.receipt_path(backup_id)),
            })
        return {
            "status": "succeeded",
            "backup_id": backup_id,
            "snapshot_id": snapshot_id,
            "manifest": lite_backup_manifest.api_manifest(manifest),
            "receipt": lite_backup_manifest.api_receipt(receipt),
            "summary": manifest["summary"],
        }
    except Exception as exc:
        _record_backup_failure(
            backup_id,
            reason=reason,
            include_app_data=include_app_data,
            include_event_journal=include_event_journal,
            error=str(exc),
        )
        raise
    finally:
        try:
            shutil.rmtree(staging_root)
        except Exception:
            pass
        _BACKUP_OPERATION_LOCK.release()


def get_backup(backup_id: str) -> dict[str, Any] | None:
    requested = str(backup_id or "").strip()
    resolved = lite_backup_manifest.resolve_backup_id(requested)
    if not resolved:
        if requested == "latest":
            pending = pending_backup()
            return _api_pending_backup(pending) if pending else lite_backup_manifest.no_backup_payload(backup_id="latest")
        return None
    manifest = lite_backup_manifest.read_manifest(resolved)
    return lite_backup_manifest.api_manifest(manifest) if manifest else None


def list_backups(limit: int = 25, cursor: str = "") -> dict[str, Any]:
    page = lite_backup_manifest.list_manifests_page(limit=limit, cursor=cursor)
    items = [lite_backup_manifest.api_manifest(item) for item in page["items"]]
    pending = pending_backup() if not items and not cursor else None
    readiness = repository_readiness()
    return {
        "status": "healthy" if items else ("queued" if pending else readiness.get("status", "degraded")),
        "count": len(items),
        "backups": items,
        "latest_backup": items[0] if items and not cursor else None,
        "pending_backup": _api_pending_backup(pending) if pending else None,
        "next_cursor": page.get("next_cursor"),
        "has_more": bool(page.get("has_more")),
        "cursor_found": bool(page.get("cursor_found")),
        "summary": "Backup history is empty. Run Backup Now to initialize the encrypted repository and create the first backup." if not items and not pending and not cursor else None,
        "updated_at": _utc(),
    }


def get_receipt(backup_id: str) -> dict[str, Any] | None:
    requested = str(backup_id or "").strip()
    resolved = lite_backup_manifest.resolve_backup_id(requested)
    if not resolved:
        if requested == "latest":
            pending = pending_backup()
            if pending:
                payload = _api_pending_backup(pending)
                payload["summary"] = "Backup receipt will be available after the worker finishes the backup."
                return payload
            return lite_backup_manifest.no_backup_payload(backup_id="latest", kind="receipt")
        return None
    receipt = lite_backup_manifest.read_receipt(resolved)
    return lite_backup_manifest.api_receipt(receipt) if receipt else None
