from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture(autouse=True)
def isolate_backup_locations(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    database = prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    deps.core.SETTINGS = deps.core.Settings(state_dir=database.parent)
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ROOT", str(tmp_path / "default-backups"))
    external = Path(tempfile.mkdtemp(prefix="pocketlab-backup-location-"))
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ALLOWED_ROOTS", str(external / "storage"))
    (external / "storage").mkdir()
    yield external
    shutil.rmtree(external, ignore_errors=True)


def test_registry_uses_opaque_backend_discovered_locations_and_rejects_media(tmp_path, isolate_backup_locations):
    from api_fastapi.services import lite_backup_locations

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    payload = lite_backup_locations.register_location(custom)
    location = next(item for item in payload["locations"] if item["location_id"] != "default-private")

    assert location["location_id"].startswith("loc-")
    assert str(custom) not in json.dumps(payload)
    assert payload["picker"]["raw_paths_accepted"] is False
    with pytest.raises(lite_backup_locations.BackupLocationError) as error:
        lite_backup_locations.register_location(tmp_path / "storage" / "DCIM")
    assert error.value.reason_code == "media_or_root_not_allowed"

    symlink_target = isolate_backup_locations / "symlink-target"
    symlink_target.mkdir()
    symlink = isolate_backup_locations / "storage" / "Pocket Lab Backups Link"
    symlink.symlink_to(symlink_target, target_is_directory=True)
    with pytest.raises(lite_backup_locations.BackupLocationError) as error:
        lite_backup_locations.register_location(symlink)
    assert error.value.reason_code == "symlink_not_allowed"


def test_registered_location_rejects_later_symlink_replacement(isolate_backup_locations):
    from api_fastapi.services import lite_backup_locations

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    target = isolate_backup_locations / "escaped"
    target.mkdir()
    custom.symlink_to(target, target_is_directory=True)

    with pytest.raises(lite_backup_locations.BackupLocationError, match="symbolic link"):
        lite_backup_locations.layout_for_location(custom_id)
    projection = lite_backup_locations.locations_projection()
    location = next(item for item in projection["locations"] if item["location_id"] == custom_id)
    assert location["available"] is False
    assert location["reason_code"] == "symlink_not_allowed"


def test_history_stays_bound_to_custom_repository_after_switch(tmp_path, isolate_backup_locations):
    from api_fastapi.services import lite_backup_locations, lite_backup_manifest

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    lite_backup_locations.select_location(custom_id)
    custom_layout = lite_backup_locations.layout_for_location(custom_id)
    custom_layout.ensure()
    manifest = lite_backup_manifest.write_manifest(
        {
            "backup_id": "custom-location-1",
            "created_at": "2026-09-10T10:00:00Z",
            "format_version": 2,
            "status": "verified",
            "verification_status": "verified",
            "restorable": True,
            "snapshot_id": "deadbeefcafebabe",
            "included_files": [],
            "repository": {"type": "local", "engine": "restic", "encrypted": True},
            "backup_location": lite_backup_locations.location_metadata(custom_id),
            "location_id": custom_id,
        },
        location_id=custom_id,
        layout=custom_layout,
    )

    lite_backup_locations.select_location("default-private")
    loaded = lite_backup_manifest.read_manifest("custom-location-1")
    history = lite_backup_manifest.list_manifests(limit=10)

    assert loaded is not None
    assert loaded["location_id"] == custom_id
    public = next(item for item in history if item["backup_id"] == "custom-location-1")
    assert public["location_id"] == custom_id
    assert public["location"]["display_name"]
    assert str(custom_layout.repository) not in json.dumps(public)
    assert manifest["manifest_checksum"]


def test_forgotten_location_remains_history_visible_but_restore_unavailable(tmp_path, isolate_backup_locations):
    from api_fastapi.services import lite_backup_locations, lite_backup_manifest

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    layout = lite_backup_locations.layout_for_location(custom_id)
    layout.ensure()
    lite_backup_manifest.write_manifest(
        {
            "backup_id": "forgotten-location-1",
            "created_at": "2026-09-10T10:00:00Z",
            "format_version": 2,
            "status": "verified",
            "verification_status": "verified",
            "restorable": True,
            "snapshot_id": "deadbeefcafebabe",
            "included_files": [],
            "repository": {"type": "local", "engine": "restic", "encrypted": True},
            "backup_location": lite_backup_locations.location_metadata(custom_id),
            "location_id": custom_id,
        },
        location_id=custom_id,
        layout=layout,
    )
    lite_backup_locations.forget_location(custom_id)

    public = next(item for item in lite_backup_manifest.list_manifests(limit=10) if item["backup_id"] == "forgotten-location-1")
    assert public["location_id"] == custom_id
    assert public["location"]["status"] == "unavailable"
    with pytest.raises(Exception, match="unavailable"):
        from api_fastapi.services import lite_backup

        lite_backup._load_verified_manifest("forgotten-location-1")


def test_restore_preview_uses_manifest_location_after_selection_switch(tmp_path, isolate_backup_locations, monkeypatch):
    from api_fastapi.services import lite_backup, lite_backup_locations, lite_backup_manifest

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    layout = lite_backup_locations.layout_for_location(custom_id)
    layout.ensure()
    (layout.repository / "config").write_text("custom-repository-config", encoding="utf-8")
    fingerprint = lite_backup_locations.repository_fingerprint(custom_id, layout)
    lite_backup_manifest.write_manifest(
        {
            "backup_id": "source-routing-1",
            "created_at": "2026-09-10T10:00:00Z",
            "format_version": 2,
            "status": "verified",
            "verification_status": "verified",
            "restorable": True,
            "snapshot_id": "deadbeefcafebabe",
            "included_files": [],
            "repository": {"type": "local", "engine": "restic", "encrypted": True},
            "backup_location": {
                **lite_backup_locations.location_metadata(custom_id),
                "repository_fingerprint": fingerprint,
            },
            "location_id": custom_id,
        },
        location_id=custom_id,
        layout=layout,
    )
    lite_backup_locations.select_location("default-private")
    seen = []

    def fake_run(args, *, env, **kwargs):
        seen.append(env["RESTIC_REPOSITORY"])
        return subprocess.CompletedProcess(args, 0, stdout='{"struct_type":"node"}\n', stderr="")

    monkeypatch.setattr(lite_backup, "_restic_binary", lambda: "restic")
    monkeypatch.setattr(lite_backup, "_run_restic", fake_run)
    preview = lite_backup.create_restore_preview("source-routing-1")

    assert preview["location_id"] == custom_id
    assert seen == [str(layout.repository)]
    assert str(lite_backup_locations.layout_for_location("default-private").repository) not in seen


def test_repository_identity_change_blocks_bound_restore(tmp_path, isolate_backup_locations):
    from api_fastapi.services import lite_backup, lite_backup_locations, lite_backup_manifest

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    layout = lite_backup_locations.layout_for_location(custom_id)
    layout.ensure()
    (layout.repository / "config").write_text("repository-a", encoding="utf-8")
    fingerprint = lite_backup_locations.repository_fingerprint(custom_id, layout)
    lite_backup_manifest.write_manifest(
        {
            "backup_id": "replaced-repository-1",
            "created_at": "2026-09-10T10:00:00Z",
            "format_version": 2,
            "status": "verified",
            "verification_status": "verified",
            "restorable": True,
            "snapshot_id": "deadbeefcafebabe",
            "included_files": [],
            "repository": {"type": "local", "engine": "restic", "encrypted": True},
            "backup_location": {
                **lite_backup_locations.location_metadata(custom_id),
                "repository_fingerprint": fingerprint,
            },
            "location_id": custom_id,
        },
        location_id=custom_id,
        layout=layout,
    )
    (layout.repository / "config").write_text("repository-b", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no longer matches"):
        lite_backup._load_verified_manifest("replaced-repository-1")


def test_selected_location_disappearance_is_unavailable(isolate_backup_locations):
    from api_fastapi.services import lite_backup_locations

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    lite_backup_locations.select_location(custom_id)
    shutil.rmtree(custom)

    projection = lite_backup_locations.locations_projection()
    location = next(item for item in projection["locations"] if item["location_id"] == custom_id)
    assert location["status"] == "missing"
    assert location["available"] is False


def test_location_health_reports_low_space_and_capacity(isolate_backup_locations, monkeypatch):
    from api_fastapi.services import lite_backup_locations

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    actual_disk_usage = lite_backup_locations.shutil.disk_usage
    monkeypatch.setattr(
        lite_backup_locations.shutil,
        "disk_usage",
        lambda path: actual_disk_usage(path)._replace(free=1),
    )
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_MIN_FREE_BYTES", "2")

    projection = lite_backup_locations.locations_projection()
    location = next(item for item in projection["locations"] if item["location_id"] == custom_id)
    assert location["status"] == "low_space"
    assert location["available"] is False
    assert location["free_bytes"] == 1
    assert location["capacity_bytes"] > 1


def test_location_health_reports_read_only(isolate_backup_locations, monkeypatch):
    from api_fastapi.services import lite_backup_locations

    custom = isolate_backup_locations / "storage" / "Pocket Lab Backups"
    registered = lite_backup_locations.register_location(custom)
    custom_id = next(item["location_id"] for item in registered["locations"] if item["location_id"] != "default-private")
    monkeypatch.setattr(lite_backup_locations.os, "access", lambda _path, _mode: False)

    projection = lite_backup_locations.locations_projection()
    location = next(item for item in projection["locations"] if item["location_id"] == custom_id)
    assert location["status"] == "read_only"
    assert location["available"] is False
