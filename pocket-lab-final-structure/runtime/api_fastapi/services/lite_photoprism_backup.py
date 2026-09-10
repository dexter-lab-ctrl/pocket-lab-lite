"""Bounded PhotoPrism application-metadata backup and restore support.

PhotoPrism owns the media tree, while Pocket Lab owns the app registration and
the recovery transaction.  This module deliberately handles only the
registered PhotoPrism configuration file's safe settings and the SQLite index
database.  It never walks originals/imports, copies media, or emits a raw
configuration value.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .. import deps
from . import lite_app_runtime, lite_storage_faults

APP_ID = "photoprism"
SUPPORTED_DATABASE_DRIVER = "sqlite"
METADATA_RELATIVE_PATH = "application/photoprism/metadata.sqlite3"
CONFIGURATION_RELATIVE_PATH = "application/photoprism/configuration.json"
CONFIGURATION_KEYS = (
    "PHOTOPRISM_DATABASE_DRIVER",
    "PHOTOPRISM_AUTH_MODE",
    "PHOTOPRISM_HTTP_PORT",
    "PHOTOPRISM_LOG_LEVEL",
)
SAFE_AUTH_MODES = frozenset({"password", "public", "proxy"})
SAFE_LOG_LEVELS = frozenset({"trace", "debug", "info", "warn", "error", "fatal"})
_MAX_CONFIG_BYTES = 512 * 1024
_MAX_DB_BYTES = 8 * 1024 * 1024 * 1024


class PhotoPrismBackupError(RuntimeError):
    """A safe, bounded error from the registered PhotoPrism adapter."""


def _now() -> str:
    return deps.now_utc_iso()


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise PhotoPrismBackupError(f"Registered PhotoPrism {label} is a symlink")
    if not path.is_file():
        raise PhotoPrismBackupError(f"Registered PhotoPrism {label} is missing")
    return path


def _registered_root_and_config() -> tuple[Path, Path]:
    spec = lite_app_runtime.app_runtime_spec(APP_ID)
    if spec is None or not spec.config_paths:
        raise PhotoPrismBackupError("PhotoPrism has no registered application configuration path")
    configured = Path(spec.config_paths[0]).expanduser()
    if configured.is_symlink():
        raise PhotoPrismBackupError("Registered PhotoPrism configuration path is a symlink")
    root_candidate = configured.parent.parent
    if root_candidate.name != APP_ID or root_candidate.is_symlink():
        raise PhotoPrismBackupError("PhotoPrism application root is not the registered root")
    root = root_candidate.resolve(strict=False)
    config = configured.resolve(strict=False)
    try:
        config.relative_to(root)
    except ValueError as exc:
        raise PhotoPrismBackupError("PhotoPrism configuration escapes its registered root") from exc

    # The installer supports an override, but the runtime profile is the
    # registration authority.  Never silently back up a second root.
    override = str(os.environ.get("POCKETLAB_PHOTOPRISM_ROOT") or "").strip()
    if override and Path(override).expanduser().resolve(strict=False) != root:
        raise PhotoPrismBackupError("PhotoPrism root override does not match the registered app root")
    return root, config


def _registered_paths() -> tuple[Path, Path, Path]:
    root, config = _registered_root_and_config()
    storage = root / "storage"
    database = storage / "index.db"
    if storage.is_symlink() or database.is_symlink():
        raise PhotoPrismBackupError("PhotoPrism metadata destination is a symlink")
    resolved_storage = storage.resolve(strict=False)
    resolved_database = database.resolve(strict=False)
    if resolved_storage != root / "storage" or resolved_database != root / "storage" / "index.db":
        raise PhotoPrismBackupError("PhotoPrism metadata destination escapes the registered app root")
    return root, config, database


def _parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        if path.stat().st_size > _MAX_CONFIG_BYTES:
            raise PhotoPrismBackupError("PhotoPrism configuration is too large to inspect safely")
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except PhotoPrismBackupError:
        raise
    except (OSError, UnicodeError) as exc:
        raise PhotoPrismBackupError("PhotoPrism configuration could not be read safely") from exc
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, value = stripped.partition("=")
        if not separator:
            continue
        key = key.strip()
        if key not in CONFIGURATION_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _driver(config: Path, database: Path) -> str | None:
    values = _parse_env(config)
    driver = values.get("PHOTOPRISM_DATABASE_DRIVER", "").strip().casefold()
    if database.exists() and driver != SUPPORTED_DATABASE_DRIVER:
        if driver in {"mysql", "mariadb", "postgres", "postgresql"}:
            raise PhotoPrismBackupError(
                "PhotoPrism metadata uses an unsupported database driver; no logical adapter is registered"
            )
        raise PhotoPrismBackupError(
            "PhotoPrism metadata database driver could not be proven to be the registered SQLite backend"
        )
    return driver or None


def inspect_metadata() -> dict[str, Any]:
    root, config, database = _registered_paths()
    config_present = config.is_file() and not config.is_symlink()
    database_present = database.is_file() and not database.is_symlink()
    if not config_present and not database_present:
        return {
            "status": "not_present",
            "app_id": APP_ID,
            "database_driver": None,
            "configuration_present": False,
            "database_present": False,
            "sanitized": True,
        }
    driver = _driver(config, database) if config_present or database_present else None
    if database_present and database.stat().st_size > _MAX_DB_BYTES:
        raise PhotoPrismBackupError("PhotoPrism metadata database exceeds the bounded backup size")
    return {
        "status": "present",
        "app_id": APP_ID,
        "database_driver": driver,
        "configuration_present": config_present,
        "database_present": database_present,
        "sanitized": True,
    }


def _safe_configuration_payload(config: Path, driver: str | None) -> dict[str, Any]:
    values = _parse_env(config)
    auth_mode = values.get("PHOTOPRISM_AUTH_MODE", "").strip().casefold()
    log_level = values.get("PHOTOPRISM_LOG_LEVEL", "").strip().casefold()
    try:
        port = int(values.get("PHOTOPRISM_HTTP_PORT", ""))
    except (TypeError, ValueError):
        port = 0
    return {
        "format_version": 1,
        "app_id": APP_ID,
        "database_driver": driver or None,
        "authentication_mode": auth_mode if auth_mode in SAFE_AUTH_MODES else None,
        "http_port": port if 1 <= port <= 65535 else None,
        "log_level": log_level if log_level in SAFE_LOG_LEVELS else None,
        "configuration_present": True,
        "registered_paths_preserved": True,
        "media_preserved": True,
        "secret_values_excluded": True,
        "sanitized": True,
    }


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    lite_storage_faults.raise_if_storage_fault("backup_output_write")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_sqlite_metadata(path: Path) -> dict[str, Any]:
    candidate = _safe_file(path, label="metadata database")
    if candidate.stat().st_size > _MAX_DB_BYTES:
        raise PhotoPrismBackupError("PhotoPrism metadata database exceeds the bounded size")
    connection = sqlite3.connect(f"file:{quote(str(candidate), safe='/')}?mode=ro", uri=True, timeout=15)
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        table_count = int(
            connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        )
    except sqlite3.Error as exc:
        raise PhotoPrismBackupError("PhotoPrism metadata SQLite validation failed") from exc
    finally:
        connection.close()
    valid = integrity == "ok" and quick == "ok" and not foreign_keys and table_count > 0
    result = {
        "valid": valid,
        "integrity_check": integrity,
        "quick_check": quick,
        "foreign_keys_clean": not foreign_keys,
        "table_count": table_count,
        "size_bytes": candidate.stat().st_size,
        "sha256": _sha256(candidate),
        "database_driver": SUPPORTED_DATABASE_DRIVER,
        "sanitized": True,
    }
    if not valid:
        raise PhotoPrismBackupError("PhotoPrism metadata SQLite validation failed")
    return result


def _copy_sqlite_online(source: Path, destination: Path) -> dict[str, Any]:
    source = _safe_file(source, label="metadata database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lite_storage_faults.raise_if_storage_fault("backup_output_write")
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex[:8]}.tmp")
    source_connection = sqlite3.connect(
        f"file:{quote(str(source), safe='/')}?mode=ro", uri=True, timeout=15
    )
    try:
        target_connection = sqlite3.connect(str(temporary), timeout=15)
        try:
            source_connection.backup(target_connection, pages=1000, sleep=0.05)
            target_connection.commit()
        finally:
            target_connection.close()
        os.chmod(temporary, 0o600)
        _validate_sqlite_metadata(temporary)
        os.replace(temporary, destination)
    except sqlite3.Error as exc:
        raise PhotoPrismBackupError("PhotoPrism metadata online backup failed") from exc
    finally:
        source_connection.close()
        temporary.unlink(missing_ok=True)
    validation = _validate_sqlite_metadata(destination)
    return {
        "set": "PhotoPrism application metadata",
        "source": "PhotoPrism SQLite metadata database",
        "relative_path": METADATA_RELATIVE_PATH,
        "size_bytes": destination.stat().st_size,
        "sha256": validation["sha256"],
        "kind": "logical_database",
        "component": "photoprism_metadata_database",
        "database_driver": SUPPORTED_DATABASE_DRIVER,
        "validation": validation,
    }


def create_application_backup(staging_root: Path) -> dict[str, Any]:
    """Create bounded PhotoPrism metadata artifacts under restic staging."""
    inspection = inspect_metadata()
    if inspection["status"] == "not_present":
        return {
            "status": "not_present",
            "records": [],
            "components": {
                "photoprism_metadata_database": {"status": "not_present", "required": False},
                "photoprism_safe_configuration": {"status": "not_present", "required": False},
            },
            "summary": "PhotoPrism metadata is not present on this installation.",
        }
    root, config, database = _registered_paths()
    driver = inspection.get("database_driver")
    records: list[dict[str, Any]] = []
    components: dict[str, dict[str, Any]] = {}
    if inspection.get("configuration_present"):
        configuration = staging_root / CONFIGURATION_RELATIVE_PATH
        payload = _safe_configuration_payload(config, driver)
        _write_json_file(configuration, payload)
        records.append(
            {
                "set": "PhotoPrism safe configuration",
                "source": "PhotoPrism safe configuration settings",
                "relative_path": CONFIGURATION_RELATIVE_PATH,
                "size_bytes": configuration.stat().st_size,
                "sha256": _sha256(configuration),
                "kind": "safe_configuration",
                "component": "photoprism_safe_configuration",
                "validation": {"status": "validated", "secret_values_excluded": True, "sanitized": True},
            }
        )
        components["photoprism_safe_configuration"] = {"status": "validated", "required": True}
    else:
        components["photoprism_safe_configuration"] = {"status": "not_present", "required": False}
    if inspection.get("database_present"):
        database_record = _copy_sqlite_online(database, staging_root / METADATA_RELATIVE_PATH)
        records.append(database_record)
        components["photoprism_metadata_database"] = {
            "status": "validated",
            "required": True,
            "database_driver": SUPPORTED_DATABASE_DRIVER,
            "integrity_check": database_record["validation"],
        }
    else:
        components["photoprism_metadata_database"] = {"status": "not_present", "required": False}
    return {
        "status": "validated",
        "records": records,
        "components": components,
        "summary": "PhotoPrism safe configuration and SQLite application metadata validated." if records else "PhotoPrism metadata was not present.",
        "registered_root": True,
    }


def _source_record(source_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    relative = str(record.get("relative_path") or "").lstrip("/")
    if relative not in {METADATA_RELATIVE_PATH, CONFIGURATION_RELATIVE_PATH}:
        raise PhotoPrismBackupError("Selected restore contains an unregistered PhotoPrism destination")
    raw_source = source_root / Path(relative)
    if raw_source.is_symlink():
        raise PhotoPrismBackupError("Selected PhotoPrism restore artifact is a symlink")
    source = raw_source.resolve(strict=False)
    try:
        source.relative_to(source_root.resolve())
    except ValueError as exc:
        raise PhotoPrismBackupError("Selected PhotoPrism restore artifact escapes staging") from exc
    if not source.is_file() or source.is_symlink():
        raise PhotoPrismBackupError("Selected PhotoPrism restore artifact is missing")
    expected = str(record.get("sha256") or "")
    if not expected or _sha256(source) != expected:
        raise PhotoPrismBackupError("Selected PhotoPrism restore artifact checksum does not match")
    root, config, database = _registered_paths()
    kind = "metadata_database" if relative == METADATA_RELATIVE_PATH else "safe_configuration"
    if kind == "metadata_database":
        validation = _validate_sqlite_metadata(source)
        target = database
    else:
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PhotoPrismBackupError("Selected PhotoPrism safe configuration is invalid") from exc
        _configuration_values_from_payload(payload)
        validation = {"status": "validated", "secret_values_excluded": True, "sanitized": True}
        target = config
    if target.is_symlink():
        raise PhotoPrismBackupError("PhotoPrism restore destination is a symlink")
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise PhotoPrismBackupError("PhotoPrism restore destination escapes the registered root") from exc
    return {
        "relative_path": relative,
        "source": source,
        "target": target,
        "sha256": expected,
        "kind": kind,
        "validation": validation,
    }


def validate_staged_application_files(source_root: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    inspection = inspect_metadata()
    if inspection.get("database_driver") not in {None, SUPPORTED_DATABASE_DRIVER}:
        raise PhotoPrismBackupError("Current PhotoPrism database driver is incompatible with the selected restore")
    return [_source_record(source_root, record) for record in records]


def _safe_config_from_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {"exists": False, "values": {}, "sanitized": True}
    values = _parse_env(path)
    safe: dict[str, Any] = {}
    for key in CONFIGURATION_KEYS:
        if key not in values:
            continue
        value = values[key]
        if key == "PHOTOPRISM_DATABASE_DRIVER":
            safe[key] = value.casefold() if value.casefold() == SUPPORTED_DATABASE_DRIVER else None
        elif key == "PHOTOPRISM_AUTH_MODE":
            safe[key] = value.casefold() if value.casefold() in SAFE_AUTH_MODES else None
        elif key == "PHOTOPRISM_LOG_LEVEL":
            safe[key] = value.casefold() if value.casefold() in SAFE_LOG_LEVELS else None
        elif key == "PHOTOPRISM_HTTP_PORT":
            try:
                port = int(value)
            except (TypeError, ValueError):
                port = 0
            safe[key] = port if 1 <= port <= 65535 else None
    return {"exists": True, "values": safe, "sanitized": True}


def _configuration_values_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("app_id") != APP_ID or payload.get("format_version") != 1:
        raise PhotoPrismBackupError("Selected PhotoPrism safe configuration format is unsupported")
    driver = payload.get("database_driver")
    if driver not in {None, SUPPORTED_DATABASE_DRIVER}:
        raise PhotoPrismBackupError("Selected PhotoPrism safe configuration driver is unsupported")
    auth_mode = payload.get("authentication_mode")
    if auth_mode not in ({None} | SAFE_AUTH_MODES):
        raise PhotoPrismBackupError("Selected PhotoPrism authentication mode is unsupported")
    log_level = payload.get("log_level")
    if log_level not in ({None} | SAFE_LOG_LEVELS):
        raise PhotoPrismBackupError("Selected PhotoPrism log level is unsupported")
    port = payload.get("http_port")
    if port is not None and (
        isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535
    ):
        raise PhotoPrismBackupError("Selected PhotoPrism HTTP port is unsupported")
    return {
        "database_driver": driver,
        "authentication_mode": auth_mode,
        "http_port": port,
        "log_level": log_level,
    }


def checkpoint_application_files(restore_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    from . import lite_restore_transaction

    root = lite_restore_transaction.restore_transaction_dir(restore_id) / "checkpoint" / "application-files"
    result: list[dict[str, Any]] = []
    for item in records:
        target = Path(item["target"])
        entry: dict[str, Any] = {
            "relative_path": item["relative_path"],
            "kind": item["kind"],
            "target": "PhotoPrism metadata database" if item["kind"] == "metadata_database" else "PhotoPrism safe configuration",
            "existed": target.is_file() and not target.is_symlink(),
        }
        if item["kind"] == "safe_configuration":
            entry["safe_configuration"] = _safe_config_from_file(target)
        elif entry["existed"]:
            source_stat = target.stat()
            checkpoint = root / "metadata.sqlite3"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, checkpoint)
            os.chmod(checkpoint, stat.S_IMODE(source_stat.st_mode))
            entry.update({"size_bytes": checkpoint.stat().st_size, "sha256": _sha256(checkpoint)})
        result.append(entry)
    manifest = {"files": result, "created_at": _now(), "sanitized": True}
    lite_restore_transaction.atomic_write_json(
        lite_restore_transaction.restore_transaction_dir(restore_id) / "checkpoint" / "application-files.json",
        manifest,
    )
    return manifest


def _write_safe_configuration(path: Path, values: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise PhotoPrismBackupError("PhotoPrism configuration destination is unavailable")
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise PhotoPrismBackupError("PhotoPrism configuration could not be read safely") from exc
    replacements = {
        "PHOTOPRISM_DATABASE_DRIVER": str(values.get("database_driver") or ""),
        "PHOTOPRISM_AUTH_MODE": str(values.get("authentication_mode") or ""),
        "PHOTOPRISM_HTTP_PORT": str(values.get("http_port") or ""),
        "PHOTOPRISM_LOG_LEVEL": str(values.get("log_level") or ""),
    }
    replacements = {key: value for key, value in replacements.items() if value}
    if any("\n" in value or "\r" in value or "=" in value for value in replacements.values()):
        raise PhotoPrismBackupError("PhotoPrism safe configuration contains an invalid value")
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        candidate = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key, separator, _value = candidate.partition("=")
        key = key.strip()
        if separator and key in replacements:
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in replacements.items():
        if key not in seen:
            output.append(f"{key}={value}")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        lite_storage_faults.raise_if_storage_fault("atomic_temp_write")
        temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode) or 0o600)
        lite_storage_faults.raise_if_storage_fault("atomic_replace")
        os.replace(temporary, path)
    except OSError as exc:
        raise PhotoPrismBackupError("PhotoPrism safe configuration restore could not be committed") from exc
    finally:
        temporary.unlink(missing_ok=True)


def restore_staged_application_files(records: list[dict[str, Any]]) -> dict[str, Any]:
    restored: list[dict[str, Any]] = []
    for item in records:
        source = Path(item["source"])
        target = Path(item["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["kind"] == "metadata_database":
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.restore.tmp")
            try:
                shutil.copyfile(source, temporary)
                os.chmod(temporary, stat.S_IMODE(source.stat().st_mode) or 0o600)
                lite_storage_faults.raise_if_storage_fault("atomic_replace")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            validation = _validate_sqlite_metadata(target)
            actual_hash = validation["sha256"]
        else:
            payload = json.loads(source.read_text(encoding="utf-8"))
            _write_safe_configuration(target, _configuration_values_from_payload(payload))
            actual_hash = _sha256(source)
        restored.append(
            {
                "relative_path": item["relative_path"],
                "target": "PhotoPrism metadata database"
                if item["kind"] == "metadata_database"
                else "PhotoPrism safe configuration",
                "size_bytes": target.stat().st_size,
                "sha256": actual_hash,
                "action": "restored",
                "database_driver": SUPPORTED_DATABASE_DRIVER if item["kind"] == "metadata_database" else None,
            }
        )
    return {"restored_files": restored, "restored_file_count": len(restored)}


def _checkpoint_manifest(restore_id: str) -> dict[str, Any]:
    from . import lite_restore_transaction

    path = lite_restore_transaction.restore_transaction_dir(restore_id) / "checkpoint" / "application-files.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PhotoPrismBackupError("PhotoPrism application checkpoint is unavailable") from exc
    if not isinstance(payload, dict):
        raise PhotoPrismBackupError("PhotoPrism application checkpoint is invalid")
    return payload


def restore_checkpoint_application_files(restore_id: str, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    from . import lite_restore_transaction

    payload = manifest if isinstance(manifest, dict) else _checkpoint_manifest(restore_id)
    root, config, database = _registered_paths()
    checkpoint_root = lite_restore_transaction.restore_transaction_dir(restore_id) / "checkpoint" / "application-files"
    restored = 0
    removed = 0
    for item in payload.get("files") or []:
        if not isinstance(item, dict):
            raise PhotoPrismBackupError("PhotoPrism application checkpoint record is invalid")
        relative = str(item.get("relative_path") or "")
        target = database if relative == METADATA_RELATIVE_PATH else config if relative == CONFIGURATION_RELATIVE_PATH else None
        if target is None:
            raise PhotoPrismBackupError("PhotoPrism application checkpoint destination is not registered")
        if target.is_symlink():
            raise PhotoPrismBackupError("PhotoPrism checkpoint destination is a symlink")
        target.resolve(strict=False).relative_to(root)
        if not item.get("existed"):
            if target.exists():
                target.unlink()
                removed += 1
            continue
        if item.get("kind") == "safe_configuration":
            snapshot = item.get("safe_configuration") if isinstance(item.get("safe_configuration"), dict) else {}
            values = snapshot.get("values") if isinstance(snapshot.get("values"), dict) else {}
            if target.is_file():
                _write_safe_configuration(target, _configuration_values_from_payload({
                    "app_id": APP_ID,
                    "format_version": 1,
                    "database_driver": values.get("PHOTOPRISM_DATABASE_DRIVER"),
                    "authentication_mode": values.get("PHOTOPRISM_AUTH_MODE"),
                    "http_port": values.get("PHOTOPRISM_HTTP_PORT"),
                    "log_level": values.get("PHOTOPRISM_LOG_LEVEL"),
                }))
            else:
                raise PhotoPrismBackupError("PhotoPrism configuration checkpoint cannot be restored safely")
        else:
            source = checkpoint_root / "metadata.sqlite3"
            expected = str(item.get("sha256") or "")
            if not source.is_file() or not expected or _sha256(source) != expected:
                raise PhotoPrismBackupError("PhotoPrism metadata checkpoint checksum does not match")
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.rollback.tmp")
            try:
                shutil.copyfile(source, temporary)
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            _validate_sqlite_metadata(target)
        restored += 1
    return {"restored_files": restored, "removed_files": removed, "sanitized": True}


def _pm2_status() -> str:
    spec = lite_app_runtime.app_runtime_spec(APP_ID)
    if spec is None:
        return "unknown"
    pm2 = shutil.which("pm2")
    if not pm2:
        return "unknown"
    try:
        result = subprocess.run([pm2, "jlist"], check=False, capture_output=True, text=True, timeout=5)
        rows = json.loads(result.stdout or "[]") if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return "unknown"
    if not isinstance(rows, list):
        return "unknown"
    for row in rows:
        if not isinstance(row, dict) or row.get("name") != spec.process_name:
            continue
        status = str((row.get("pm2_env") or {}).get("status") or "").casefold()
        if status == "online":
            return "online"
        if status in {"stopped", "errored"}:
            return "stopped"
        return "unknown"
    return "absent"


def _pm2_action(action: str) -> bool:
    spec = lite_app_runtime.app_runtime_spec(APP_ID)
    pm2 = shutil.which("pm2")
    if spec is None or not pm2 or action not in {"stop", "restart"}:
        return False
    try:
        result = subprocess.run(
            [pm2, action, spec.process_name, "--update-env"] if action == "restart" else [pm2, action, spec.process_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def prepare_restore_service() -> dict[str, Any]:
    """Stop only the registered PhotoPrism writer and prove the result."""
    status = _pm2_status()
    if status == "unknown":
        raise PhotoPrismBackupError("PhotoPrism writer state could not be proved before restore")
    if status in {"absent", "stopped"}:
        return {"status": "ready", "was_online": False, "process": "PhotoPrism", "sanitized": True}
    if not _pm2_action("stop"):
        raise PhotoPrismBackupError("PhotoPrism writer could not be stopped safely before restore")
    for _ in range(20):
        if _pm2_status() == "stopped":
            return {"status": "stopped", "was_online": True, "process": "PhotoPrism", "sanitized": True}
        time.sleep(0.25)
    raise PhotoPrismBackupError("PhotoPrism writer did not reach the stopped state")


def restart_after_restore(runtime_state: dict[str, Any] | None) -> dict[str, Any]:
    state = runtime_state if isinstance(runtime_state, dict) else {}
    if not state.get("was_online"):
        return {"status": "not_required", "restarted": False, "sanitized": True}
    if not _pm2_action("restart"):
        raise PhotoPrismBackupError("PhotoPrism could not be restarted after restore")
    for _ in range(20):
        if _pm2_status() == "online":
            return {"status": "restarted", "restarted": True, "sanitized": True}
        time.sleep(0.25)
    raise PhotoPrismBackupError("PhotoPrism did not return to the online state after restore")


def validate_runtime_health() -> dict[str, Any]:
    """Use bounded readiness retries after a service restart.

    PM2 reports an application online before the PhotoPrism HTTP endpoint has
    finished binding.  A single probe at that boundary makes an otherwise
    healthy restore roll back.  Retry only the registered local readiness
    probe, with small bounded limits suitable for Termux; no media is read.
    """
    try:
        attempts = max(
            1,
            min(12, int(os.environ.get("POCKETLAB_LITE_PHOTOPRISM_HEALTH_ATTEMPTS", "6"))),
        )
    except (TypeError, ValueError):
        attempts = 6
    try:
        interval = max(
            0.0,
            min(2.0, float(os.environ.get("POCKETLAB_LITE_PHOTOPRISM_HEALTH_INTERVAL", "0.5"))),
        )
    except (TypeError, ValueError):
        interval = 0.5

    result: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        result = lite_app_runtime.probe_app_runtime(APP_ID, force=True)
        if result.get("reachable") and result.get("running"):
            return {
                "status": "passed",
                "running": True,
                "reachable": True,
                "installation_state": str(result.get("installation_state") or "unknown")[:40],
                "attempt_count": attempt,
                "sanitized": True,
            }
        if attempt < attempts and interval:
            time.sleep(interval)
    return {
        "status": "failed",
        "running": bool(result.get("running")),
        "reachable": bool(result.get("reachable")),
        "installation_state": str(result.get("installation_state") or "unknown")[:40],
        "attempt_count": attempts,
        "sanitized": True,
    }
