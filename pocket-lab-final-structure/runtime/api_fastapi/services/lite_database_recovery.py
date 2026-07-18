from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import deps
from ..db.connection import database_path, online_backup, read_connection
from ..db.migrations import apply_migrations, current_schema_version, discover_migrations
from . import lite_security_evidence as evidence
from . import lite_security_policy as policy
from .lite_backup_policy import backup_layout
from . import lite_security_maintenance as maintenance

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")

CORE_TABLES = frozenset(
    {
        "schema_migrations",
        "security_scan_runs",
        "security_scan_progress_events",
        "security_scan_findings",
        "security_scan_evidence_refs",
        "security_scan_tool_runs",
        "security_profile_snapshots",
        "domain_revisions",
        "security_store_metadata",
        "security_maintenance_runs",
        "security_database_backups",
        "security_database_restores",
    }
)


def _utc() -> str:
    return deps.now_utc_iso()


def _safe_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or ""))
    return safe[:120] or "unknown"


def _is_safe_identifier(value: str) -> bool:
    return bool(_SAFE_IDENTIFIER.fullmatch(str(value or "").strip()))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_fingerprint(artifact_hashes: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(artifact_hashes.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b":")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    clean = policy.redact_value(payload)
    deps.core.write_json_file(path, clean)
    return clean


def _read_json(path: Path, default: Any = None) -> Any:
    return policy.redact_value(deps.core.read_json_file(path, default))


def database_backup_root() -> Path:
    root = backup_layout().root / "database-backups"
    root.mkdir(parents=True, exist_ok=True)
    (root / "rollback").mkdir(parents=True, exist_ok=True)
    (root / "restore-previews").mkdir(parents=True, exist_ok=True)
    (root / "restore-runs").mkdir(parents=True, exist_ok=True)
    return root


def database_backup_package(backup_id: str) -> Path:
    return database_backup_root() / _safe_name(backup_id)


def database_restore_preview_path(preview_id: str) -> Path:
    return database_backup_root() / "restore-previews" / f"{_safe_name(preview_id)}.json"


def database_restore_run_path(restore_id: str) -> Path:
    return database_backup_root() / "restore-runs" / f"{_safe_name(restore_id)}.json"


@contextmanager
def _database_recovery_lock(operation: str):
    """Serialize online backup and restore without leaving a stale crash lock."""
    lock_path = database_backup_root() / ".database-recovery.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another database backup or restore is already running") from exc
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(
                json.dumps(
                    {
                        "operation": _safe_name(operation),
                        "started_at": _utc(),
                        "sanitized": True,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            handle.flush()
            os.fsync(handle.fileno())
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _migration_contract() -> list[dict[str, Any]]:
    return [
        {"version": item.version, "name": item.name, "checksum": item.checksum}
        for item in discover_migrations()
    ]


def _database_migrations(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _validate_migration_contract(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    known = {item["version"]: item for item in _migration_contract()}
    if not rows:
        return False, "Migration metadata is missing"
    latest_supported = max(known) if known else 0
    latest_backup = max(int(row.get("version") or 0) for row in rows)
    if latest_backup > latest_supported:
        return False, "Backup schema is newer than this Pocket Lab version"
    for row in rows:
        version = int(row.get("version") or 0)
        expected = known.get(version)
        if not expected:
            return False, "Backup contains an unsupported migration"
        if str(row.get("name") or "") != expected["name"]:
            return False, "Backup migration name does not match"
        if str(row.get("checksum") or "") != expected["checksum"]:
            return False, "Backup migration checksum does not match"
    return True, "Migration checksums match"


def validate_database_file(path: Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.is_file():
        raise RuntimeError("Database backup file is missing")
    conn = sqlite3.connect(str(candidate))
    conn.row_factory = sqlite3.Row
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        schema_version = int(
            conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
        )
        migrations = [
            dict(row)
            for row in conn.execute(
                "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
    finally:
        conn.close()
    migration_ok, migration_summary = _validate_migration_contract(migrations)
    missing_tables = sorted(CORE_TABLES - tables)
    valid = integrity == "ok" and quick_check == "ok" and migration_ok and not missing_tables
    return {
        "valid": valid,
        "integrity_check": integrity,
        "quick_check": quick_check,
        "schema_version": schema_version,
        "migration_checksums_valid": migration_ok,
        "migration_summary": migration_summary,
        "missing_core_tables": missing_tables,
        "sqlite_version": sqlite3.sqlite_version,
        "size_bytes": candidate.stat().st_size,
        "sha256": _sha256(candidate),
        "sanitized": True,
    }


def _api_backup(manifest: dict[str, Any]) -> dict[str, Any]:
    verification = manifest.get("verification") if isinstance(manifest.get("verification"), dict) else {}
    return policy.redact_value(
        {
            "backup_id": manifest.get("backup_id"),
            "status": manifest.get("status"),
            "created_at": manifest.get("created_at"),
            "verified_at": manifest.get("verified_at"),
            "verification_status": "verified" if verification.get("valid") else "not_verified",
            "size_bytes": manifest.get("size_bytes"),
            "schema_version": manifest.get("schema_version"),
            "sqlite_version": manifest.get("sqlite_version"),
            "evidence_reference_count": manifest.get("evidence_reference_count", 0),
            "restore_preview": manifest.get("restore_preview"),
            "summary": manifest.get("summary"),
            "rollback_available": bool(manifest.get("rollback_available")),
            "sanitized": True,
        }
    )


def _upsert_database_backup_record(manifest: dict[str, Any]) -> None:
    """Keep backup metadata available even after restoring an older database snapshot."""
    apply_migrations()
    backup_id = str(manifest.get("backup_id") or "").strip()
    if not backup_id:
        raise RuntimeError("Database backup manifest is missing its backup id")
    with sqlite3.connect(str(database_path())) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            INSERT INTO security_database_backups(
                backup_id, status, created_at, verified_at, file_name, size_bytes,
                sha256, schema_version, sqlite_version, manifest_json, sanitized
            ) VALUES (?, 'verified', ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(backup_id) DO UPDATE SET
                status=excluded.status,
                verified_at=excluded.verified_at,
                file_name=excluded.file_name,
                size_bytes=excluded.size_bytes,
                sha256=excluded.sha256,
                schema_version=excluded.schema_version,
                sqlite_version=excluded.sqlite_version,
                manifest_json=excluded.manifest_json,
                sanitized=1
            """,
            (
                backup_id,
                manifest.get("created_at"),
                manifest.get("verified_at"),
                manifest.get("database_file"),
                int(manifest.get("size_bytes") or 0),
                manifest.get("database_sha256"),
                int(manifest.get("schema_version") or 0),
                manifest.get("sqlite_version"),
                json.dumps(policy.redact_value(manifest), sort_keys=True, separators=(",", ":")),
            ),
        )
        conn.commit()


def _create_database_backup_unlocked(command: dict[str, Any] | None = None) -> dict[str, Any]:
    command = dict(command or {})
    apply_migrations()
    backup_id = _safe_name(str(command.get("backup_id") or command.get("command_id") or _safe_id("db-backup")))
    package = database_backup_package(backup_id)
    if package.exists():
        existing = _read_json(package / "manifest.json", {})
        if isinstance(existing, dict) and existing.get("verification", {}).get("valid"):
            return _api_backup(existing)
        raise RuntimeError("Database backup id already exists")

    requested_at = _utc()
    tmp_package = database_backup_root() / f".{backup_id}.tmp-{uuid.uuid4().hex[:8]}"
    tmp_package.mkdir(parents=True, exist_ok=False)
    db_name = f"pocketlab-lite-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    backup_db = tmp_package / db_name
    progress_state = {"calls": 0, "remaining": None, "total": None}

    def progress(_status: int, remaining: int, total: int) -> None:
        progress_state["calls"] += 1
        progress_state["remaining"] = int(remaining)
        progress_state["total"] = int(total)

    try:
        online_backup(backup_db, progress=progress)
        verification = validate_database_file(backup_db)
        if not verification["valid"]:
            raise RuntimeError("SQLite online backup validation failed")
        migrations = _database_migrations(backup_db)
        orphan_manifest = maintenance.generate_orphan_evidence_manifest()
        with read_connection() as conn:
            evidence_reference_count = int(
                conn.execute("SELECT COUNT(*) FROM security_scan_evidence_refs").fetchone()[0]
            )
        schema_payload = {
            "schema_version": verification["schema_version"],
            "sqlite_version": verification["sqlite_version"],
            "core_tables": sorted(CORE_TABLES),
            "created_at": requested_at,
            "sanitized": True,
        }
        migrations_payload = {
            "schema_version": verification["schema_version"],
            "migrations": migrations,
            "checksums_valid": verification["migration_checksums_valid"],
            "sanitized": True,
        }
        evidence_manifest = {
            "generated_at": orphan_manifest.get("generated_at"),
            "referenced": orphan_manifest.get("referenced"),
            "unreferenced": orphan_manifest.get("unreferenced"),
            "missing": orphan_manifest.get("missing"),
            "hash_mismatch": orphan_manifest.get("hash_mismatch"),
            "automatic_deletion_enabled": False,
            "sanitized": True,
        }
        restore_preview = {
            "status": "available",
            "backup_id": backup_id,
            "schema_version": verification["schema_version"],
            "integrity_check": verification["integrity_check"],
            "requires_confirmation": True,
            "destructive_changes_applied": False,
            "summary": "A restore preview can be generated without changing Pocket Lab.",
            "sanitized": True,
        }
        _write_json(tmp_package / "schema.json", schema_payload)
        _write_json(tmp_package / "migrations.json", migrations_payload)
        _write_json(tmp_package / "evidence-manifest.json", evidence_manifest)
        _write_json(tmp_package / "restore-preview.json", restore_preview)
        receipt = _write_json(
            tmp_package / "receipt.json",
            {
                "backup_id": backup_id,
                "status": "verified",
                "created_at": requested_at,
                "verified_at": _utc(),
                "evidence_saved": True,
                "summary": "Database backup verified.",
                "sanitized": True,
            },
        )
        artifact_hashes = {
            item.name: _sha256(item)
            for item in (
                backup_db,
                tmp_package / "schema.json",
                tmp_package / "migrations.json",
                tmp_package / "evidence-manifest.json",
                tmp_package / "restore-preview.json",
                tmp_package / "receipt.json",
            )
        }
        backup_sha256 = _package_fingerprint(artifact_hashes)
        hashes_payload = {
            "database_file": db_name,
            "database_sha256": verification["sha256"],
            "backup_sha256": backup_sha256,
            "artifact_sha256": artifact_hashes,
            "size_bytes": verification["size_bytes"],
            "sanitized": True,
        }
        _write_json(tmp_package / "hashes.json", hashes_payload)
        manifest = {
            "backup_id": backup_id,
            "status": "verified",
            "created_at": requested_at,
            "verified_at": receipt["verified_at"],
            "database_file": db_name,
            "size_bytes": verification["size_bytes"],
            "database_sha256": verification["sha256"],
            "backup_sha256": backup_sha256,
            "schema_version": verification["schema_version"],
            "sqlite_version": verification["sqlite_version"],
            "logical_identity": "pocketlab-lite-security-state",
            "migration_count": len(migrations),
            "evidence_reference_count": evidence_reference_count,
            "verification": verification,
            "restore_preview": restore_preview,
            "backup_progress": progress_state,
            "excluded": [
                ".env files",
                "restic passwords",
                "NATS credentials",
                "tokens",
                "private keys",
                "raw logs",
                "raw scanner payloads",
            ],
            "summary": "Database backup verified and ready for restore preview.",
            "sanitized": True,
        }
        _write_json(tmp_package / "manifest.json", manifest)
        os.replace(tmp_package, package)
        _fsync_directory(package.parent)

        _upsert_database_backup_record(manifest)
        return _api_backup(manifest)
    except Exception:
        shutil.rmtree(tmp_package, ignore_errors=True)
        raise


def create_database_backup(command: dict[str, Any] | None = None) -> dict[str, Any]:
    state = maintenance.maintenance_state()
    if state.get("active"):
        raise RuntimeError("Database backup is blocked while maintenance is active")
    operation = str((command or {}).get("command_id") or "database-backup")
    with _database_recovery_lock(operation):
        return _create_database_backup_unlocked(command)


def _resolve_backup_id(backup_id: str) -> str | None:
    value = str(backup_id or "latest").strip()
    if value != "latest":
        return value if _is_safe_identifier(value) else None
    items = list_database_backups(limit=1).get("backups") or []
    candidate = str(items[0].get("backup_id") or "") if items else ""
    return candidate if _is_safe_identifier(candidate) else None


def get_database_backup(backup_id: str) -> dict[str, Any] | None:
    resolved = _resolve_backup_id(backup_id)
    if not resolved:
        return None
    manifest = _read_json(database_backup_package(resolved) / "manifest.json", None)
    return _api_backup(manifest) if isinstance(manifest, dict) else None


def list_database_backups(*, limit: int = 25) -> dict[str, Any]:
    max_items = max(1, min(int(limit), 100))
    manifests: list[dict[str, Any]] = []
    for path in sorted(
        (item for item in database_backup_root().iterdir() if item.is_dir() and not item.name.startswith("." ) and item.name not in {"rollback", "restore-previews", "restore-runs"}),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        manifest = _read_json(path / "manifest.json", None)
        if isinstance(manifest, dict):
            manifests.append(_api_backup(manifest))
        if len(manifests) >= max_items:
            break
    return {
        "status": "healthy" if manifests else "empty",
        "count": len(manifests),
        "backups": manifests,
        "latest_backup": manifests[0] if manifests else None,
        "updated_at": _utc(),
        "sanitized": True,
    }


def verify_database_backup(backup_id: str) -> dict[str, Any]:
    resolved = _resolve_backup_id(backup_id)
    if not resolved:
        raise RuntimeError("Database backup was not found")
    package = database_backup_package(resolved)
    manifest = _read_json(package / "manifest.json", None)
    hashes = _read_json(package / "hashes.json", None)
    if not isinstance(manifest, dict) or not isinstance(hashes, dict):
        raise RuntimeError("Database backup manifest is missing")
    db_file = package / str(manifest.get("database_file") or "")
    validation = validate_database_file(db_file)
    if str(hashes.get("database_sha256") or "") != validation["sha256"]:
        raise RuntimeError("Database backup hash does not match")
    expected_artifacts = hashes.get("artifact_sha256")
    if not isinstance(expected_artifacts, dict) or not expected_artifacts:
        raise RuntimeError("Database backup artifact hashes are missing")
    actual_artifacts: dict[str, str] = {}
    for name, expected_hash in expected_artifacts.items():
        if not _is_safe_identifier(Path(str(name)).stem) or Path(str(name)).name != str(name):
            raise RuntimeError("Database backup artifact name is invalid")
        artifact = package / str(name)
        if not artifact.is_file():
            raise RuntimeError("Database backup artifact is missing")
        actual_hash = _sha256(artifact)
        if actual_hash != str(expected_hash or ""):
            raise RuntimeError("Database backup artifact hash does not match")
        actual_artifacts[str(name)] = actual_hash
    backup_sha256 = _package_fingerprint(actual_artifacts)
    if str(hashes.get("backup_sha256") or "") != backup_sha256:
        raise RuntimeError("Database backup package hash does not match")
    if str(manifest.get("backup_sha256") or "") != backup_sha256:
        raise RuntimeError("Database backup manifest hash does not match")
    if int(manifest.get("schema_version") or 0) != validation["schema_version"]:
        raise RuntimeError("Database backup schema version does not match")
    if not validation["valid"]:
        raise RuntimeError("Database backup validation failed")
    manifest["status"] = "verified"
    manifest["verified_at"] = _utc()
    manifest["verification"] = validation
    _write_json(package / "manifest.json", manifest)
    return {**_api_backup(manifest), "verification": validation}


def _table_counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(path))
    try:
        counts: dict[str, int] = {}
        for table in (
            "security_scan_runs",
            "security_scan_progress_events",
            "security_scan_findings",
            "security_scan_tool_runs",
            "security_scan_evidence_refs",
            "security_profile_snapshots",
        ):
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts
    finally:
        conn.close()


def create_database_restore_preview(backup_id: str) -> dict[str, Any]:
    resolved = _resolve_backup_id(backup_id)
    if not resolved:
        raise RuntimeError("Database backup was not found")
    verification = verify_database_backup(resolved)
    package = database_backup_package(resolved)
    manifest = _read_json(package / "manifest.json", {})
    backup_db = package / str(manifest.get("database_file") or "")
    current_counts = _table_counts(database_path())
    backup_counts = _table_counts(backup_db)
    preview_id = _safe_id("db-preview")
    preview = {
        "preview_id": preview_id,
        "backup_id": resolved,
        "status": "ready",
        "created_at": _utc(),
        "restore_allowed": True,
        "requires_confirmation": True,
        "destructive_changes_applied": False,
        "schema_version": verification.get("schema_version"),
        "current_counts": current_counts,
        "backup_counts": backup_counts,
        "changes": {
            key: int(backup_counts.get(key, 0)) - int(current_counts.get(key, 0))
            for key in sorted(set(current_counts) | set(backup_counts))
        },
        "active_scan_blocked": bool(maintenance.active_security_scan()),
        "summary": "Restore preview ready. No database files were replaced.",
        "sanitized": True,
    }
    if preview["active_scan_blocked"]:
        preview["restore_allowed"] = False
        preview["status"] = "blocked"
        preview["summary"] = "Restore is blocked while a Security scan is active."
    _write_json(database_restore_preview_path(preview_id), preview)
    return preview


def get_database_restore_preview(preview_id: str) -> dict[str, Any] | None:
    if not _is_safe_identifier(preview_id):
        return None
    payload = _read_json(database_restore_preview_path(preview_id), None)
    return payload if isinstance(payload, dict) else None


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(str(path), flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _refresh_security_projections() -> dict[str, Any]:
    try:
        from . import lite_security

        _repository, state, _revision = lite_security._sqlite_state_projection()
        evidence.write_state(state)
        lite_security.write_compact_security_state(state)
        return {"status": "passed", "summary": "Security projections refreshed."}
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__, "summary": "Security projection refresh failed."}


def _parity_check() -> dict[str, Any]:
    try:
        from .lite_security_store import SecuritySQLiteRepository

        state = evidence.read_state()
        if not isinstance(state, dict):
            return {"status": "unavailable", "matched": None, "summary": "Compatibility state is not available."}
        result = SecuritySQLiteRepository().compare_json_state(state, record=False)
        return {"status": "passed" if result.get("matched") else "failed", **result}
    except Exception as exc:
        return {"status": "failed", "matched": False, "error_type": type(exc).__name__}


def _record_restore_result(result: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Persist a sanitized restore audit row in the currently active database."""
    _upsert_database_backup_record(manifest)
    completed_at = result.get("completed_at") or result.get("failed_at")
    with sqlite3.connect(str(database_path())) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            INSERT OR REPLACE INTO security_database_restores(
                restore_id, backup_id, preview_id, state, requested_at, completed_at,
                rollback_file_name, summary, metadata_json, sanitized
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                result.get("restore_id"),
                result.get("backup_id"),
                result.get("preview_id"),
                result.get("state"),
                result.get("started_at"),
                completed_at,
                result.get("rollback_file_name"),
                result.get("summary"),
                json.dumps(policy.redact_value(result), sort_keys=True, separators=(",", ":")),
            ),
        )
        conn.commit()


def _restore_database_backup_unlocked(command: dict[str, Any]) -> dict[str, Any]:
    if not bool(command.get("confirm")):
        raise RuntimeError("Explicit restore confirmation is required")
    backup_id = _resolve_backup_id(str(command.get("backup_id") or ""))
    preview_id = str(command.get("preview_id") or "").strip()
    if not backup_id or not preview_id:
        raise RuntimeError("Restore requires an explicit backup and preview id")
    preview = get_database_restore_preview(preview_id)
    if not preview or preview.get("backup_id") != backup_id:
        raise RuntimeError("Restore preview does not match the selected backup")
    if preview.get("status") != "ready" or not preview.get("restore_allowed"):
        raise RuntimeError("Restore preview is not ready")
    if maintenance.active_security_scan():
        raise RuntimeError("Restore is blocked while a Security scan is active")

    verification = verify_database_backup(backup_id)
    package = database_backup_package(backup_id)
    manifest = _read_json(package / "manifest.json", {})
    source_db = package / str(manifest.get("database_file") or "")
    restore_id = _safe_name(str(command.get("restore_id") or command.get("command_id") or _safe_id("db-restore")))
    started_at = _utc()
    live_db = database_path()
    rollback_name = f"pocketlab-lite-pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{restore_id[-8:]}.sqlite3"
    rollback_db = database_backup_root() / "rollback" / rollback_name
    staged_restore = live_db.with_name(f".{live_db.name}.{restore_id}.restore.tmp")
    result: dict[str, Any]

    maintenance.enter_maintenance(operation_id=restore_id, kind="database_restore")
    try:
        maintenance.update_maintenance(restore_id, state="validating", summary="Validating the selected database backup.")
        validate_database_file(source_db)
        if maintenance.active_security_scan():
            raise RuntimeError("Restore was blocked by a newly active Security scan")

        maintenance.update_maintenance(restore_id, state="stopping_writers", writers_stopped=True, summary="Database writers are quiesced for restore.")
        grace_seconds = max(0.0, min(float(os.environ.get("POCKETLAB_LITE_RESTORE_QUIESCE_SECONDS", "0.25")), 5.0))
        if grace_seconds:
            time.sleep(grace_seconds)
        maintenance.run_wal_checkpoint(mode="TRUNCATE", operation_id=restore_id, writers_stopped=True)

        maintenance.update_maintenance(restore_id, state="creating_rollback", writers_stopped=True, summary="Creating a validated rollback copy.")
        online_backup(rollback_db)
        rollback_validation = validate_database_file(rollback_db)
        if not rollback_validation["valid"]:
            raise RuntimeError("Rollback copy validation failed")

        maintenance.update_maintenance(restore_id, state="replacing", writers_stopped=True, summary="Replacing the database atomically.")
        shutil.copy2(source_db, staged_restore)
        _fsync_file(staged_restore)
        staged_validation = validate_database_file(staged_restore)
        if not staged_validation["valid"]:
            raise RuntimeError("Staged restore database validation failed")
        os.replace(staged_restore, live_db)
        _fsync_directory(live_db.parent)

        maintenance.update_maintenance(restore_id, state="restarting", writers_stopped=True, summary="Reopening Pocket Lab database services safely.")
        apply_migrations()
        _upsert_database_backup_record(manifest)
        gate_fault_enabled = str(os.environ.get("POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if bool(command.get("gate_fail_after_replace")) and gate_fault_enabled:
            raise RuntimeError("Bounded S8 post-replacement verification fault")
        maintenance.update_maintenance(restore_id, state="verifying", writers_stopped=True, summary="Verifying restored Pocket Lab state.")
        restored_validation = validate_database_file(live_db)
        projection = _refresh_security_projections()
        parity = _parity_check()
        quick_ok = restored_validation.get("quick_check") == "ok"
        if not restored_validation.get("valid") or not quick_ok or projection.get("status") != "passed" or parity.get("matched") is not True:
            raise RuntimeError("Post-restore verification failed")

        completed_at = _utc()
        result = {
            "status": "completed",
            "state": "completed",
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "rollback_available": True,
            "rollback_file_name": rollback_name,
            "verification": restored_validation,
            "projection": projection,
            "parity": parity,
            "manual_wal_file_deletion": False,
            "summary": "Database recovery completed. Rollback remains available.",
            "sanitized": True,
        }
        _write_json(database_restore_run_path(restore_id), result)
        _record_restore_result(result, manifest)
        maintenance.leave_maintenance(restore_id, state="completed", summary="Database recovery completed.")
        return result
    except Exception as exc:
        rollback_result = {"attempted": False, "status": "not_available"}
        if rollback_db.exists():
            rollback_result = {"attempted": True, "status": "rolling_back"}
            try:
                maintenance.update_maintenance(restore_id, state="rolling_back", writers_stopped=True, summary="Restore verification failed. Rolling back safely.")
                rollback_stage = live_db.with_name(f".{live_db.name}.{restore_id}.rollback.tmp")
                shutil.copy2(rollback_db, rollback_stage)
                _fsync_file(rollback_stage)
                if not validate_database_file(rollback_stage)["valid"]:
                    raise RuntimeError("Rollback database validation failed")
                os.replace(rollback_stage, live_db)
                _fsync_directory(live_db.parent)
                apply_migrations()
                rollback_validation = validate_database_file(live_db)
                projection = _refresh_security_projections()
                parity = _parity_check()
                rollback_result = {
                    "attempted": True,
                    "status": "completed" if rollback_validation.get("valid") and projection.get("status") == "passed" and parity.get("matched") is True else "failed",
                    "verification": rollback_validation,
                    "projection": projection,
                    "parity": parity,
                }
            except Exception as rollback_exc:
                rollback_result = {"attempted": True, "status": "failed", "error_type": type(rollback_exc).__name__}
        failed = {
            "status": "failed",
            "state": "failed",
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "started_at": started_at,
            "failed_at": _utc(),
            "error_type": type(exc).__name__,
            "summary": "Database restore failed. Automatic rollback was attempted.",
            "rollback": rollback_result,
            "rollback_available": rollback_db.exists(),
            "rollback_file_name": rollback_name if rollback_db.exists() else None,
            "manual_wal_file_deletion": False,
            "sanitized": True,
        }
        _write_json(database_restore_run_path(restore_id), failed)
        try:
            _record_restore_result(failed, manifest)
        except Exception:
            pass
        try:
            maintenance.leave_maintenance(restore_id, state="failed", summary=failed["summary"])
        except Exception:
            pass
        raise RuntimeError(failed["summary"]) from exc
    finally:
        try:
            staged_restore.unlink()
        except FileNotFoundError:
            pass


def restore_database_backup(command: dict[str, Any]) -> dict[str, Any]:
    operation = str(command.get("command_id") or command.get("restore_id") or "database-restore")
    with _database_recovery_lock(operation):
        return _restore_database_backup_unlocked(command)


def get_database_restore_run(restore_id: str) -> dict[str, Any] | None:
    if not _is_safe_identifier(restore_id):
        return None
    payload = _read_json(database_restore_run_path(restore_id), None)
    return payload if isinstance(payload, dict) else None


def database_recovery_status() -> dict[str, Any]:
    backups = list_database_backups(limit=25)
    latest_preview = None
    previews = sorted((database_backup_root() / "restore-previews").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if previews:
        latest_preview = _read_json(previews[0], None)
    latest_restore = None
    restores = sorted((database_backup_root() / "restore-runs").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if restores:
        latest_restore = _read_json(restores[0], None)
    return {
        "status": "maintenance" if maintenance.maintenance_state().get("active") else ("healthy" if backups.get("count") else "ready"),
        "summary": "Database protection is ready." if backups.get("count") else "Create a verified Pocket Lab database backup.",
        "latest_backup": backups.get("latest_backup"),
        "backup_history": backups.get("backups"),
        "latest_restore_preview": latest_preview,
        "last_restore": latest_restore,
        "maintenance": maintenance.maintenance_state(),
        "wal": maintenance.wal_diagnostics(),
        "rollback_available": bool(latest_restore and latest_restore.get("rollback_available")),
        "updated_at": _utc(),
        "sanitized": True,
    }
