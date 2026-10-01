#!/usr/bin/env python3
"""Promote one verified database backup into the main runtime state.

This command is intentionally offline and fail-closed.  It consumes a
short-lived receipt issued by the isolated qualification runtime, stages only
the migrations owned by the exact target ``main`` revision, stops only the
known Pocket Lab PM2 processes, keeps a SQLite rollback copy, and performs one
atomic database replacement.  It never edits migration metadata in place and
never applies the feature checkout's newer migrations to the main database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "pocket-lab-final-structure" / "runtime"
MIGRATION_ROOT_RELATIVE = "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
DATABASE_NAME = "pocketlab-lite.sqlite3"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
MIGRATION_FILE = re.compile(r"^(\d+)_([a-z0-9_-]+)\.sql$")
PM2_PROCESS_NAMES = (
    "pocketlab-runtime-reconciler",
    "pocketlab-core-supervisor",
    "pocket-api",
    "pocket-worker",
    "pocket-opa",
    "pocket-nats",
    "pocket-node-agent",
    "pocket-telemetry",
    "caddy-proxy",
)


class RecoveryError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _write_journal(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    clean = {**payload, "sanitized": True, "updated_at": _utc()}
    raw = (json.dumps(clean, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        if os.write(fd, raw) != len(raw):
            raise OSError("recovery journal write was incomplete")
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _read_receipt_token(path: Path) -> str:
    candidate = path.expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise RecoveryError("recovery_receipt_file_missing", "The recovery receipt file is unavailable.") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RecoveryError("recovery_receipt_file_unsafe", "The recovery receipt file must be a private regular file.")
    if metadata.st_size < 32 or metadata.st_size > 512:
        raise RecoveryError("recovery_receipt_file_unsafe", "The recovery receipt file has an invalid size.")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise RecoveryError("recovery_receipt_file_unreadable", "The recovery receipt file could not be read.") from exc
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise RecoveryError("recovery_receipt_invalid", "The recovery receipt is invalid.") from exc
    if not 32 <= len(value) <= 256 or any(char.isspace() for char in value):
        raise RecoveryError("recovery_receipt_invalid", "The recovery receipt is invalid.")
    return value


def _remove_sqlite_sidecars(path: Path) -> list[str]:
    removed: list[str] = []
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        try:
            if sidecar.is_symlink():
                raise RecoveryError("sqlite_sidecar_unsafe", "The live SQLite sidecar is not a regular file.")
            if not sidecar.exists():
                continue
            if not sidecar.is_file():
                raise RecoveryError("sqlite_sidecar_unsafe", "The live SQLite sidecar is not a regular file.")
            sidecar.unlink()
            removed.append(suffix[1:])
        except FileNotFoundError:
            continue
    if removed:
        _fsync_directory(path.parent)
    return removed


def _git_output(*arguments: str, binary: bool = False) -> bytes | str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RecoveryError("target_revision_unavailable", "The target repository revision could not be inspected.") from exc
    if result.returncode != 0:
        raise RecoveryError("target_revision_unavailable", "The target repository revision could not be inspected.")
    return result.stdout if binary else result.stdout.decode("utf-8", errors="strict").strip()


def _resolve_target_main(target_sha: str) -> None:
    values = []
    for ref in ("main", "origin/main"):
        try:
            value = str(_git_output("rev-parse", "--verify", f"{ref}^{{commit}}"))
        except RecoveryError:
            continue
        values.append(value)
    if target_sha not in values:
        raise RecoveryError("target_revision_mismatch", "The receipt target revision is not the checked-out main revision.")


def _target_migrations(target_sha: str, target_schema: int) -> list[dict[str, Any]]:
    raw_paths = str(_git_output("ls-tree", "-r", "--name-only", target_sha, "--", MIGRATION_ROOT_RELATIVE)).splitlines()
    migrations: list[dict[str, Any]] = []
    for raw_path in raw_paths:
        relative = raw_path.strip()
        name = Path(relative).name
        match = MIGRATION_FILE.fullmatch(name)
        if not match:
            continue
        version = int(match.group(1))
        if version > target_schema:
            continue
        source_path = REPO_ROOT / relative
        try:
            current_bytes = source_path.read_bytes()
        except OSError as exc:
            raise RecoveryError("target_migration_contract_invalid", "The target migration contract is unavailable locally.") from exc
        target_bytes = bytes(_git_output("show", f"{target_sha}:{relative}", binary=True))
        current_checksum = hashlib.sha256(current_bytes).hexdigest()
        target_checksum = hashlib.sha256(target_bytes).hexdigest()
        if current_checksum != target_checksum:
            raise RecoveryError("target_migration_drift", "The checked-out runtime migration differs from target main.")
        migrations.append({
            "version": version,
            "name": match.group(2),
            "checksum": target_checksum,
            "sql": target_bytes.decode("utf-8", errors="strict"),
        })
    migrations.sort(key=lambda item: int(item["version"]))
    if not migrations or int(migrations[-1]["version"]) != target_schema:
        raise RecoveryError("target_migration_contract_invalid", "The target main schema does not match the receipt binding.")
    if len({int(item["version"]) for item in migrations}) != len(migrations):
        raise RecoveryError("target_migration_contract_invalid", "The target main migration contract has duplicate versions.")
    return migrations


def _migration_rows(path: Path) -> list[dict[str, Any]]:
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT version,name,applied_at,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    except (OSError, sqlite3.Error) as exc:
        raise RecoveryError("database_metadata_invalid", "The database migration metadata could not be read.") from exc
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass
    return [dict(row) for row in rows]


def _validate_source_migrations(path: Path, target_migrations: list[dict[str, Any]], target_schema: int) -> int:
    rows = _migration_rows(path)
    if not rows:
        raise RecoveryError("database_metadata_invalid", "The verified backup has no migration metadata.")
    contract = {int(item["version"]): item for item in target_migrations}
    versions = [int(row.get("version") or 0) for row in rows]
    source_schema = max(versions, default=0)
    if source_schema > target_schema or any(version not in contract for version in versions):
        raise RecoveryError("backup_newer_than_target", "The verified backup is newer than the target main schema.")
    expected_versions = [version for version in sorted(contract) if version <= source_schema]
    if versions != expected_versions:
        raise RecoveryError("database_metadata_invalid", "The verified backup migration history is not a compatible prefix.")
    for row in rows:
        expected = contract[int(row["version"])]
        if str(row.get("name") or "") != str(expected["name"]) or str(row.get("checksum") or "") != str(expected["checksum"]):
            raise RecoveryError("database_metadata_invalid", "The verified backup migration checksum differs from target main.")
    return source_schema


def _sql_statements(sql: str):
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise RecoveryError("target_migration_contract_invalid", "The target migration SQL is incomplete.")


def _apply_target_migrations(path: Path, target_migrations: list[dict[str, Any]], target_schema: int) -> None:
    contract = {int(item["version"]): item for item in target_migrations}
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall()
        applied = {int(row["version"]): dict(row) for row in rows}
        if any(version not in contract or version > target_schema for version in applied):
            raise RecoveryError("database_metadata_invalid", "The staged database contains a migration newer than target main.")
        for version, row in applied.items():
            expected = contract[version]
            if str(row["name"]) != str(expected["name"]) or str(row["checksum"]) != str(expected["checksum"]):
                raise RecoveryError("database_metadata_invalid", "The staged database migration checksum differs from target main.")
        for migration in target_migrations:
            version = int(migration["version"])
            if version in applied:
                continue
            for statement in _sql_statements(str(migration["sql"])):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES (?,?,?,?)",
                (version, str(migration["name"]), _utc(), str(migration["checksum"])),
            )
        conn.commit()
    except RecoveryError:
        conn.rollback()
        raise
    except (sqlite3.Error, OSError) as exc:
        conn.rollback()
        raise RecoveryError("target_migration_apply_failed", "The target main migrations could not be applied to the staged copy.") from exc
    finally:
        conn.close()
    rows = _migration_rows(path)
    if [int(row.get("version") or 0) for row in rows] != [int(item["version"]) for item in target_migrations]:
        raise RecoveryError("target_migration_apply_failed", "The staged database did not reach the exact target schema.")


def _safe_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RecoveryError(f"{label}_unsafe", f"The {label.replace('_', ' ')} is not a regular file.")


def _copy_and_sync(source: Path, destination: Path) -> None:
    _safe_regular_file(source, label="database")
    shutil.copyfile(source, destination)
    os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
    _fsync_file(destination)


def _create_sqlite_rollback(source: Path, destination: Path) -> None:
    _safe_regular_file(source, label="live database")
    if destination.exists() or destination.is_symlink():
        raise RecoveryError("rollback_artifact_exists", "The recovery rollback artifact already exists.")
    source_conn = sqlite3.connect(str(source))
    destination_conn = sqlite3.connect(str(destination))
    try:
        source_conn.backup(destination_conn)
        integrity = str(destination_conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise RecoveryError("rollback_copy_failed", "The live database rollback copy failed SQLite integrity validation.")
        destination_conn.commit()
    except RecoveryError:
        raise
    except sqlite3.Error as exc:
        raise RecoveryError("rollback_copy_failed", "The live database rollback copy could not be created.") from exc
    finally:
        destination_conn.close()
        source_conn.close()
    os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
    _fsync_file(destination)


def _pm2_processes() -> dict[str, str]:
    pm2 = shutil.which("pm2")
    if not pm2:
        raise RecoveryError("pm2_unavailable", "PM2 is required for the live offline handoff.")
    try:
        result = subprocess.run(
            [pm2, "jlist"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        payload = json.loads(result.stdout.decode("utf-8")) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    if not isinstance(payload, list):
        raise RecoveryError("pm2_inventory_unavailable", "The PM2 runtime inventory could not be read safely.")
    result: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        status = str(env.get("status") or "").casefold()
        if name in PM2_PROCESS_NAMES:
            result[name] = status
    return result


def _stop_pm2(*, skip_pm2: bool) -> list[str]:
    if skip_pm2:
        if os.environ.get("POCKETLAB_OFFLINE_RECOVERY_TEST_MODE") != "1":
            raise RecoveryError("pm2_skip_forbidden", "Skipping PM2 is permitted only in explicit test mode.")
        return []
    pm2 = shutil.which("pm2")
    if not pm2:
        raise RecoveryError("pm2_unavailable", "PM2 is required for the live offline handoff.")
    inventory = _pm2_processes()
    stopped: list[str] = []
    for name in PM2_PROCESS_NAMES:
        if inventory.get(name) not in {"online", "launching", "waiting_restart", "one-launch-status"}:
            continue
        try:
            result = subprocess.run(
                [pm2, "stop", name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RecoveryError("pm2_stop_failed", "A required Pocket Lab PM2 process could not be stopped safely.") from exc
        if result.returncode != 0:
            raise RecoveryError("pm2_stop_failed", "A required Pocket Lab PM2 process could not be stopped safely.")
        stopped.append(name)
    return stopped


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError("backup_manifest_invalid", "The selected backup manifest could not be read.") from exc
    if not isinstance(value, dict):
        raise RecoveryError("backup_manifest_invalid", "The selected backup manifest is invalid.")
    return value


def _configure_runtime(args: argparse.Namespace, qualification_state: Path, backup_root: Path) -> None:
    os.environ.update({
        "POCKETLAB_ENVIRONMENT": "qualification",
        "POCKETLAB_HARNESS_ENABLED": "1",
        "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
        "POCKETLAB_QUALIFICATION_OWNER": "0",
        "POCKETLAB_TEST_AUTH_BYPASS": "0",
        "POCKETLAB_STATE_DIR": str(qualification_state),
        "POCKETLAB_LITE_DB_PATH": str(qualification_state / DATABASE_NAME),
        "POCKETLAB_LITE_BACKUP_ROOT": str(backup_root),
        "POCKETLAB_RECOVERY_TARGET_MAIN_SHA": args.target_main_sha,
        "POCKETLAB_RECOVERY_TARGET_SCHEMA": str(args.target_schema),
    })
    sys.path.insert(0, str(RUNTIME_ROOT))


def _select_latest_compatible_backup(
    recovery: Any,
    *,
    receipt_backup_id: str,
    target_migrations: list[dict[str, Any]],
    target_schema: int,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    catalog = recovery.list_database_backups(limit=100)
    candidates: list[tuple[float, str, dict[str, Any], dict[str, Any]]] = []
    for item in catalog.get("backups") or []:
        if not isinstance(item, dict) or str(item.get("status") or "") != "verified":
            continue
        if str(item.get("verification_status") or "") != "verified":
            continue
        backup_id = str(item.get("backup_id") or "")
        if not SAFE_ID.fullmatch(backup_id):
            continue
        try:
            package = recovery.database_backup_package(backup_id)
            manifest, validation = recovery._verify_database_backup_package(
                package,
                expected_backup_id=backup_id,
                persist_manifest=False,
            )
            source_db = package / str(manifest.get("database_file") or "")
            source_schema = _validate_source_migrations(source_db, target_migrations, target_schema)
        except (RecoveryError, RuntimeError, OSError, sqlite3.Error):
            continue
        if source_schema > target_schema or not validation.get("valid"):
            continue
        candidates.append((_parse_time(manifest.get("created_at")), backup_id, manifest, validation))
    if not candidates:
        raise RecoveryError("compatible_backup_missing", "No verified backup is compatible with target main.")
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _created, selected_id, manifest, validation = candidates[0]
    if selected_id != receipt_backup_id:
        raise RecoveryError("recovery_backup_not_latest", "The recovery receipt is not bound to the latest compatible verified backup.")
    return selected_id, manifest, validation


def run(args: argparse.Namespace) -> dict[str, Any]:
    target_sha = str(args.target_main_sha or "").strip().casefold()
    if not SHA1.fullmatch(target_sha):
        raise RecoveryError("target_revision_invalid", "The target main revision must be a full commit SHA.")
    try:
        target_schema = int(args.target_schema)
    except (TypeError, ValueError) as exc:
        raise RecoveryError("target_schema_invalid", "The target main schema is invalid.") from exc
    if not 1 <= target_schema <= 999:
        raise RecoveryError("target_schema_invalid", "The target main schema is invalid.")

    main_state = Path(args.main_state_dir).expanduser().resolve()
    qualification_state = Path(args.qualification_state_dir).expanduser().resolve()
    backup_root = Path(args.backup_root).expanduser().resolve()
    main_db = main_state / DATABASE_NAME
    qualification_db = qualification_state / DATABASE_NAME
    if main_state == qualification_state or main_db == qualification_db:
        raise RecoveryError("state_isolation_missing", "Main and qualification state must be distinct.")
    _safe_regular_file(qualification_db, label="qualification database")
    _safe_regular_file(main_db, label="live database")
    receipt_path = Path(args.receipt_file).expanduser()
    token = _read_receipt_token(receipt_path)

    _configure_runtime(args, qualification_state, backup_root)
    _resolve_target_main(target_sha)
    target_migrations = _target_migrations(target_sha, target_schema)

    try:
        from api_fastapi.services import lite_database_recovery as recovery
        from api_fastapi.services import lite_harness
    except (ImportError, OSError) as exc:
        raise RecoveryError("qualification_runtime_unavailable", "The qualification recovery runtime could not be loaded.") from exc

    try:
        receipt = lite_harness.inspect_recovery_receipt(token)
    except lite_harness.HarnessError as exc:
        raise RecoveryError(exc.reason_code, exc.message) from exc
    if receipt.get("target_runtime_sha") != target_sha or int(receipt.get("target_schema") or 0) != target_schema:
        raise RecoveryError("recovery_target_mismatch", "The recovery receipt is bound to a different target main runtime.")
    receipt_id = str(receipt.get("receipt_id") or "")
    receipt_backup_id = str(receipt.get("backup_id") or "")
    receipt_preview_id = str(receipt.get("preview_id") or "")
    if not SAFE_ID.fullmatch(receipt_id) or not SAFE_ID.fullmatch(receipt_backup_id) or not SAFE_ID.fullmatch(receipt_preview_id):
        raise RecoveryError("recovery_binding_invalid", "The recovery receipt binding is invalid.")

    preview = recovery.get_database_restore_preview(receipt_preview_id)
    if (
        not isinstance(preview, dict)
        or str(preview.get("backup_id") or "") != receipt_backup_id
        or str(preview.get("status") or "") != "ready"
        or preview.get("restore_allowed") is not True
    ):
        raise RecoveryError("recovery_preview_blocked", "The recovery preview is not ready for offline promotion.")

    selected_id, manifest, source_validation = _select_latest_compatible_backup(
        recovery,
        receipt_backup_id=receipt_backup_id,
        target_migrations=target_migrations,
        target_schema=target_schema,
    )
    source_package = recovery.database_backup_package(selected_id)
    source_db = source_package / str(manifest.get("database_file") or "")
    if int(preview.get("schema_version") or 0) != int(manifest.get("schema_version") or 0):
        raise RecoveryError("recovery_preview_mismatch", "The recovery preview schema does not match the selected backup.")

    promotion_root = main_state / "security" / "recovery" / "offline-promotions" / receipt_id
    if promotion_root.exists() or promotion_root.is_symlink():
        raise RecoveryError("recovery_transaction_exists", "A recovery transaction already exists for this receipt.")
    promotion_root.mkdir(parents=True, mode=0o700)
    candidate_db = promotion_root / "candidate.sqlite3"
    rollback_db = promotion_root / "rollback.sqlite3"
    journal_path = promotion_root / "journal.json"
    journal: dict[str, Any] = {
        "receipt_id": receipt_id,
        "backup_id": selected_id,
        "preview_id": receipt_preview_id,
        "target_runtime_sha": target_sha,
        "target_schema": target_schema,
        "phase": "preflight",
        "main_database": str(main_db),
        "qualification_state": str(qualification_state),
        "source_schema": int(manifest.get("schema_version") or 0),
        "source_database_sha256": str(source_validation.get("sha256") or ""),
    }
    _write_journal(journal_path, journal)
    stopped: list[str] = []
    try:
        _copy_and_sync(source_db, candidate_db)
        _apply_target_migrations(candidate_db, target_migrations, target_schema)
        staged_validation = recovery.validate_database_file(candidate_db)
        if not staged_validation.get("valid") or int(staged_validation.get("schema_version") or 0) != target_schema:
            raise RecoveryError("staged_database_invalid", "The target-schema staged database failed SQLite validation.")
        canonical_file = source_package / str(manifest.get("canonical_projection_file") or "")
        projection_payload = _load_json(canonical_file)
        expected_projection = projection_payload.get("projection")
        if not isinstance(expected_projection, dict):
            raise RecoveryError("canonical_projection_missing", "The verified backup canonical projection is unavailable.")
        parity = recovery._compare_projection(expected_projection, candidate_db)
        if parity.get("matched") is not True:
            raise RecoveryError("canonical_projection_mismatch", "The staged target-schema database differs from the verified canonical projection.")
        candidate_sha = _sha256(candidate_db)
        journal.update({
            "phase": "preflight_ready",
            "candidate_sha256": candidate_sha,
            "candidate_size_bytes": candidate_db.stat().st_size,
            "staged_validation": {
                "schema_version": staged_validation.get("schema_version"),
                "integrity_check": staged_validation.get("integrity_check"),
                "quick_check": staged_validation.get("quick_check"),
                "foreign_keys_clean": staged_validation.get("foreign_keys_clean"),
            },
            "canonical_parity": {"matched": True, "mismatch_fields": []},
        })
        _write_journal(journal_path, journal)

        stopped = _stop_pm2(skip_pm2=bool(args.skip_pm2))
        _create_sqlite_rollback(main_db, rollback_db)
        rollback_sha = _sha256(rollback_db)
        journal.update({"phase": "writers_stopped", "pm2_stopped": stopped, "rollback_sha256": rollback_sha})
        _write_journal(journal_path, journal)

        try:
            consumed = lite_harness.consume_recovery_receipt(
                token,
                expected_target_sha=target_sha,
                expected_target_schema=target_schema,
                expected_backup_id=selected_id,
                expected_preview_id=receipt_preview_id,
            )
        except lite_harness.HarnessError as exc:
            raise RecoveryError(exc.reason_code, exc.message) from exc
        journal.update({"phase": "receipt_consumed", "receipt_status": consumed.get("status")})
        _write_journal(journal_path, journal)

        if args.inject_failure == "before-promotion":
            raise RecoveryError("injected_failure", "The requested pre-promotion test fault was injected.")

        # The candidate was fully validated before this point.  After this
        # atomic handoff do not reopen it or run migrations against the main
        # database; the next main-runtime startup owns readiness validation.
        sidecars = _remove_sqlite_sidecars(main_db)
        os.replace(candidate_db, main_db)
        _fsync_file(main_db)
        _fsync_directory(main_db.parent)
        if _sha256(main_db) != candidate_sha:
            journal.update({"phase": "promotion_uncertain", "sidecars_removed": sidecars})
            _write_journal(journal_path, journal)
            raise RecoveryError("promotion_checksum_mismatch", "The promoted database checksum did not match its staged copy.")
        journal.update({"phase": "promoted", "sidecars_removed": sidecars, "next_action": "Switch to target main and start the validated runtime."})
        _write_journal(journal_path, journal)
        try:
            receipt_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # The secret file is not part of the database transaction. Keep
            # the promotion successful but report that cleanup is required.
            journal["receipt_file_cleanup"] = "deferred"
            _write_journal(journal_path, journal)
        return {
            "status": "promoted",
            "receipt_id": receipt_id,
            "backup_id": selected_id,
            "preview_id": receipt_preview_id,
            "target_runtime_sha": target_sha,
            "target_schema": target_schema,
            "source_schema": int(manifest.get("schema_version") or 0),
            "candidate_sha256": candidate_sha,
            "rollback_sha256": rollback_sha,
            "pm2_stopped": stopped,
            "journal": str(journal_path),
            "rollback_database": str(rollback_db),
            "sanitized": True,
        }
    except RecoveryError as exc:
        journal.update({"phase": "failed_before_promotion" if candidate_db.exists() else "promotion_uncertain", "failure_reason_code": exc.reason_code})
        try:
            _write_journal(journal_path, journal)
        except OSError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote one receipt-bound verified backup to main SQLite state")
    parser.add_argument("--receipt-file", required=True)
    parser.add_argument("--main-state-dir", required=True)
    parser.add_argument("--qualification-state-dir", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--target-main-sha", required=True)
    parser.add_argument("--target-schema", required=True, type=int)
    parser.add_argument("--skip-pm2", action="store_true")
    parser.add_argument("--inject-failure", choices=("before-promotion",))
    parser.set_defaults(handler=run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = args.handler(args)
    except RecoveryError as exc:
        print(f"ERROR {exc.reason_code}: {exc.message}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"ERROR offline_recovery_failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
