from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
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
from . import lite_restore_transaction as restore_txn

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
        foreign_key_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
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
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        conn.close()
    migration_ok, migration_summary = _validate_migration_contract(migrations)
    missing_tables = sorted(CORE_TABLES - tables)
    supported_migrations = discover_migrations()
    current_version = max((item.version for item in supported_migrations), default=0)
    schema_current = schema_version == current_version
    foreign_keys_clean = not foreign_key_rows
    valid = (
        integrity == "ok"
        and quick_check == "ok"
        and foreign_keys_clean
        and migration_ok
        and not missing_tables
    )
    return {
        "valid": valid,
        "integrity_check": integrity,
        "quick_check": quick_check,
        "foreign_keys_clean": foreign_keys_clean,
        "foreign_key_violation_count": len(foreign_key_rows),
        "schema_version": schema_version,
        "current_schema_version": current_version,
        "schema_current": schema_current,
        "migration_checksums_valid": migration_ok,
        "migration_summary": migration_summary,
        "missing_core_tables": missing_tables,
        "journal_mode": journal_mode,
        "standalone_database": not any(
            candidate.with_name(candidate.name + suffix).exists()
            for suffix in ("-wal", "-shm")
        ),
        "sqlite_version": sqlite3.sqlite_version,
        "size_bytes": candidate.stat().st_size,
        "sha256": _sha256(candidate),
        "sanitized": True,
    }


def _migration_statements(sql: str):
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise RuntimeError("Migration SQL is incomplete")


def _apply_migrations_to_database(path: Path) -> list[int]:
    """Bring a staged standalone database to the current schema before promotion."""
    applied_now: list[int] = []
    migrations = discover_migrations()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        )
        applied = {
            int(row["version"]): (str(row["name"]), str(row["checksum"]))
            for row in conn.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            )
        }
        known_versions = {item.version for item in migrations}
        unexpected = sorted(set(applied) - known_versions)
        if unexpected:
            raise RuntimeError("Database schema is newer than this Pocket Lab version")
        for migration in migrations:
            prior = applied.get(migration.version)
            if prior:
                if prior != (migration.name, migration.checksum):
                    raise RuntimeError("Migration checksum or name does not match")
                continue
            for statement in _migration_statements(migration.sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, _utc(), migration.checksum),
            )
            applied_now.append(migration.version)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return applied_now


def _canonical_projection_from_json() -> dict[str, Any]:
    from . import lite_security_store as store

    state = evidence.read_state()
    if isinstance(state, dict):
        return policy.redact_value(store._json_shadow_projection(state))
    # Early SQLite-only fixtures may not have emitted compatibility JSON yet.
    # Seed the package projection from the already validated authoritative DB;
    # production backups normally use the canonical JSON source above.
    return _database_projection(database_path())


def _database_projection(path: Path) -> dict[str, Any]:
    from .lite_security_store import SecuritySQLiteRepository

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        repository = SecuritySQLiteRepository(initialize=False)
        return policy.redact_value(repository._sqlite_shadow_projection(conn=conn))
    finally:
        conn.close()


