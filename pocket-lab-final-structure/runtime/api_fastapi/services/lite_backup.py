from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
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
    args: list[str], *, env: dict[str, str], timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, check=False, capture_output=True, text=True, env=env, timeout=timeout
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
        "pre_restore_checkpoint": {
            "status": "not_created",
            "summary": "A checkpoint will be required before restore is implemented.",
        },
        "actions": ["backup_now"],
        "planned_actions": ["verify_backup", "preview_restore", "restore_latest"],
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

        copied = _copy_sources_to_staging(backup_id, staging_root)
        backup_args = [
            restic,
            "backup",
            str(staging_root),
            "--json",
            "--tag",
            "pocket-lab-lite",
            "--tag",
            f"backup-id={backup_id}",
        ]
        backup_result = _run_restic(backup_args, env=env, timeout=600)
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
            "summary": f"Backup created with {len(copied)} safe item(s). Evidence saved.",
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
