from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .. import deps
from . import lite_backup_manifest
from .lite_backup_policy import (
    backup_layout,
    backup_scope,
    discover_state_sources,
    public_repository_label,
)


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


def record_backup_request(command: dict[str, Any]) -> dict[str, Any]:
    backup_id = _command_id(command)
    requested_at = _utc()
    pending = {
        "backup_id": backup_id,
        "status": "queued",
        "requested_at": requested_at,
        "reason": command.get("reason") or "manual backup",
        "include_app_data": bool(command.get("include_app_data", False)),
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
    return str(
        command.get("command_id")
        or command.get("job_id")
        or command.get("trace_id")
        or uuid.uuid4().hex
    )


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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
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
        "restic_path": restic,
        "repository_initialized": initialized,
        "repository": {
            "type": "local",
            "engine": "restic",
            "encrypted": True,
            "ready": ready,
            "location": public_repository_label(layout),
            "details": {
                "root": str(layout.root),
                "restic_repo": str(layout.repository),
                "manifests": str(layout.manifests),
                "receipts": str(layout.receipts),
            },
        },
        "latest_backup_id": latest.get("backup_id") if latest else None,
        "checked_at": _utc(),
    }


def recovery_status() -> dict[str, Any]:
    readiness = repository_readiness()
    backups = [
        lite_backup_manifest.api_manifest(item)
        for item in lite_backup_manifest.list_manifests(limit=25)
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


def _copy_sources_to_staging(backup_id: str, staging_root: Path) -> list[dict[str, Any]]:
    sources = discover_state_sources()
    copied: list[dict[str, Any]] = []
    for item in sources:
        src = Path(item["path"])
        rel = Path(str(item["relative_path"]).lstrip("/"))
        dest = staging_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(
            {
                "set": item.get("set") or "Lite runtime state",
                "source": str(item.get("relative_path") or rel),
                "relative_path": str(rel),
                "size_bytes": dest.stat().st_size,
                "sha256": _sha256(dest),
            }
        )
    metadata_path = staging_root / "backup-metadata" / "scope.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "backup_id": backup_id,
        "created_at": _utc(),
        "source_count": len(copied),
        "scope": backup_scope(),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    copied.append(
        {
            "set": "Backup metadata",
            "source": "backup-metadata/scope.json",
            "relative_path": "backup-metadata/scope.json",
            "size_bytes": metadata_path.stat().st_size,
            "sha256": _sha256(metadata_path),
        }
    )
    return copied


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


def _record_backup_failure(backup_id: str, *, reason: str, include_app_data: bool, error: str) -> None:
    safe_error = str(error or "backup failed").strip()
    if len(safe_error) > 2000:
        safe_error = safe_error[:2000] + "..."
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



def _safe_restic_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr.strip() or result.stdout.strip() or "restic command failed").strip()
    if len(text) > 2000:
        text = text[:2000] + "..."
    return text


def _load_verified_manifest(backup_id: str) -> tuple[str, dict[str, Any]]:
    resolved = lite_backup_manifest.resolve_backup_id(backup_id)
    if not resolved:
        raise FileNotFoundError("Backup was not found.")
    manifest = lite_backup_manifest.read_manifest(resolved)
    if not manifest:
        raise FileNotFoundError("Backup manifest was not found.")
    return resolved, manifest


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
    ]
    status = "verified" if all(check.get("status") == "passed" for check in checks) else "failed"
    verified_at = _utc()
    manifest = dict(manifest)
    manifest["verification_status"] = status
    manifest["verified_at"] = verified_at if status == "verified" else None
    manifest["verification"] = {
        "status": status,
        "checked_at": verified_at,
        "reason": reason or "manual verification",
        "checks": checks,
        "previous_manifest_checksum": stored_checksum,
    }
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
    deps.core.write_json_file(
        deps.settings().state_dir / "backup_state.json",
        {
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
        },
    )
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


