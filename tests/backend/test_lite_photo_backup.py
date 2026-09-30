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
    originals = tmp_path / "originals"
    originals.mkdir()
    monkeypatch.setattr(lite_photo_backup, "_originals_path", lambda: originals)
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
    monkeypatch.setattr(photo_backup, "_revoke_job_credential", lambda _job: True)
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



def test_ephemeral_credential_file_is_encrypted_at_rest(photo_backup, monkeypatch):
    monkeypatch.setattr(photo_backup, "_epoch", lambda: 1000.0)
    ref = "cred-" + ("b" * 32)
    photo_backup._store_credential(
        credential_ref=ref,
        backup_id="photo-encrypted",
        node_id="storage-phone",
        password="raw-short-lived-password",
        auth_name="PocketLab-test",
        auth_id="authidentifier",
        webdav_url="https://pocket.test.ts.net/apps/photoprism/originals/",
    )

    path = photo_backup._credential_path(ref)
    raw = path.read_bytes()
    assert path.suffix == ".bin"
    assert b"raw-short-lived-password" not in raw
    assert b"pocket.test.ts.net" not in raw
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(photo_backup._credential_key_path().stat().st_mode & 0o777) == "0o600"

    loaded = photo_backup._load_credential(ref)
    assert loaded["password"] == "raw-short-lived-password"
    assert loaded["backup_id"] == "photo-encrypted"


