from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import subprocess

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    apply_migrations()
    yield state


def _create_photoprism_tree(tmp_path: Path, *, driver: str = "sqlite") -> tuple[Path, Path, Path]:
    root = Path.home() / ".pocket_lab" / "lite" / "apps" / "photoprism"
    config = root / "config" / "photoprism.env"
    database = root / "storage" / "index.db"
    config.parent.mkdir(parents=True, exist_ok=True)
    database.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "\n".join(
            (
                f"PHOTOPRISM_DATABASE_DRIVER={driver}",
                "PHOTOPRISM_AUTH_MODE=password",
                "PHOTOPRISM_HTTP_PORT=2342",
                "PHOTOPRISM_LOG_LEVEL=info",
                "PHOTOPRISM_ADMIN_PASSWORD=current-secret-value",
                "PHOTOPRISM_STORAGE_PATH=/private/media/root",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE photos (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        connection.execute("INSERT INTO photos(id, title) VALUES (1, 'backup-time photo metadata')")
        connection.commit()
    # The adapter must never inspect or copy these payload roots.
    for relative in ("originals/photo.jpg", "imports/video.mp4", "thumbnails/thumb.jpg", "cache/index.tmp"):
        candidate = root / "storage" / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"user-media-payload")
    shared = tmp_path / "storage" / "emulated" / "0" / "DCIM" / "phone.jpg"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_bytes(b"android-media-payload")
    return root, config, database


def test_photoprism_adapter_copies_only_registered_safe_metadata(isolated_runtime, tmp_path):
    from api_fastapi.services import lite_photoprism_backup

    root, _config, database = _create_photoprism_tree(tmp_path)
    staging = tmp_path / "staging"
    result = lite_photoprism_backup.create_application_backup(staging)

    assert result["status"] == "validated"
    assert result["components"]["photoprism_metadata_database"]["status"] == "validated"
    assert result["components"]["photoprism_safe_configuration"]["status"] == "validated"
    paths = {item["relative_path"] for item in result["records"]}
    assert paths == {
        lite_photoprism_backup.METADATA_RELATIVE_PATH,
        lite_photoprism_backup.CONFIGURATION_RELATIVE_PATH,
    }
    assert (staging / lite_photoprism_backup.METADATA_RELATIVE_PATH).is_file()
    configuration = staging / lite_photoprism_backup.CONFIGURATION_RELATIVE_PATH
    configuration_payload = json.loads(configuration.read_text(encoding="utf-8"))
    serialized = json.dumps(result, sort_keys=True) + json.dumps(configuration_payload, sort_keys=True)
    assert "current-secret-value" not in serialized
    assert str(root) not in serialized
    assert "/private/media/root" not in serialized
    with sqlite3.connect(staging / lite_photoprism_backup.METADATA_RELATIVE_PATH) as connection:
        assert connection.execute("SELECT title FROM photos WHERE id=1").fetchone()[0] == "backup-time photo metadata"
    assert (root / "storage" / "originals" / "photo.jpg").read_bytes() == b"user-media-payload"
    assert (tmp_path / "storage" / "emulated" / "0" / "DCIM" / "phone.jpg").read_bytes() == b"android-media-payload"


def test_photoprism_runtime_health_retries_bounded_startup_window(monkeypatch):
    from api_fastapi.services import lite_app_runtime, lite_photoprism_backup

    observations = iter(
        [
            {"running": False, "reachable": False, "installation_state": "installed_degraded"},
            {"running": True, "reachable": True, "installation_state": "installed_running"},
        ]
    )
    monkeypatch.setenv("POCKETLAB_LITE_PHOTOPRISM_HEALTH_ATTEMPTS", "3")
    monkeypatch.setenv("POCKETLAB_LITE_PHOTOPRISM_HEALTH_INTERVAL", "0")
    monkeypatch.setattr(
        lite_app_runtime,
        "probe_app_runtime",
        lambda _app_id, force=False: next(observations),
    )

    result = lite_photoprism_backup.validate_runtime_health()

    assert result["status"] == "passed"
    assert result["attempt_count"] == 2
    assert result["sanitized"] is True


def test_full_backup_manifest_registers_photoprism_metadata_without_secrets(isolated_runtime, tmp_path, monkeypatch):
    _create_photoprism_tree(tmp_path)
    from api_fastapi import deps
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services import lite_backup, lite_backup_manifest

    apply_migrations()

    def fake_restic(args, *, env, timeout=180, cwd=None, capture_stdout=True):
        if "backup" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"snapshot_id": "photoprism-snapshot"}), "")
        if "snapshots" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps([{"id": "photoprism-snapshot"}]), "")
        if "check" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"status": "ok"}), "")
        if "init" in args:
            return subprocess.CompletedProcess(args, 0, "initialized", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(lite_backup, "_restic_binary", lambda: "restic-test")
    monkeypatch.setattr(lite_backup, "_restic_repo_initialized", lambda _layout: True)
    monkeypatch.setattr(lite_backup, "_run_restic", fake_restic)
    deps.core.write_json_file(deps.settings().state_dir / "catalog.json", {"apps": ["photoprism"]})

    result = lite_backup.create_backup(
        {"command_id": "photoprism-full-backup", "include_app_data": True, "reason": "adapter-test"}
    )
    manifest = lite_backup_manifest.read_manifest("photoprism-full-backup")
    assert result["status"] == "succeeded"
    assert manifest is not None
    assert manifest["component_results"]["application_metadata"]["status"] == "validated"
    assert manifest["component_results"]["photoprism_metadata_database"]["status"] == "validated"
    assert "PhotoPrism safe configuration" in manifest["included_sets"]
    assert "PhotoPrism application metadata" in manifest["included_sets"]
    serialized = json.dumps(manifest, sort_keys=True)
    for secret in ("current-secret-value", "admin_password", "/private/media/root", "restic-password"):
        assert secret not in serialized
    assert lite_backup.verify_backup("photoprism-full-backup")["status"] == "verified"


def test_photoprism_mariadb_metadata_fails_closed_without_logical_adapter(isolated_runtime, tmp_path):
    from api_fastapi.services import lite_photoprism_backup

    _create_photoprism_tree(tmp_path, driver="mariadb")
    with pytest.raises(lite_photoprism_backup.PhotoPrismBackupError, match="no logical adapter"):
        lite_photoprism_backup.inspect_metadata()


def test_photoprism_restore_preserves_secret_lines_and_rejects_unregistered_paths(isolated_runtime, tmp_path):
    from api_fastapi.services import lite_photoprism_backup

    _root, config, database = _create_photoprism_tree(tmp_path)
    staging = tmp_path / "staging"
    result = lite_photoprism_backup.create_application_backup(staging)
    records = lite_photoprism_backup.validate_staged_application_files(staging, result["records"])

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE photos SET title='post-backup metadata'")
        connection.commit()
    config.write_text(
        config.read_text(encoding="utf-8").replace("PHOTOPRISM_HTTP_PORT=2342", "PHOTOPRISM_HTTP_PORT=2999"),
        encoding="utf-8",
    )
    restored = lite_photoprism_backup.restore_staged_application_files(records)
    assert restored["restored_file_count"] == 2
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT title FROM photos WHERE id=1").fetchone()[0] == "backup-time photo metadata"
    restored_config = config.read_text(encoding="utf-8")
    assert "PHOTOPRISM_HTTP_PORT=2342" in restored_config
    assert "PHOTOPRISM_ADMIN_PASSWORD=current-secret-value" in restored_config
    assert "PHOTOPRISM_STORAGE_PATH=/private/media/root" in restored_config

    with pytest.raises(lite_photoprism_backup.PhotoPrismBackupError, match="unregistered"):
        lite_photoprism_backup.validate_staged_application_files(
            staging,
            [{"relative_path": "application/photoprism/../../secret", "sha256": "0" * 64}],
        )


def test_selected_full_restore_restores_photoprism_metadata_and_leaves_media_untouched(
    isolated_runtime, tmp_path, monkeypatch
):
    from api_fastapi.services import lite_backup, lite_backup_manifest, lite_database_recovery
    from api_fastapi.services import lite_photoprism_backup

    root, config, database = _create_photoprism_tree(tmp_path)
    saved_snapshot = tmp_path / "saved-snapshot"

    def fake_restic(args, *, env, timeout=180, cwd=None, capture_stdout=True):
        if "backup" in args:
            assert cwd is not None
            saved_snapshot.mkdir(parents=True, exist_ok=True)
            for source in Path(cwd).rglob("*"):
                if source.is_file():
                    destination = saved_snapshot / source.relative_to(cwd)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.read_bytes())
            return subprocess.CompletedProcess(args, 0, json.dumps({"snapshot_id": "full-app-snapshot"}), "")
        if "snapshots" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps([{"id": "full-app-snapshot"}]), "")
        if "check" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"status": "ok"}), "")
        if "ls" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"path": "/", "type": "dir"}) + "\n", "")
        if "restore" in args:
            target = Path(args[args.index("--target") + 1])
            for source in saved_snapshot.rglob("*"):
                if source.is_file():
                    destination = target / source.relative_to(saved_snapshot)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.read_bytes())
            return subprocess.CompletedProcess(args, 0, "restore completed", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(lite_backup, "_restic_binary", lambda: "restic-test")
    monkeypatch.setattr(lite_backup, "_restic_repo_initialized", lambda _layout: True)
    monkeypatch.setattr(lite_backup, "_run_restic", fake_restic)
    monkeypatch.setattr(lite_backup, "_validate_lite_api_health", lambda: {"status": "passed", "http_status": 200})
    monkeypatch.setattr(
        lite_backup,
        "_restore_service_restart_if_needed",
        lambda _files: {"status": "not_required", "needed": False, "services": []},
    )
    monkeypatch.setattr(
        lite_database_recovery,
        "_prepare_application_service_for_restore",
        lambda: {"status": "ready", "was_online": False, "process": "PhotoPrism", "sanitized": True},
    )
    monkeypatch.setattr(
        lite_database_recovery,
        "_restart_application_service_after_restore",
        lambda _state: {"status": "not_required", "restarted": False, "sanitized": True},
    )
    monkeypatch.setattr(
        lite_photoprism_backup,
        "validate_runtime_health",
        lambda: {"status": "passed", "running": True, "reachable": True, "sanitized": True},
    )

    media = root / "storage" / "originals" / "photo.jpg"
    media_before = media.read_bytes()
    lite_backup.create_backup(
        {"command_id": "full-photoprism-restore", "include_app_data": True, "reason": "full-app-test"}
    )
    assert saved_snapshot.is_dir()
    assert lite_backup.verify_backup("full-photoprism-restore")["status"] == "verified"
    manifest = lite_backup_manifest.read_manifest("full-photoprism-restore")
    assert manifest is not None
    preview = lite_backup.create_restore_preview("full-photoprism-restore", reason="full-app-test")

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE photos SET title='changed after backup'")
        connection.commit()
    config.write_text(
        config.read_text(encoding="utf-8").replace("PHOTOPRISM_HTTP_PORT=2342", "PHOTOPRISM_HTTP_PORT=2999"),
        encoding="utf-8",
    )
    media.write_bytes(b"media-changed-after-backup")

    result = lite_backup.apply_restore(
        {
            "command_id": "full-photoprism-restore-run",
            "backup_id": "full-photoprism-restore",
            "preview_id": preview["preview_id"],
            "confirm": True,
            "reason": "full-app-test",
        }
    )
    assert result["status"] == "succeeded", json.dumps(result, indent=2, default=str)
    assert result["application_validation"]["status"] == "passed"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT title FROM photos WHERE id=1").fetchone()[0] == "backup-time photo metadata"
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restored_config = config.read_text(encoding="utf-8")
    assert "PHOTOPRISM_HTTP_PORT=2342" in restored_config
    assert "PHOTOPRISM_ADMIN_PASSWORD=current-secret-value" in restored_config
    assert media.read_bytes() == b"media-changed-after-backup"
    assert media.read_bytes() != media_before