def _target_for_backup_path(relative_path: str) -> Path | None:
    rel = Path(str(relative_path or "").lstrip("/"))
    parts = rel.parts
    if not parts:
        return None
    if parts[0] == "state":
        return deps.settings().state_dir.joinpath(*parts[1:]) if len(parts) > 1 else deps.settings().state_dir
    return None


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
    restic_items = _parse_restic_ls(result.stdout)
    included = manifest.get("included_files") or []
    changes: list[dict[str, Any]] = []
    for item in included:
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
                "target": "Lite state" if target else "Backup metadata",
                "backup_size_bytes": item.get("size_bytes"),
            }
        )
    preview_id = f"preview-{resolved}-{uuid.uuid4().hex[:12]}"
    created_at = _utc()
    verified = manifest.get("verification_status") == "verified"
    preview = {
        "preview_id": preview_id,
        "backup_id": resolved,
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "status": "ready" if verified else "needs_verification",
        "restore_allowed": bool(verified),
        "restore_supported": True,
        "verification_status": manifest.get("verification_status", "not_verified"),
        "reason": reason or "manual restore preview",
        "summary": "Preview ready. Restore can run only after explicit confirmation and an automatic checkpoint." if verified else "Preview created, but backup must be verified before restore can be enabled.",
        "change_count": len(changes),
        "changes": changes[:500],
        "restic_item_count": len(restic_items),
        "sensitive_items_excluded": manifest.get("excluded_sensitive_items", []),
        "warnings": [
            "Restore execution is not performed by this preview.",
            "A pre-restore checkpoint will be created before any state file is changed.",
            "Raw secrets remain excluded from this restore point.",
        ],
    }
    path = restore_preview_path(preview_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    deps.core.write_json_file(
        deps.settings().state_dir / "backup_state.json",
        {
            "latest_backup_id": resolved,
            "latest_snapshot_id": snapshot_id,
            "pending_backup": None,
            "latest_restore_preview": {
                "preview_id": preview_id,
                "backup_id": resolved,
                "status": preview["status"],
                "created_at": created_at,
                "change_count": len(changes),
            },
            "updated_at": created_at,
            "manifest": str(lite_backup_manifest.manifest_path(resolved)),
            "restore_preview": str(path),
        },
    )
    return preview


def restore_checkpoint_path(checkpoint_id: str) -> Path:
    return backup_layout().restore_checkpoints / f"{checkpoint_id}.json"


def restore_run_path(restore_id: str) -> Path:
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
    text = str(error or "restore failed").strip()
    if len(text) > 2000:
        text = text[:2000] + "..."
    return text


def _manifest_file_by_relative_path(manifest: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
    wanted = str(relative_path or "").lstrip("/")
    for item in manifest.get("included_files") or []:
        if str(item.get("relative_path") or item.get("source") or "").lstrip("/") == wanted:
            return item
    return None


def _restored_source_for(restored_root: Path, relative_path: str) -> Path | None:
    rel = Path(str(relative_path or "").lstrip("/"))
    candidate = restored_root / rel
    if candidate.exists() and candidate.is_file():
        return candidate
    wanted = rel.parts
    if not wanted:
        return None
    for item in restored_root.rglob(rel.name):
        if not item.is_file():
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


def _record_restore_run(restore_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    restore_run_path(restore_id).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


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
        [pm2, "restart", api_name, "--update-env"],
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
    url = os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_URL", "http://127.0.0.1:8443/api/lite/recovery")
    timeout = float(os.environ.get("POCKETLAB_LITE_RESTORE_HEALTH_TIMEOUT", "5"))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - local operator-configured URL
            raw = response.read(1024 * 1024).decode("utf-8", errors="replace")
            http_status = int(getattr(response, "status", 200))
    except Exception as exc:
        return {
            "status": "failed",
            "url": url,
            "summary": f"Lite API health check failed: {_safe_restore_error(exc)}",
        }
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}
    recovery_status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
    passed = http_status == 200 and recovery_status in {"healthy", "degraded"}
    return {
        "status": "passed" if passed else "failed",
        "url": url,
        "http_status": http_status,
        "recovery_status": recovery_status or None,
        "summary": "Lite API health validated after restore." if passed else "Lite API responded, but health status was not acceptable after restore.",
    }


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
    manifest = lite_backup_manifest.read_manifest(backup_id)
    if not manifest:
        raise RuntimeError("Backup manifest was not found")
    if manifest.get("verification_status") != "verified":
        raise RuntimeError("Backup must be verified before restore")
    snapshot_id = str(manifest.get("snapshot_id") or "").strip()
    if snapshot_id != str(preview.get("snapshot_id") or "").strip():
        raise RuntimeError("Restore preview snapshot does not match the backup manifest")
    restic = _restic_binary()
    if not restic:
        raise RuntimeError("restic is required for Lite restore but was not found in PATH")

    started_at = _utc()
    layout = backup_layout()
    layout.ensure()
    restore_root = layout.staging / f"restore-{restore_id}"
    if restore_root.exists():
        shutil.rmtree(restore_root)
    restore_root.mkdir(parents=True, exist_ok=True)
    checkpoint: dict[str, Any] | None = None
    restored_files: list[dict[str, Any]] = []
    skipped_changes: list[dict[str, Any]] = []
    try:
        checkpoint = _create_pre_restore_checkpoint(preview, restore_id=restore_id, reason=reason)
        restore_result = _run_restic(
            [restic, "restore", snapshot_id, "--target", str(restore_root)],
            env=_restic_env(layout),
            timeout=600,
        )
        if restore_result.returncode != 0:
            raise RuntimeError(f"restic restore failed: {_safe_restic_error(restore_result.stderr or restore_result.stdout)}")
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
        completed_at = _utc()
        final_status = "succeeded" if health_validation.get("status") == "passed" and service_restart.get("status") not in {"failed"} else "succeeded_with_warnings"
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
        result = {
            "status": "failed",
            "restore_id": restore_id,
            "backup_id": preview.get("backup_id"),
            "preview_id": preview_id,
            "checkpoint_id": checkpoint.get("checkpoint_id") if checkpoint else None,
            "started_at": started_at,
            "failed_at": failed_at,
            "error": _safe_restore_error(exc),
            "summary": "Restore failed. The pre-restore checkpoint remains available for recovery." if checkpoint else "Restore failed before checkpoint creation.",
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
        try:
            shutil.rmtree(restore_root)
        except Exception:
            pass


def create_backup(command: dict[str, Any]) -> dict[str, Any]:
    backup_id = _command_id(command)
    include_app_data = bool(command.get("include_app_data", False))
    reason = str(command.get("reason") or "manual backup")
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
        copied = _copy_sources_to_staging(backup_id, staging_root)
        copied.extend(_copy_database_backup_to_staging(database_backup_id, staging_root))
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
        backup_result = _run_restic(backup_args, env=env, timeout=600, cwd=staging_root)
        if backup_result.returncode != 0:
            raise RuntimeError(
                f"restic backup failed: {backup_result.stderr.strip() or backup_result.stdout.strip()}"
            )
        snapshot_id = _parse_snapshot_id(backup_result.stdout) or backup_id
        scope = backup_scope(include_app_data=include_app_data)
        included_sets = sorted(
            {str(item.get("set") or "Lite runtime state") for item in copied}
        )
        manifest = {
            "backup_id": backup_id,
            "created_at": created_at,
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
            "included_files": copied,
            "excluded_sensitive_items": scope["excluded_sensitive"],
            "excluded_runtime_items": scope["excluded_runtime"],
            "conditional_items": scope["conditional"],
            "verification_status": "not_verified",
            "verified_at": None,
            "risk_level": "low",
            "evidence_references": [
                "pocketlab.events.lite.backup.started",
                "pocketlab.events.lite.backup.snapshot_created",
                "pocketlab.audit.lite.backup.created",
            ],
            "restic": {
                "stdout_summary": "restic backup completed",
                "stderr_present": bool(backup_result.stderr.strip()),
            },
            "database_backup": database_backup,
            "summary": f"Backup created with {len(copied)} safe item(s), including a verified Pocket Lab database backup. Evidence saved.",
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
        deps.core.write_json_file(
            deps.settings().state_dir / "backup_state.json",
            {
                "latest_backup_id": backup_id,
                "latest_snapshot_id": snapshot_id,
                "pending_backup": None,
                "updated_at": _utc(),
                "manifest": str(lite_backup_manifest.manifest_path(backup_id)),
                "receipt": str(lite_backup_manifest.receipt_path(backup_id)),
            },
        )
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
            error=str(exc),
        )
        raise
    finally:
        try:
            shutil.rmtree(staging_root)
        except Exception:
            pass


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


def list_backups(limit: int = 25) -> dict[str, Any]:
    items = [
        lite_backup_manifest.api_manifest(item)
        for item in lite_backup_manifest.list_manifests(limit=limit)
    ]
    pending = pending_backup() if not items else None
    readiness = repository_readiness()
    return {
        "status": "healthy" if items else ("queued" if pending else readiness.get("status", "degraded")),
        "count": len(items),
        "backups": items,
        "latest_backup": items[0] if items else None,
        "pending_backup": _api_pending_backup(pending) if pending else None,
        "summary": "Backup history is empty. Run Backup Now to initialize the encrypted repository and create the first backup." if not items and not pending else None,
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