def test_corrupt_encrypted_credential_fails_closed_and_is_removed(photo_backup):
    ref = "cred-" + ("c" * 32)
    path = photo_backup._credential_path(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-fernet-token")
    path.chmod(0o600)

    assert photo_backup._load_credential(ref) is None
    assert not path.exists()


def test_webdav_probe_requires_options_and_propfind(photo_backup, monkeypatch):
    calls = []

    class Response:
        def __init__(self, status):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        calls.append((request.get_method(), timeout))
        return Response(200 if request.get_method() == "OPTIONS" else 207)

    monkeypatch.setattr(photo_backup.urllib.request, "urlopen", fake_urlopen)
    assert photo_backup._probe_webdav(
        "https://pocket.test.ts.net/apps/photoprism/originals/",
        "admin",
        "short-lived-password",
    ) is True
    assert [method for method, _ in calls] == ["OPTIONS", "PROPFIND"]


def test_webdav_probe_rejects_insecure_origin_without_network_call(photo_backup, monkeypatch):
    called = []
    monkeypatch.setattr(photo_backup.urllib.request, "urlopen", lambda *_args, **_kwargs: called.append(True))
    assert photo_backup._probe_webdav(
        "http://192.0.2.1/apps/photoprism/originals/",
        "admin",
        "password",
    ) is False
    assert called == []



def test_photo_backup_api_status_and_internal_endpoints_are_semantic_only(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import fleet
    from pocket_lab_test_utils import client as make_client

    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "fleet_status",
        lambda _request=None: {
            "status": "ok",
            "provider": "photoprism_webdav",
            "devices": [],
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "status",
        lambda node_id, _request=None: {
            "status": "ready",
            "ready": True,
            "node_id": node_id,
            "provider": "photoprism_webdav",
            "sanitized": True,
        },
    )

    api = make_client()
    fleet_response = api.get("/api/lite/media-backup")
    device_response = api.get("/api/lite/devices/storage-phone/photo-backup")

    assert fleet_response.status_code == 200
    assert fleet_response.json()["provider"] == "photoprism_webdav"
    assert device_response.status_code == 200
    assert device_response.json()["node_id"] == "storage-phone"

    openapi = api.get("/openapi.json").json()
    paths = openapi.get("paths", {})
    assert "/api/lite/media-backup" in paths
    assert "/api/lite/devices/{node_id}/photo-backup" in paths
    assert not any("/internal/photo-backup/" in path for path in paths)


def test_photo_backup_api_repeated_start_is_idempotent(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import fleet
    from pocket_lab_test_utils import client as make_client

    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "make_start_command",
        lambda *_args, **_kwargs: {
            "idempotent": True,
            "backup_id": "photo-existing",
            "node_id": "storage-phone",
            "collections": ["camera"],
        },
    )

    response = make_client().post(
        "/api/lite/devices/storage-phone/photo-backup",
        json={"collections": ["camera"]},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "already_running"
    assert payload["backup_id"] == "photo-existing"
    assert payload["sanitized"] is True


def test_photo_backup_api_start_queues_only_domain_command(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import fleet
    from pocket_lab_test_utils import client as make_client

    command = {
        "command_id": "photo-queued",
        "backup_id": "photo-queued",
        "node_id": "storage-phone",
        "collections": ["camera", "pictures"],
        "provider": "photoprism_webdav",
    }
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "make_start_command",
        lambda *_args, **_kwargs: command,
    )
    captured = {}

    async def fake_submit(subject, event_type, payload, **kwargs):
        captured.update(
            subject=subject,
            event_type=event_type,
            payload=payload,
            trace_id=kwargs.get("trace_id"),
        )
        return {"status": "queued"}

    monkeypatch.setattr(fleet, "submit_domain_command", fake_submit)

    response = make_client().post(
        "/api/lite/devices/storage-phone/photo-backup",
        json={"collections": ["camera", "pictures"]},
    )

    assert response.status_code == 202
    assert response.json()["backup_id"] == "photo-queued"
    assert captured["subject"] == fleet.lite_photo_backup.PHOTO_BACKUP_START_SUBJECT
    assert captured["event_type"] == "lite.photo_backup.requested"
    encoded = json.dumps(captured)
    assert "password" not in encoded.lower()
    assert "webdav_url" not in encoded.lower()
    assert "rclone" not in encoded.lower()


def test_photo_backup_api_cancel_idle_and_active_are_truthful(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import fleet
    from pocket_lab_test_utils import client as make_client

    api = make_client()
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "make_cancel_command",
        lambda *_args, **_kwargs: {
            "command_id": "cancel-idle",
            "backup_id": "",
            "node_id": "storage-phone",
            "idle": True,
        },
    )
    idle = api.post("/api/lite/devices/storage-phone/photo-backup/cancel", json={})
    assert idle.status_code == 202
    assert idle.json()["status"] == "idle"

    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "make_cancel_command",
        lambda *_args, **_kwargs: {
            "command_id": "cancel-active",
            "backup_id": "photo-active",
            "node_id": "storage-phone",
            "idle": False,
        },
    )

    async def fake_submit(*_args, **_kwargs):
        return {"status": "queued"}

    monkeypatch.setattr(fleet, "submit_domain_command", fake_submit)
    active = api.post("/api/lite/devices/storage-phone/photo-backup/cancel", json={})
    assert active.status_code == 202
    assert active.json()["backup_id"] == "photo-active"
    assert active.json()["summary"] == "Stopping photo backup safely."


def test_internal_credential_endpoint_is_no_store_and_node_authenticated(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import fleet
    from pocket_lab_test_utils import client as make_client

    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "authenticate_agent",
        lambda node_id, token: {"node_id": node_id, "token_seen": bool(token)},
    )
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "consume_credential",
        lambda **kwargs: {
            "backup_id": kwargs["backup_id"],
            "node_id": kwargs["node_id"],
            "username": "admin",
            "password": "one-time-secret",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )

    response = make_client().get(
        "/api/lite/internal/photo-backup/credentials/" + "cred-" + ("d" * 32),
        params={"backup_id": "photo-internal"},
        headers={
            "X-PocketLab-Node-Id": "storage-phone",
            "X-PocketLab-Agent-Token": "agent-token",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"
    payload = response.json()
    assert payload["destination_prefix"] == "PocketLab/Devices/storage-phone"
    assert payload["password"] == "one-time-secret"



def test_photoprism_session_id_parser_prefers_json_contract(photo_backup):
    output = json.dumps([
        {
            "session_id": "refsession123456",
            "user": "admin",
            "authentication_method": "app password",
            "client": "PocketLab-storage-phone-abcd1234",
            "scope": "webdav",
        }
    ])
    assert photo_backup._parse_auth_id(
        output,
        "PocketLab-storage-phone-abcd1234",
    ) == "refsession123456"


def test_photoprism_app_password_parser_handles_terminal_formatted_table(photo_backup):
    output = (
        "\x1b[32m│ App Password                │ Authorization Scope │\x1b[0m\n"
        "│ HY8fxO-8hvNqB-43UV4q-1AZ0vu │ webdav              │\n"
    )
    assert photo_backup._parse_app_password(output) == (
        "HY8fxO-8hvNqB-43UV4q-1AZ0vu"
    )


def test_photoprism_session_id_parser_never_uses_client_name_as_identifier(photo_backup):
    output = (
        "| Session ID | User | Authentication Method | Client | Scope |\n"
        "| refsession123456 | admin | app password | PocketLab-storage-phone-abcd1234 | webdav |"
    )
    assert photo_backup._parse_auth_id(
        output,
        "PocketLab-storage-phone-abcd1234",
    ) == "refsession123456"
    assert photo_backup._parse_auth_id(
        "| PocketLab-storage-phone-abcd1234 | admin | webdav |",
        "PocketLab-storage-phone-abcd1234",
    ) == ""


def test_photoprism_revoke_is_noninteractive_and_uses_only_session_id(photo_backup, monkeypatch):
    calls = []

    def fake_command(args, timeout, input_text=None):
        calls.append((args, timeout, input_text))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(photo_backup, "_photoprism_command", fake_command)
    assert photo_backup._revoke_auth_id("refsession123456") is True
    assert calls == [
        (
            ["auth", "rm", "refsession123456"],
            photo_backup.PHOTOPRISM_COMMAND_TIMEOUT_SECONDS,
            "y\n",
        )
    ]


def test_app_password_creation_requires_revocable_session_id(photo_backup, monkeypatch):
    responses = iter([
        SimpleNamespace(returncode=0, stdout="webdav", stderr=""),
        SimpleNamespace(
            returncode=0,
            stdout=(
                "| App Password | Authorization Scope |\n"
                "| abcdefghijklmnop-qrstuvwx | webdav |\n"
            ),
            stderr="",
        ),
    ])
    monkeypatch.setattr(
        photo_backup,
        "_photoprism_command",
        lambda *_args, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        photo_backup,
        "_find_auth_id",
        lambda _name: "",
    )
    with pytest.raises(RuntimeError) as exc:
        photo_backup._create_app_password("storage-phone", "photo-abcdef12")
    assert str(exc.value) == "webdav_credential_parse_failed"


def test_photo_backup_workload_is_explicitly_worker_owned():
    ensure_runtime_path()
    from api_fastapi.services import workload_admission

    definition = workload_admission.WORKLOADS["photo_backup.execute"]
    assert definition.execution_owner.value == "worker_owned"
    assert definition.cost_class.value == "heavy"
    assert definition.audit_evidence_required is True



def test_capacity_read_does_not_create_missing_photoprism_state(photo_backup, tmp_path, monkeypatch):
    missing = tmp_path / "missing-originals"
    monkeypatch.setattr(photo_backup, "_originals_path", lambda: missing)
    result = photo_backup.server_capacity()
    assert result["status"] == "unavailable"
    assert not missing.exists()


def test_worker_redelivery_does_not_rotate_credential_or_republish_node_start(photo_backup, monkeypatch):
    state = photo_backup._state()
    state["jobs"]["photo-redelivery"] = {
        "backup_id": "photo-redelivery",
        "node_id": "storage-phone",
        "status": "starting",
        "summary": "Starting protected photo backup on the device.",
        "credential_ref_internal": "cred-" + ("e" * 32),
        "auth_id_internal": "session-redelivery",
        "started_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-redelivery"
    photo_backup._save_state(state)

    monkeypatch.setattr(
        photo_backup,
        "_create_app_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("redelivery must not create another credential")
        ),
    )

    async def should_not_publish(*_args, **_kwargs):
        raise AssertionError("redelivery must not republish node start")

    monkeypatch.setattr(photo_backup, "_publish_node_command", should_not_publish)
    result = asyncio.run(photo_backup.execute_start({
        "command_id": "photo-redelivery",
        "backup_id": "photo-redelivery",
        "node_id": "storage-phone",
        "collections": ["camera"],
    }))
    assert result["status"] == "starting"
    assert result["backup_id"] == "photo-redelivery"


def test_terminal_agent_progress_cannot_regress_completed_job(photo_backup):
    state = photo_backup._state()
    state["jobs"]["photo-done"] = {
        "backup_id": "photo-done",
        "node_id": "storage-phone",
        "status": "completed",
        "summary": "Photos are backed up.",
        "completed_at": photo_backup._now(),
        "started_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-done"
    photo_backup._save_state(state)
    result = photo_backup.record_agent_progress(
        "photo-done",
        "storage-phone",
        {"status": "interrupted", "summary": "late stale report"},
    )
    assert result["status"] == "completed"
    assert result["summary"] == "Photos are backed up."


def test_auth_lookup_falls_back_when_json_listing_is_not_supported(photo_backup, monkeypatch):
    calls = []
    responses = iter([
        SimpleNamespace(returncode=2, stdout="", stderr="unknown flag"),
        SimpleNamespace(
            returncode=0,
            stdout="| refsession123456 | admin | app password | PocketLab-test | webdav |",
            stderr="",
        ),
    ])
    def fake_command(args, timeout):
        calls.append(args)
        return next(responses)
    monkeypatch.setattr(photo_backup, "_photoprism_command", fake_command)
    assert photo_backup._find_auth_id("PocketLab-test") == "refsession123456"
    assert calls == [
        ["auth", "ls", "--json", "PocketLab-test"],
        ["auth", "ls", "PocketLab-test"],
    ]


def test_public_job_projects_aggregate_conflicts_without_file_names(photo_backup):
    result = photo_backup._public_job({
        "backup_id": "photo-conflict",
        "node_id": "storage-phone",
        "status": "completed",
        "conflicts": 3,
        "conflict_name_internal": "private.jpg",
    })
    assert result["conflicts"] == 3
    assert "conflict_name_internal" not in result
    assert "private.jpg" not in json.dumps(result)



def test_start_submission_failure_releases_job_for_retry(photo_backup):
    state = photo_backup._state()
    state["jobs"]["photo-submit-failed"] = {
        "backup_id": "photo-submit-failed",
        "node_id": "storage-phone",
        "status": "queued",
        "summary": "Photo backup request queued.",
        "started_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-submit-failed"
    photo_backup._save_state(state)
    result = photo_backup.mark_submission_failed(
        "photo-submit-failed"
    )
    assert result["status"] == "failed"
    assert result["retryable"] is True
    assert result["reason_code"] == "command_submission_failed"


def test_progress_contract_preserves_conflicts_required_and_remaining_bytes(photo_backup, monkeypatch):
    monkeypatch.setattr(photo_backup, "_revoke_job_credential", lambda _job: None)
    state = photo_backup._state()
    state["jobs"]["photo-progress-aggregate"] = {
        "backup_id": "photo-progress-aggregate",
        "node_id": "storage-phone",
        "status": "transferring",
        "started_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-progress-aggregate"
    photo_backup._save_state(state)
    result = photo_backup.record_agent_progress(
        "photo-progress-aggregate",
        "storage-phone",
        {
            "status": "completed",
            "conflicts": 2,
            "bytes_total_required": 5000,
            "bytes_total_planned": 5000,
            "bytes_transferred": 5000,
            "bytes_remaining": 0,
            "photo_processing_state": "processing",
        },
    )
    assert result["conflicts"] == 2
    assert result["bytes_total_required"] == 5000
    assert result["bytes_transferred"] == 5000
    assert result["bytes_remaining"] == 0
    assert result["photo_processing_state"] == "processing"



@pytest.mark.parametrize(
    ("case", "expected_blocker", "expected_summary"),
    [
        ("offline", "source_offline", "offline"),
        ("tool", "rclone_unavailable", "tools"),
        ("permission", "photo_storage_access_missing", "Allow photo access"),
        ("photoprism", "photoprism_unavailable", "PhotoPrism"),
        ("remote", "secure_route_unavailable", "Remote access not ready"),
        ("storage", "destination_storage_full", "protected space"),
    ],
)
def test_readiness_failure_modes_are_distinct_and_sanitized(
    photo_backup, monkeypatch, case, expected_blocker, expected_summary
):
    agent = {
        "node_id": "storage-phone",
        "name": "Storage Phone",
        "role": "storage",
        "connection": "online",
        "status": "healthy",
        "photo_backup": {
            "rclone_available": True,
            "rclone_version": "rclone v1.71.2",
            "photo_storage_access": True,
            "collections": ["camera", "pictures", "videos"],
        },
    }
    if case == "offline":
        agent["connection"] = "offline"
        agent["status"] = "offline"
    if case == "tool":
        agent["photo_backup"]["rclone_available"] = False
    if case == "permission":
        agent["photo_backup"]["photo_storage_access"] = False

    monkeypatch.setattr(photo_backup, "_agent", lambda _node_id: agent)
    monkeypatch.setattr(
        photo_backup.lite_app_runtime,
        "probe_app_runtime",
        lambda *_args, **_kwargs: {
            "running": case != "photoprism",
            "reachable": case != "photoprism",
        },
    )
    monkeypatch.setattr(
        photo_backup,
        "_secure_origin",
        lambda _request=None: None if case == "remote" else "https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        photo_backup,
        "server_capacity",
        lambda: {
            "status": "storage_full" if case == "storage" else "ready",
            "hard_upload_budget_bytes": 0 if case == "storage" else 10_000,
            "safe_upload_budget_bytes": 0 if case == "storage" else 8_000,
            "sanitized": True,
        },
    )

    result = photo_backup.readiness("storage-phone")
    assert result["ready"] is False
    assert expected_blocker in result["blockers"]
    assert expected_summary.lower() in result["summary"].lower()
    encoded = json.dumps(result).lower()
    assert "password" not in encoded
    assert "webdav_url" not in encoded


def test_protected_server_host_is_not_eligible_for_photo_backup(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "_agent",
        lambda _node_id: {
            "node_id": "server-phone",
            "name": "Server Phone",
            "role": "server_host",
            "is_current": True,
        },
    )
    result = photo_backup.readiness("server-phone")
    assert result["status"] == "not_eligible"
    assert result["ready"] is False


def test_fleet_bootstrap_keeps_rclone_failure_non_fatal():
    fleet_source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/fleet.py"
    ).read_text(encoding="utf-8")
    helper = Path(
        "pocket-lab-final-structure/"
        "pocket-lab-bootstrap-production-scripts-patched/"
        "scripts/lite/ensure-fleet-media-tools.sh"
    ).read_text(encoding="utf-8")
    base_installer = Path(
        "pocket-lab-final-structure/"
        "pocket-lab-bootstrap-production-scripts-patched/"
        "scripts/install-termux-packages.sh"
    ).read_text(encoding="utf-8")

    assert 'if ! bash "$MEDIA_TOOLS_FILE"; then' in fleet_source
    assert "Device enrollment will continue" in fleet_source
    assert "ensure_pkg_installed rclone" in helper
    assert "rclone" not in base_installer.split("local packages=(", 1)[1].split(")", 1)[0]


def test_progress_audit_is_coalesced_and_terminal_event_is_single_shot(photo_backup, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(photo_backup, "_epoch", lambda: now[0])
    state = photo_backup._state()
    state["jobs"]["photo-audit"] = {
        "backup_id": "photo-audit",
        "node_id": "storage-phone",
        "status": "transferring",
        "items_total": 10,
        "items_transferred": 2,
        "items_remaining": 8,
        "bytes_total_required": 1000,
        "bytes_transferred": 200,
        "bytes_remaining": 800,
        "started_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-audit"
    photo_backup._save_state(state)

    first = photo_backup.claim_progress_audit_events("photo-audit", "storage-phone")
    second = photo_backup.claim_progress_audit_events("photo-audit", "storage-phone")
    assert [item["event_type"] for item in first] == ["lite.photo_backup.progress"]
    assert second == []

    now[0] += 61
    third = photo_backup.claim_progress_audit_events("photo-audit", "storage-phone")
    assert [item["event_type"] for item in third] == ["lite.photo_backup.progress"]

    photo_backup._update_job(
        "photo-audit",
        status="completed",
        completed_at=photo_backup._now(),
    )
    terminal = photo_backup.claim_progress_audit_events("photo-audit", "storage-phone")
    duplicate = photo_backup.claim_progress_audit_events("photo-audit", "storage-phone")
    # No credential was created in this fixture, so terminal audit truthfully
    # reports pending rather than falsely claiming remote revocation.
    assert [item["event_type"] for item in terminal] == [
        "lite.photo_backup.completed",
        "lite.photo_backup.credential_revoke_pending",
    ]
    assert duplicate == []


def test_stale_reconciliation_records_interruption_and_revocation_evidence(photo_backup, monkeypatch):
    monkeypatch.setattr(photo_backup, "_revoke_job_credential", lambda _job: True)
    monkeypatch.setattr(photo_backup, "_epoch", lambda: 10_000.0)
    state = photo_backup._state()
    state["jobs"]["photo-stale"] = {
        "backup_id": "photo-stale",
        "node_id": "storage-phone",
        "status": "transferring",
        "started_at": "1970-01-01T00:00:01Z",
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-stale"
    photo_backup._save_state(state)
    assert photo_backup.reconcile_stale_jobs() == 1
    evidence = photo_backup._read_json(photo_backup._evidence_path(), {})
    event_types = [item.get("event_type") for item in evidence.get("events", [])]
    assert "lite.photo_backup.interrupted" in event_types
    assert "lite.photo_backup.credential_revoked" in event_types



def test_pending_terminal_credential_revocation_is_retried(photo_backup, monkeypatch):
    state = photo_backup._state()
    state["jobs"]["photo-revoke-pending"] = {
        "backup_id": "photo-revoke-pending",
        "node_id": "storage-phone",
        "status": "completed",
        "auth_id_internal": "session-pending-1234",
        "credential_revoke_status_internal": "pending",
        "started_at": photo_backup._now(),
        "completed_at": photo_backup._now(),
        "sanitized": True,
    }
    state["latest_by_node"]["storage-phone"] = "photo-revoke-pending"
    photo_backup._save_state(state)
    calls = []
    monkeypatch.setattr(
        photo_backup,
        "_revoke_auth_id",
        lambda auth_id: calls.append(auth_id) or True,
    )
    assert photo_backup.reconcile_pending_credential_revocations() == 1
    assert calls == ["session-pending-1234"]
    saved = photo_backup._state()["jobs"]["photo-revoke-pending"]
    assert saved["credential_revoke_status_internal"] == "revoked"
    evidence = photo_backup._read_json(photo_backup._evidence_path(), {})
    assert evidence["events"][0]["event_type"] == "lite.photo_backup.credential_revoked"


def test_failed_remote_revocation_is_not_reported_as_revoked(photo_backup, monkeypatch):
    job = {
        "backup_id": "photo-revoke-failed",
        "node_id": "storage-phone",
        "status": "transferring",
        "auth_id_internal": "session-failed-1234",
        "credential_expires_at": "2099-01-01T00:00:00Z",
    }
    monkeypatch.setattr(photo_backup, "_revoke_auth_id", lambda _auth_id: False)
    assert photo_backup._revoke_job_credential(job) is False



def test_photo_backup_status_read_does_not_run_reconciliation(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "reconcile_stale_jobs",
        lambda: (_ for _ in ()).throw(
            AssertionError("GET status must remain side-effect free")
        ),
    )
    monkeypatch.setattr(
        photo_backup,
        "readiness",
        lambda node_id, _request=None: {
            "status": "ready",
            "ready": True,
            "node_id": node_id,
            "sanitized": True,
        },
    )
    state = photo_backup._state()
    state["latest_by_node"]["storage-phone"] = ""
    photo_backup._save_state(state)
    result = photo_backup.status("storage-phone")
    assert result["ready"] is True


def test_auth_lookup_can_recover_session_id_from_unfiltered_json(photo_backup, monkeypatch):
    auth_name = "PocketLab-storage-phone-abcd1234"
    calls = []
    responses = iter([
        SimpleNamespace(returncode=0, stdout="[]", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps([
                {
                    "session_id": "refsession123456",
                    "client": auth_name,
                    "scope": "webdav",
                }
            ]),
            stderr="",
        ),
    ])

    def fake_command(args, timeout):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(
        photo_backup,
        "_photoprism_command",
        fake_command,
    )
    assert photo_backup._find_auth_id(auth_name) == "refsession123456"
    assert calls == [
        ["auth", "ls", "--json", auth_name],
        ["auth", "ls", auth_name],
        ["auth", "ls", "--json"],
    ]


def test_app_password_is_never_used_as_revocation_argv_identifier(photo_backup):
    source = Path(photo_backup.__file__).read_text(encoding="utf-8")
    create_body = source.split("def _create_app_password", 1)[1].split(
        "def _revoke_auth_id", 1
    )[0]
    assert "_revoke_auth_id(\n                password" not in create_body
    assert "auth_id or password" not in create_body



def test_retry_metadata_and_storage_snapshots_are_sanitized(photo_backup, monkeypatch):
    monkeypatch.setattr(
        photo_backup,
        "status",
        lambda *_args, **_kwargs: {
            "ready": True,
            "storage": {
                "status": "ready",
                "total_bytes": 1000,
                "free_bytes": 800,
                "hard_upload_budget_bytes": 700,
                "safe_upload_budget_bytes": 650,
                "sanitized": True,
            },
            "latest_backup": {
                "backup_id": "photo-prior",
                "status": "interrupted",
                "retryable": True,
                "retry_count": 2,
            },
        },
    )
    monkeypatch.setattr(
        photo_backup,
        "_agent",
        lambda node_id: {
            "node_id": node_id,
            "name": "Storage Phone",
            "role": "storage",
        },
    )
    command = photo_backup.make_start_command(
        "storage-phone",
        ["camera"],
    )
    saved = photo_backup._state()["jobs"][command["backup_id"]]
    public = photo_backup._public_job(saved)
    assert public["retry_count"] == 3
    assert public["reserve_policy"]["hard_reserve_fraction"] == 0.10
    assert public["server_storage_before"]["free_bytes"] == 800
    encoded = json.dumps(public).lower()
    assert "password" not in encoded
    assert "webdav_url" not in encoded
