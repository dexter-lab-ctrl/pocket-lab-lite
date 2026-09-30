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



def test_second_device_is_blocked_while_server_phone_backup_is_active(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "status",
        lambda node_id, *_args, **_kwargs: {"ready": True, "latest_backup": None, "node_id": node_id},
    )
    monkeypatch.setattr(
        photo_backup,
        "_agent",
        lambda node_id: {"node_id": node_id, "name": node_id},
    )
    state = photo_backup._state()
    state["jobs"]["photo-active-other"] = {
        "backup_id": "photo-active-other",
        "node_id": "phone-a",
        "status": "transferring",
        "started_at": photo_backup._now(),
    }
    state["latest_by_node"]["phone-a"] = "photo-active-other"
    photo_backup._save_state(state)

    with pytest.raises(Exception) as exc:
        photo_backup.make_start_command("phone-b", ["camera"])

    detail = getattr(exc.value, "detail", {})
    assert detail.get("status") == "photo_backup_busy"
    assert detail.get("retryable") is True


def test_credential_response_uses_stable_per_device_namespace(photo_backup, monkeypatch):
    deleted = []
    monkeypatch.setattr(
        photo_backup,
        "_load_credential",
        lambda _ref: {
            "node_id": "storage-phone",
            "backup_id": "photo-1",
            "username": "admin",
            "password": "short-lived-password",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "expires_at_epoch": photo_backup._epoch() + 60,
        },
    )
    monkeypatch.setattr(photo_backup, "_delete_credential", lambda ref: deleted.append(ref))
    monkeypatch.setattr(
        photo_backup,
        "server_capacity",
        lambda: {"status": "ready", "safe_upload_budget_bytes": 123, "hard_upload_budget_bytes": 456},
    )

    result = photo_backup.consume_credential(
        credential_ref="cred-" + ("a" * 32),
        node_id="storage-phone",
        backup_id="photo-1",
    )

    assert result["destination_prefix"] == "PocketLab/Devices/storage-phone"
    assert deleted == ["cred-" + ("a" * 32)]


def test_terminal_progress_projects_required_and_remaining_bytes(photo_backup, monkeypatch):
    monkeypatch.setattr(photo_backup, "_revoke_job_credential", lambda _job: None)
    monkeypatch.setattr(photo_backup, "_append_evidence", lambda *_args, **_kwargs: None)
    state = photo_backup._state()
    state["jobs"]["photo-1"] = {
        "backup_id": "photo-1",
        "node_id": "storage-phone",
        "status": "transferring",
        "started_at": photo_backup._now(),
    }
    state["latest_by_node"]["storage-phone"] = "photo-1"
    photo_backup._save_state(state)

    result = photo_backup.record_agent_progress(
        "photo-1",
        "storage-phone",
        {
            "status": "partial_storage_limit",
            "items_total": 10,
            "items_transferred": 6,
            "items_remaining": 4,
            "bytes_total": 1000,
            "bytes_total_planned": 700,
            "bytes_total_required": 1000,
            "bytes_transferred": 600,
            "bytes_remaining": 400,
            "partial": True,
            "retryable": True,
            "photo_processing_state": "processing",
            "progress": {"phase": "partial_storage_limit", "percent": 60, "step": "Storage limit reached."},
        },
    )

    assert result["bytes_total_required"] == 1000
    assert result["bytes_total_planned"] == 700
    assert result["bytes_transferred"] == 600
    assert result["bytes_remaining"] == 400
    assert result["photo_processing_state"] == "processing"
    assert result["partial"] is True


def test_capacity_contract_exposes_reserve_policy_without_paths(photo_backup, monkeypatch):
    block = 4096
    total_bytes = 20 * 1024 * 1024 * 1024
    free_bytes = 10 * 1024 * 1024 * 1024
    monkeypatch.setattr(
        os,
        "statvfs",
        lambda _path: SimpleNamespace(
            f_blocks=total_bytes // block,
            f_bavail=free_bytes // block,
            f_frsize=block,
        ),
    )
    result = photo_backup.server_capacity()
    assert result["hard_reserve_fraction"] == 0.10
    assert result["planning_reserve_fraction"] == 0.15
    assert result["planning_reserve_min_bytes"] == 2 * 1024 * 1024 * 1024
    assert "path" not in result