def _projection_checksum(projection: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _compare_projection(expected: dict[str, Any], path: Path) -> dict[str, Any]:
    from . import lite_security_store as store

    actual = _database_projection(path)
    result = store._compare_projections(expected, actual)
    return policy.redact_value({**result, "expected_checksum": _projection_checksum(expected), "actual_checksum": _projection_checksum(actual)})


def _remove_sqlite_sidecars(path: Path) -> list[str]:
    removed: list[str] = []
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        try:
            sidecar.unlink()
            removed.append(suffix[1:])
        except FileNotFoundError:
            continue
    if removed:
        _fsync_directory(path.parent)
    return removed


def _bump_security_revision_once(path: Path) -> int:
    now = _utc()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO domain_revisions(domain, revision, updated_at)
            VALUES ('security', 1, ?)
            ON CONFLICT(domain) DO UPDATE SET
                revision = domain_revisions.revision + 1,
                updated_at = excluded.updated_at
            """,
            (now,),
        )
        row = conn.execute(
            "SELECT revision FROM domain_revisions WHERE domain='security'"
        ).fetchone()
        conn.commit()
        return int(row[0]) if row else 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
        canonical_projection = _canonical_projection_from_json()
        projection_compare = _compare_projection(canonical_projection, backup_db)
        if projection_compare.get("matched") is not True:
            raise RuntimeError("SQLite online backup canonical projection validation failed")
        projection_payload = {
            "projection": canonical_projection,
            "projection_checksum": _projection_checksum(canonical_projection),
            "database_projection_checksum": projection_compare.get("actual_checksum"),
            "matched": True,
            "created_at": requested_at,
            "sanitized": True,
        }
        restore_preview = {
            "status": "available",
            "backup_id": backup_id,
            "schema_version": verification["schema_version"],
            "integrity_check": verification["integrity_check"],
            "foreign_keys_clean": verification["foreign_keys_clean"],
            "canonical_parity": True,
            "requires_confirmation": True,
            "destructive_changes_applied": False,
            "summary": "A restore preview can be generated without changing Pocket Lab.",
            "sanitized": True,
        }
        _write_json(tmp_package / "schema.json", schema_payload)
        _write_json(tmp_package / "migrations.json", migrations_payload)
        _write_json(tmp_package / "evidence-manifest.json", evidence_manifest)
        _write_json(tmp_package / "canonical-projection.json", projection_payload)
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
                tmp_package / "canonical-projection.json",
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
            "package_format_version": 2,
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
            "canonical_projection_file": "canonical-projection.json",
            "canonical_projection_checksum": projection_payload["projection_checksum"],
            "canonical_parity": True,
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
    projection_name = str(manifest.get("canonical_projection_file") or "")
    if int(manifest.get("package_format_version") or 1) >= 2:
        if not projection_name or Path(projection_name).name != projection_name:
            raise RuntimeError("Database backup canonical projection is missing")
        projection_payload = _read_json(package / projection_name, None)
        if not isinstance(projection_payload, dict) or not isinstance(projection_payload.get("projection"), dict):
            raise RuntimeError("Database backup canonical projection is invalid")
        expected_projection = projection_payload["projection"]
        expected_checksum = _projection_checksum(expected_projection)
        if expected_checksum != str(projection_payload.get("projection_checksum") or ""):
            raise RuntimeError("Database backup canonical projection checksum does not match")
        projection_compare = _compare_projection(expected_projection, db_file)
        if projection_compare.get("matched") is not True:
            raise RuntimeError("Database backup canonical projection validation failed")
        manifest["canonical_parity"] = True
        manifest["canonical_projection_checksum"] = expected_checksum
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


def _reconcile_security_run_projections(repository: Any) -> dict[str, Any]:
    """Make derived run JSON exactly match the restored SQLite run set.

    ``security/runs`` is compatibility output, not evidence.  Restore may move
    SQLite backwards to a verified backup, so run projection files created
    after that backup must not survive as canonical "future" runs.  Evidence
    directories are intentionally untouched.
    """
    from . import lite_security

    expected: set[str] = set()
    written = 0
    cursor_epoch_ms: int | None = None
    cursor_run_id: str | None = None
    while True:
        page = repository.list_runs_page(
            limit=200,
            cursor_epoch_ms=cursor_epoch_ms,
            cursor_run_id=cursor_run_id,
        )
        rows = page.get("runs") if isinstance(page, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            run_id = str(row.get("run_id") or "")
            if not run_id:
                continue
            payload = lite_security._sqlite_run_payload(
                repository,
                row,
                include_details=True,
                include_related=True,
            ) or row
            evidence.write_run(run_id, payload)
            expected.add(f"{evidence.safe_run_id(run_id)}.json")
            written += 1
        next_cursor = page.get("next_cursor") if isinstance(page, dict) else None
        if not page.get("has_more") or not isinstance(next_cursor, dict):
            break
        cursor_epoch_ms = int(next_cursor.get("epoch_ms") or 0)
        cursor_run_id = str(next_cursor.get("run_id") or "")
        if cursor_epoch_ms <= 0 or not cursor_run_id:
            raise RuntimeError("Security run projection cursor is invalid")

    removed = 0
    runs_directory = evidence.runs_dir()
    for path in sorted(runs_directory.glob("*.json")):
        if path.name not in expected:
            path.unlink()
            removed += 1
    _fsync_directory(runs_directory)
    return {
        "status": "passed",
        "written_run_projections": written,
        "removed_stale_run_projections": removed,
        "evidence_files_deleted": False,
    }


def _refresh_security_projections() -> dict[str, Any]:
    try:
        from . import lite_security

        repository, state, _revision = lite_security._sqlite_state_projection()
        runs = _reconcile_security_run_projections(repository)
        evidence.write_state(state)
        lite_security.write_compact_security_state(state)
        lite_security.invalidate_security_read_caches()
        progress = lite_security.fence_security_progress_after_database_restore(
            repository=repository,
        )
        return {
            "status": "passed",
            "summary": "Security projections refreshed.",
            "runs": runs,
            "progress": progress,
        }
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__, "summary": "Security projection refresh failed."}


def _parity_check() -> dict[str, Any]:
    try:
        from .lite_security_store import SecuritySQLiteRepository

        result = SecuritySQLiteRepository().compare_legacy_source(
            source_root=evidence.security_root(),
            record=False,
        )
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




def _truncate_wal_for_restore(path: Path) -> dict[str, Any]:
    """Checkpoint WAL without mutating Pocket Lab lifecycle/audit tables."""
    conn = sqlite3.connect(str(path), timeout=15)
    try:
        row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        conn.close()
    busy, log_frames, checkpointed_frames = (int(row[0]), int(row[1]), int(row[2]))
    if busy or quick != "ok":
        raise RuntimeError("Restore WAL checkpoint did not quiesce cleanly")
    return {
        "checkpoint_busy": busy,
        "checkpoint_log_frames": log_frames,
        "checkpointed_frames": checkpointed_frames,
        "quick_check": quick,
        "manual_wal_file_deletion": False,
    }


def _security_projection_targets() -> list[Path]:
    """Files derived from Security lifecycle state that must move with SQLite."""
    targets: list[Path] = [evidence.state_path()]
    runs = evidence.runs_dir()
    if runs.exists():
        targets.extend(sorted(path for path in runs.glob("*.json") if path.is_file()))
    compact = evidence.security_root() / "compact"
    if compact.exists():
        targets.extend(sorted(path for path in compact.rglob("*.json") if path.is_file()))
    # Keep expected compact roots in the checkpoint even when absent so rollback
    # can remove files created by a failed restore.
    expected = [
        compact / "security_summary.json",
        compact / "security_freshness.json",
        compact / "security_progress.json",
        compact / "security_history_index.json",
        compact / "profile_latest.json",
        compact / "coverage_summary_compact.json",
    ]
    targets.extend(path for path in expected if path not in targets)
    return sorted(set(targets), key=lambda item: str(item))


def _relative_state_path(path: Path) -> str:
    root = deps.settings().state_dir.resolve()
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("Restore state target is outside the Pocket Lab state directory") from exc


def _copy_file_durable(source: Path, target: Path, *, mode: int | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        shutil.copyfile(source, temporary)
        if mode is not None:
            os.chmod(temporary, stat.S_IMODE(mode))
        _fsync_file(temporary)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _checkpoint_state_files(restore_id: str) -> dict[str, Any]:
    checkpoint_root = restore_txn.restore_transaction_dir(restore_id) / "checkpoint" / "state-files"
    records: list[dict[str, Any]] = []
    for source in _security_projection_targets():
        relative = _relative_state_path(source)
        record: dict[str, Any] = {"relative_path": relative, "existed": source.is_file()}
        if source.is_file():
            source_stat = source.stat()
            target = checkpoint_root / relative
            _copy_file_durable(source, target, mode=source_stat.st_mode)
            record.update(
                {
                    "size_bytes": source_stat.st_size,
                    "sha256": _sha256(source),
                    "mode": stat.S_IMODE(source_stat.st_mode),
                }
            )
        records.append(record)
    manifest = {
        "checkpoint_id": f"checkpoint-{restore_id}",
        "created_at": _utc(),
        "files": records,
        "sanitized": True,
    }
    restore_txn.atomic_write_json(
        restore_txn.restore_transaction_dir(restore_id) / "checkpoint" / "state-files.json",
        manifest,
    )
    return manifest


def _restore_checkpoint_state_files(restore_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    state_root = deps.settings().state_dir.resolve()
    checkpoint_root = restore_txn.restore_transaction_dir(restore_id) / "checkpoint" / "state-files"
    records = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    expected: set[str] = set()
    restored = 0
    removed = 0
    # Remove generated compatibility projections that did not exist in the
    # checkpoint.  Security evidence is deliberately outside these roots.
    compact = evidence.security_root() / "compact"
    runs = evidence.runs_dir()
    checkpoint_relatives = {
        str(item.get("relative_path"))
        for item in records
        if isinstance(item, dict) and item.get("relative_path")
    }
    for projection_root, recursive in ((compact, True), (runs, False)):
        if not projection_root.exists():
            continue
        candidates = projection_root.rglob("*.json") if recursive else projection_root.glob("*.json")
        for current in sorted(candidates, reverse=True):
            relative = _relative_state_path(current)
            if relative not in checkpoint_relatives:
                current.unlink(missing_ok=True)
                removed += 1
        _fsync_directory(projection_root)
    for item in reversed(records):
        if not isinstance(item, dict):
            continue
        relative = str(item.get("relative_path") or "")
        if not relative:
            continue
        destination = (state_root / relative).resolve(strict=False)
        try:
            destination.relative_to(state_root)
        except ValueError as exc:
            raise RuntimeError("Checkpoint contains an unsafe state path") from exc
        expected.add(relative)
        if not bool(item.get("existed")):
            if destination.exists():
                destination.unlink()
                removed += 1
            continue
        source = checkpoint_root / relative
        if not source.is_file() or _sha256(source) != str(item.get("sha256") or ""):
            raise RuntimeError("Checkpoint state file validation failed")
        _copy_file_durable(source, destination, mode=int(item.get("mode") or 0o600))
        if _sha256(destination) != str(item.get("sha256") or ""):
            raise RuntimeError("Restored state file checksum does not match checkpoint")
        restored += 1
    return {"restored_files": restored, "removed_files": removed, "expected_files": len(expected)}


def _read_state_file_manifest(restore_id: str) -> dict[str, Any]:
    path = restore_txn.restore_transaction_dir(restore_id) / "checkpoint" / "state-files.json"
    payload = _read_json(path, {})
    if not isinstance(payload, dict):
        raise RuntimeError("Restore checkpoint state manifest is unavailable")
    return payload


def _database_revision(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT revision FROM domain_revisions WHERE domain='security'"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _required_free_bytes(source_db: Path, live_db: Path, state_manifest: dict[str, Any] | None = None) -> int:
    state_bytes = sum(
        int(item.get("size_bytes") or 0)
        for item in (state_manifest or {}).get("files", [])
        if isinstance(item, dict) and item.get("existed")
    )
    # checkpoint + staging + same-directory promotion temp + bounded safety reserve
    return max(32 * 1024 * 1024, source_db.stat().st_size * 3 + live_db.stat().st_size + state_bytes * 2)


def _ensure_restore_space(source_db: Path, live_db: Path, state_manifest: dict[str, Any] | None = None) -> dict[str, int]:
    usage = shutil.disk_usage(live_db.parent)
    required = _required_free_bytes(source_db, live_db, state_manifest)
    if usage.free < required:
        raise RuntimeError("Insufficient free space for a validated restore and rollback checkpoint")
    return {"free_bytes": int(usage.free), "required_bytes": int(required)}


def _restore_run_snapshot(
    journal: dict[str, Any], *, persist: bool = True, **extra: Any
) -> dict[str, Any]:
    public = restore_txn.public_journal_view(journal) or {}
    phase = str(public.get("phase") or "created")
    terminal = phase in restore_txn.TERMINAL_PHASES
    state = "completed" if phase == "committed" else "failed" if terminal else "running"
    payload = {
        **public,
        "state": state,
        "status": state,
        "rollback_available": bool(journal.get("checkpoint_hashes")),
        "rollback": journal.get("rollback") if isinstance(journal.get("rollback"), dict) else None,
        "summary": journal.get("summary") or public.get("summary"),
        "sanitized": True,
        **extra,
    }
    if persist:
        _write_json(database_restore_run_path(str(journal.get("restore_id") or "unknown")), payload)
    return payload


def _transition(restore_id: str, phase: str, summary: str, **updates: Any) -> dict[str, Any]:
    journal = restore_txn.update_journal(
        restore_id,
        phase=phase,
        summary=summary,
        **updates,
    )
    maintenance.update_maintenance(
        restore_id,
        state=phase,
        writers_stopped=phase not in {"created", "checkpointing"},
        summary=summary,
    )
    _restore_run_snapshot(journal)
    return journal


def _promote_database(source: Path, live_db: Path) -> dict[str, Any]:
    temporary = live_db.with_name(f".{live_db.name}.{uuid.uuid4().hex[:8]}.promote.tmp")
    try:
        shutil.copyfile(source, temporary)
        _fsync_file(temporary)
        staged_hash = _sha256(temporary)
        _remove_sqlite_sidecars(live_db)
        os.replace(temporary, live_db)
        _fsync_directory(live_db.parent)
        active_hash = _sha256(live_db)
        if active_hash != staged_hash:
            raise RuntimeError("Promoted database checksum does not match staged database")
        return {"sha256": active_hash, "size_bytes": live_db.stat().st_size}
    finally:
        temporary.unlink(missing_ok=True)


def _rollback_transaction(
    restore_id: str,
    *,
    failure: BaseException | None = None,
) -> dict[str, Any]:
    journal = restore_txn.read_journal(restore_id)
    if not journal:
        raise RuntimeError("Restore journal is unavailable for rollback")
    checkpoint_db = restore_txn.checkpoint_database_path(restore_id)
    live_db = database_path()
    attempts = int(journal.get("rollback_attempt_count") or 0) + 1
    category = restore_txn.safe_failure_category(failure) if failure else str(journal.get("restore_failure_category") or "restore_interrupted")
    journal = _transition(
        restore_id,
        "rollback_started",
        "Restore did not commit. Pocket Lab is restoring the validated checkpoint.",
        rollback_attempt_count=attempts,
        restore_failure_category=category,
        failure_category=category,
        status="running",
        api_worker_restart_allowed=False,
        rollback={"status": "running", "attempted": True},
    )
    try:
        restore_txn.inject_fault("during_rollback")
        expected_hash = str((journal.get("checkpoint_hashes") or {}).get("database") or "")
        if not checkpoint_db.is_file() or not expected_hash or _sha256(checkpoint_db) != expected_hash:
            raise RuntimeError("Rollback checkpoint database checksum does not match")
        promoted = _promote_database(checkpoint_db, live_db)
        restore_txn.inject_fault("after_rollback_promotion")
        files_result = _restore_checkpoint_state_files(restore_id, _read_state_file_manifest(restore_id))
        journal = _transition(
            restore_id,
            "rollback_validating",
            "Pocket Lab is validating the recovered checkpoint.",
            active_hashes={"database": promoted["sha256"]},
            rollback={"status": "validating", "attempted": True, **files_result},
        )
        validation = validate_database_file(live_db)
        if not validation.get("valid") or not validation.get("schema_current"):
            raise RuntimeError("Rollback database validation failed")
        if _sha256(live_db) != expected_hash:
            raise RuntimeError("Rollback database checksum is not identical to checkpoint")
        checkpoint_projection = journal.get("checkpoint_projection")
        if isinstance(checkpoint_projection, dict):
            parity = _compare_projection(checkpoint_projection, live_db)
            if parity.get("matched") is not True:
                raise RuntimeError("Rollback canonical projection does not match checkpoint")
        # Compatibility files were restored byte-for-byte above; do not regenerate
        # them here because exact rollback is part of the transaction contract.
        completed_at = _utc()
        journal = restore_txn.update_journal(
            restore_id,
            phase="rolled_back",
            summary="Restore failed safely. The pre-restore checkpoint was recovered and validated.",
            status="failed",
            terminal_status="rolled_back",
            completed_at=completed_at,
            api_worker_restart_allowed=True,
            rollback={
                "status": "rolled_back",
                "attempted": True,
                "verification": validation,
                "checkpoint_database_hash_matched": True,
                **files_result,
            },
        )
        result = _restore_run_snapshot(journal, failed_at=completed_at)
        maintenance.leave_maintenance(
            restore_id,
            state="rolled_back",
            summary="Restore failed safely and the validated checkpoint was recovered.",
        )
        return result
    except Exception as rollback_error:
        failed_at = _utc()
        journal = restore_txn.update_journal(
            restore_id,
            phase="rollback_failed",
            summary="Automatic rollback could not be validated. Database writers remain blocked.",
            status="failed",
            terminal_status="rollback_failed",
            completed_at=failed_at,
            failure_category="rollback_validation_failed",
            rollback_failure_category=restore_txn.safe_failure_category(rollback_error),
            api_worker_restart_allowed=False,
            rollback={
                "status": "rollback_failed",
                "attempted": True,
                "error_type": type(rollback_error).__name__,
            },
        )
        result = _restore_run_snapshot(journal, failed_at=failed_at)
        # Deliberately do not clear maintenance. The supervisor and startup guard
        # keep writers stopped until an operator repairs the checkpoint issue.
        return result


def _abandon_before_promotion(restore_id: str, error: BaseException) -> dict[str, Any]:
    completed_at = _utc()
    journal = restore_txn.update_journal(
        restore_id,
        phase="rolled_back",
        summary="Restore stopped before active data changed.",
        status="failed",
        terminal_status="rolled_back",
        completed_at=completed_at,
        restore_failure_category=restore_txn.safe_failure_category(error),
        failure_category=restore_txn.safe_failure_category(error),
        api_worker_restart_allowed=True,
        rollback={"status": "not_required", "attempted": False},
    )
    result = _restore_run_snapshot(journal, failed_at=completed_at)
    maintenance.leave_maintenance(
        restore_id,
        state="rolled_back",
        summary="Restore stopped before promotion. Active data was unchanged.",
    )
    return result


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
    existing_guard = restore_txn.guard_status()
    restore_id = _safe_name(str(command.get("restore_id") or command.get("command_id") or _safe_id("db-restore")))
    if existing_guard.get("unresolved") and existing_guard.get("restore_id") != restore_id:
        raise RuntimeError("Another restore transaction requires recovery")

    verify_database_backup(backup_id)
    package = database_backup_package(backup_id)
    manifest = _read_json(package / "manifest.json", {})
    source_db = package / str(manifest.get("database_file") or "")
    canonical_file = package / str(manifest.get("canonical_projection_file") or "canonical-projection.json")
    projection_payload = _read_json(canonical_file, None)
    expected_projection = (
        projection_payload.get("projection")
        if isinstance(projection_payload, dict)
        else None
    )
    if not isinstance(expected_projection, dict):
        raise RuntimeError("Backup canonical projection is unavailable")
    live_db = database_path()
    started_at = _utc()
    checkpoint_db = restore_txn.checkpoint_database_path(restore_id)
    staged_db = restore_txn.staged_database_path(restore_id)
    promoted = False

    journal = restore_txn.read_journal(restore_id)
    if journal and journal.get("phase") in {"committed", "rolled_back"}:
        return _restore_run_snapshot(journal)
    if journal:
        return recover_restore_transaction(restore_id)

    if maintenance.maintenance_state().get("active"):
        raise RuntimeError("Another maintenance operation is already active")
    journal = restore_txn.create_journal(
        restore_id=restore_id,
        backup_id=backup_id,
        preview_id=preview_id,
        target_names=["pocketlab-lite.sqlite3", "security_state.json", "security/runs/*.json", "security/compact/*.json"],
    )
    maintenance.enter_maintenance(operation_id=restore_id, kind="database_restore")
    journal = restore_txn.update_journal(
        restore_id,
        summary="Preparing a validated restore transaction.",
        started_at=started_at,
        source_package_fingerprint=manifest.get("package_fingerprint"),
    )
    _restore_run_snapshot(journal)
    try:
        _transition(restore_id, "checkpointing", "Creating a validated pre-restore checkpoint.")
        maintenance.update_maintenance(
            restore_id,
            state="checkpointing",
            writers_stopped=True,
            summary="Database writers are quiesced while Pocket Lab creates a checkpoint.",
        )
        grace_seconds = max(0.0, min(float(os.environ.get("POCKETLAB_LITE_RESTORE_QUIESCE_SECONDS", "0.25")), 5.0))
        if grace_seconds:
            time.sleep(grace_seconds)
        wal_checkpoint = _truncate_wal_for_restore(live_db)
        checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
        # Writers are blocked and WAL has been truncated, so a durable ordinary
        # file copy preserves the exact active database bytes for rollback.
        _copy_file_durable(live_db, checkpoint_db, mode=live_db.stat().st_mode)
        checkpoint_validation = validate_database_file(checkpoint_db)
        if not checkpoint_validation.get("valid") or not checkpoint_validation.get("schema_current"):
            raise RuntimeError("Pre-restore checkpoint validation failed")
        checkpoint_projection = _database_projection(checkpoint_db)
        state_manifest = _checkpoint_state_files(restore_id)
        space = _ensure_restore_space(source_db, live_db, state_manifest)
        checkpoint_hashes = {
            "database": _sha256(checkpoint_db),
            "state_files_manifest": _sha256(
                restore_txn.restore_transaction_dir(restore_id) / "checkpoint" / "state-files.json"
            ),
        }
        journal = _transition(
            restore_id,
            "checkpoint_ready",
            "Validated pre-restore checkpoint saved.",
            checkpoint_hashes=checkpoint_hashes,
            checkpoint_metadata={
                "database": checkpoint_validation,
                "state_file_count": len(state_manifest.get("files") or []),
                "security_revision": _database_revision(checkpoint_db),
                "space": space,
                "wal_checkpoint": wal_checkpoint,
            },
            checkpoint_projection=checkpoint_projection,
        )
        restore_txn.inject_fault("after_checkpoint")

        _transition(restore_id, "staging", "Copying the selected backup into isolated staging.")
        staged_db.parent.mkdir(parents=True, exist_ok=True)
        _copy_file_durable(source_db, staged_db, mode=source_db.stat().st_mode)
        _remove_sqlite_sidecars(staged_db)
        journal = _transition(
            restore_id,
            "staged",
            "Backup copied to isolated staging.",
            staged_hashes={"database_before_migration": _sha256(staged_db)},
        )
        restore_txn.inject_fault("after_staging")

        _transition(restore_id, "validating_staged", "Validating and migrating the staged database.")
        applied = _apply_migrations_to_database(staged_db)
        staged_validation = validate_database_file(staged_db)
        staged_parity = _compare_projection(expected_projection, staged_db)
        if (
            not staged_validation.get("valid")
            or not staged_validation.get("schema_current")
            or staged_parity.get("matched") is not True
        ):
            raise RuntimeError("Staged restore validation failed")
        journal = _transition(
            restore_id,
            "ready_to_promote",
            "Staged restore is validated and ready to promote.",
            staged_hashes={"database": _sha256(staged_db)},
            staged_validation=staged_validation,
            staged_projection_checksum=_projection_checksum(expected_projection),
            staged_migrations_applied=applied,
        )
        restore_txn.inject_fault("after_staged_validation")

        _transition(restore_id, "promoting", "Promoting the validated database atomically.")
        restore_txn.inject_fault("before_first_promotion")
        active = _promote_database(staged_db, live_db)
        promoted = True
        journal = restore_txn.update_journal(
            restore_id,
            summary="Validated database promoted. Active validation is required before commit.",
            promoted_paths=["pocketlab-lite.sqlite3"],
            pending_paths=["security_state.json", "security/runs/*.json", "security/compact/*.json"],
            active_hashes={"database": active["sha256"]},
        )
        _restore_run_snapshot(journal)
        restore_txn.inject_fault("after_first_promotion")
        restore_txn.inject_fault("after_sqlite_promotion")

        _transition(restore_id, "validating_active", "Validating restored data before commit.")
        restore_txn.inject_fault("before_active_validation")
        active_validation = validate_database_file(live_db)
        restore_txn.inject_fault("during_active_validation")
        active_parity = _compare_projection(expected_projection, live_db)
        if (
            not active_validation.get("valid")
            or not active_validation.get("schema_current")
            or active_parity.get("matched") is not True
            or _sha256(live_db) != str((journal.get("staged_hashes") or {}).get("database") or "")
        ):
            raise RuntimeError("Active restored database validation failed")
        restore_txn.inject_fault("before_commit")
        # The restored canonical state has passed independent active validation.
        # Only now advance the Security revision once, then regenerate derived
        # compatibility projections from the committed candidate.
        revision = _bump_security_revision_once(live_db)
        projection = _refresh_security_projections()
        parity = _parity_check()
        if projection.get("status") != "passed" or parity.get("matched") is not True:
            raise RuntimeError("Restored compatibility projection validation failed")
        _upsert_database_backup_record(manifest)
        completed_at = _utc()
        result_for_audit = {
            "restore_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview_id,
            "state": "completed",
            "started_at": started_at,
            "completed_at": completed_at,
            "summary": "Database recovery completed and validation passed.",
            "sanitized": True,
        }
        _record_restore_result(result_for_audit, manifest)
        final_validation = validate_database_file(live_db)
        journal = restore_txn.update_journal(
            restore_id,
            phase="committed",
            summary="Database recovery completed and validation passed.",
            status="completed",
            terminal_status="committed",
            completed_at=completed_at,
            promoted_paths=["pocketlab-lite.sqlite3", "security_state.json", "security/runs/*.json", "security/compact/*.json"],
            pending_paths=[],
            active_hashes={"database": _sha256(live_db)},
            api_worker_restart_allowed=True,
            final_validation=final_validation,
            canonical_parity=parity,
            security_revision=revision,
            rollback={"status": "available", "attempted": False},
        )
        result = _restore_run_snapshot(
            journal,
            completed_at=completed_at,
            verification=final_validation,
            projection=projection,
            parity=parity,
            rollback_available=True,
            manual_wal_file_deletion=False,
        )
        maintenance.leave_maintenance(
            restore_id,
            state="committed",
            summary="Database recovery completed and validation passed.",
        )
        return result
    except Exception as error:
        current = restore_txn.read_journal(restore_id) or journal
        phase = str(current.get("phase") or "created")
        if promoted or phase in restore_txn.UNSAFE_RECOVERY_PHASES:
            return _rollback_transaction(restore_id, failure=error)
        return _abandon_before_promotion(restore_id, error)
    finally:
        staged_db.unlink(missing_ok=True)
        _remove_sqlite_sidecars(staged_db)


def recover_restore_transaction(restore_id: str) -> dict[str, Any]:
    journal = restore_txn.read_journal(restore_id)
    if not journal:
        raise RuntimeError("Restore transaction journal is unavailable")
    phase = str(journal.get("phase") or "created")
    if phase in {"committed", "rolled_back"}:
        return _restore_run_snapshot(journal)
    maintenance.enter_maintenance(operation_id=restore_id, kind="database_restore")
    if phase in restore_txn.PRE_PROMOTION_PHASES:
        return _abandon_before_promotion(restore_id, RuntimeError("Restore was interrupted before promotion"))
    return _rollback_transaction(restore_id, failure=RuntimeError("Restore was interrupted after promotion"))


def recover_incomplete_restores(*, role: str = "runtime") -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for journal in restore_txn.unresolved_journals():
        restore_id = str(journal.get("restore_id") or "")
        if not restore_id:
            continue
        try:
            with _database_recovery_lock(f"startup-{role}-{restore_id}"):
                result = recover_restore_transaction(restore_id)
        except RuntimeError as exc:
            if "already running" in str(exc).lower():
                continue
            raise
        results.append(restore_txn.public_journal_view(restore_txn.read_journal(restore_id)) or result)
    guard = restore_txn.guard_status()
    return {"role": _safe_name(role), "recovered": results, "guard": guard, "sanitized": True}


def startup_recovery_guard(role: str = "runtime") -> dict[str, Any]:
    recovery = recover_incomplete_restores(role=role)
    guard = recovery["guard"]
    if guard.get("unresolved") and not guard.get("api_worker_restart_allowed"):
        raise RuntimeError("Unresolved database restore requires recovery before writers may start")
    return recovery


def restore_database_backup(command: dict[str, Any]) -> dict[str, Any]:
    operation = str(command.get("command_id") or command.get("restore_id") or "database-restore")
    with _database_recovery_lock(operation):
        return _restore_database_backup_unlocked(command)


def get_database_restore_run(restore_id: str) -> dict[str, Any] | None:
    if not _is_safe_identifier(restore_id):
        return None
    journal = restore_txn.read_journal(restore_id)
    if journal:
        return _restore_run_snapshot(journal, persist=False)
    payload = _read_json(database_restore_run_path(restore_id), None)
    return payload if isinstance(payload, dict) else None


def database_recovery_status() -> dict[str, Any]:
    backups = list_database_backups(limit=25)
    latest_preview = None
    previews = sorted((database_backup_root() / "restore-previews").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if previews:
        latest_preview = _read_json(previews[0], None)
    latest_restore = None
    journals = restore_txn.list_journals(include_terminal=True)
    if journals:
        latest_restore = _restore_run_snapshot(journals[0], persist=False)
    else:
        restores = sorted((database_backup_root() / "restore-runs").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        if restores:
            latest_restore = _read_json(restores[0], None)
    guard = restore_txn.guard_status()
    maintenance_state = maintenance.maintenance_state()
    if guard.get("rollback_failed"):
        status = "needs_attention"
        summary = "Recovery needs attention. Database writers remain blocked."
    elif guard.get("unresolved") or maintenance_state.get("active"):
        status = "maintenance"
        summary = "Database recovery is in progress."
    else:
        status = "healthy" if backups.get("count") else "ready"
        summary = "Database protection is ready." if backups.get("count") else "Create a verified Pocket Lab database backup."
    return {
        "status": status,
        "summary": summary,
        "latest_backup": backups.get("latest_backup"),
        "backup_history": backups.get("backups"),
        "latest_restore_preview": latest_preview,
        "last_restore": latest_restore,
        "active_restore": restore_txn.public_journal_view(journals[0]) if journals and journals[0].get("phase") not in restore_txn.TERMINAL_PHASES else None,
        "restore_guard": guard,
        "maintenance": maintenance_state,
        "wal": maintenance.wal_diagnostics(),
        "rollback_available": bool(latest_restore and latest_restore.get("rollback_available")),
        "updated_at": _utc(),
        "sanitized": True,
    }
