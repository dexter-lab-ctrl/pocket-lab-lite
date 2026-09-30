from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture()
def photo_backup(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_photo_backup

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setattr(lite_photo_backup, "_originals_path", lambda: tmp_path / "originals")
    return lite_photo_backup


def test_server_capacity_enforces_hard_and_planning_reserves(photo_backup, monkeypatch):
    block = 4096
    total_bytes = 100 * 1024 * 1024 * 1024
    free_bytes = 50 * 1024 * 1024 * 1024
    stat = SimpleNamespace(
        f_blocks=total_bytes // block,
        f_bavail=free_bytes // block,
        f_frsize=block,
    )
    monkeypatch.setattr(os, "statvfs", lambda _path: stat)

    capacity = photo_backup.server_capacity()

    assert capacity["hard_reserve_bytes"] == int(total_bytes * 0.10)
    assert capacity["planning_reserve_bytes"] == int(total_bytes * 0.15)
    assert capacity["safe_upload_budget_bytes"] == free_bytes - int(total_bytes * 0.15)
    assert capacity["hard_upload_budget_bytes"] == free_bytes - int(total_bytes * 0.10)
    assert capacity["sanitized"] is True


def test_collections_reject_arbitrary_paths_and_urls(photo_backup):
    assert photo_backup._collections(["camera", "pictures"]) == ["camera", "pictures"]
    with pytest.raises(Exception):
        photo_backup._collections(["/storage/emulated/0"])
    with pytest.raises(Exception):
        photo_backup._collections(["https://example.invalid/photos"])


def test_public_job_never_projects_credentials_or_paths(photo_backup):
    public = photo_backup._public_job(
        {
            "backup_id": "photo-1",
            "node_id": "storage-phone",
            "status": "completed",
            "summary": "Photos are backed up.",
            "credential_ref_internal": "cred-secret-ref",
            "auth_id_internal": "auth-secret",
            "password": "raw-password",
            "webdav_url": "https://private.example/originals/",
            "source_path": "/storage/emulated/0/DCIM",
            "items_transferred": 2,
            "bytes_transferred": 1234,
        }
    )
    dumped = json.dumps(public)
    assert "raw-password" not in dumped
    assert "cred-secret-ref" not in dumped
    assert "auth-secret" not in dumped
    assert "/storage/emulated" not in dumped
    assert "private.example" not in dumped
    assert public["items_transferred"] == 2


def test_repeated_start_returns_existing_active_backup(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "status",
        lambda *_args, **_kwargs: {
            "ready": True,
            "latest_backup": {
                "backup_id": "photo-existing",
                "node_id": "storage-phone",
                "status": "transferring",
                "collections": ["camera"],
            },
        },
    )

    command = photo_backup.make_start_command("storage-phone", ["camera"])

    assert command["idempotent"] is True
    assert command["backup_id"] == "photo-existing"


def test_worker_start_sends_only_opaque_credential_reference_to_node(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "status",
        lambda *_args, **_kwargs: {"ready": True, "latest_backup": None},
    )
    monkeypatch.setattr(
        photo_backup,
        "_agent",
        lambda node_id: {"node_id": node_id, "name": "Storage Phone"},
    )
    command = photo_backup.make_start_command("storage-phone", ["camera", "pictures"])

    monkeypatch.setattr(photo_backup, "_secure_origin", lambda _request=None: "https://pocket.test.ts.net")
    monkeypatch.setattr(
        photo_backup.lite_app_runtime,
        "probe_app_runtime",
        lambda *_args, **_kwargs: {"running": True, "reachable": True},
    )
    monkeypatch.setattr(
        photo_backup,
        "server_capacity",
        lambda: {
            "status": "ready",
            "hard_upload_budget_bytes": 10_000_000,
            "safe_upload_budget_bytes": 8_000_000,
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        photo_backup,
        "_create_app_password",
        lambda *_args: ("raw-app-password", "PocketLab-test", "authidentifier"),
    )
    monkeypatch.setattr(photo_backup, "_probe_webdav", lambda *_args: True)

    stored = {}

    def fake_store(**kwargs):
        stored.update(kwargs)

    monkeypatch.setattr(photo_backup, "_store_credential", fake_store)
    published = {}

    async def fake_publish(node_id, node_command, payload, **_kwargs):
        published.update({"node_id": node_id, "command": node_command, "payload": payload})
        return {"command_id": "node-command-1"}

    monkeypatch.setattr(photo_backup, "_publish_node_command", fake_publish)

    result = asyncio.run(photo_backup.execute_start(command))

    assert result["status"] == "starting"
    assert stored["password"] == "raw-app-password"
    encoded = json.dumps(published)
    assert published["command"] == "media.backup.photoprism.start"
    assert "credential_ref" in published["payload"]
    assert "raw-app-password" not in encoded
    assert "webdav_url" not in published["payload"]
    assert "/storage/" not in encoded


def test_device_removal_revoke_preserves_backup_contract(photo_backup, monkeypatch):
    monkeypatch.setattr(photo_backup, "_revoke_job_credential", lambda _job: None)
    payload = photo_backup._state()
    payload["jobs"]["photo-active"] = {
        "backup_id": "photo-active",
        "node_id": "storage-phone",
        "status": "transferring",
        "summary": "Backing up photos.",
        "started_at": photo_backup._now(),
    }
    payload["latest_by_node"]["storage-phone"] = "photo-active"
    photo_backup._save_state(payload)

    assert photo_backup.revoke_for_node("storage-phone") == 1
    saved = photo_backup._state()["jobs"]["photo-active"]
    assert saved["status"] == "cancelled"
    assert "preserved" in saved["summary"].lower()


def test_live_phone_import_guard_is_fail_closed(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    monkeypatch.setattr(
        lite_photoprism_media.lite_app_storage,
        "runtime_mappings",
        lambda _app_id: [
            {
                "mapping_id": "phone-media",
                "target": "import",
                "source_type": "phone_media",
                "source_path": "~/storage/shared/DCIM",
            }
        ],
    )
    assert lite_photoprism_media.live_phone_import_blocked() is True

    with pytest.raises(Exception) as exc:
        lite_photoprism_media.media_command("import_photos")
    assert "unsafe_live_media_import" in str(exc.value)
