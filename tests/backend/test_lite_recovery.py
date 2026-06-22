from __future__ import annotations

import os
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_lite_recovery_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ROOT", str(tmp_path / "lite-backups"))
    yield


def _install_fake_restic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    restic = bin_dir / "restic"
    restic.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
repo = pathlib.Path(os.environ.get('RESTIC_REPOSITORY', ''))
if 'init' in args:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'config').write_text('{}', encoding='utf-8')
    print('created restic repository')
    raise SystemExit(0)
if 'backup' in args:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'latest-snapshot').write_text('deadbeefcafebabe', encoding='utf-8')
    print(json.dumps({'message_type': 'summary', 'snapshot_id': 'deadbeefcafebabe'}))
    raise SystemExit(0)
if 'version' in args or not args:
    print('restic 0.16.0')
    raise SystemExit(0)
print(json.dumps({'message_type': 'summary', 'snapshot_id': 'deadbeefcafebabe'}))
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    restic.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")


def test_lite_recovery_status_reports_repository_shape(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    payload = lite_backup.recovery_status()
    assert payload["repository"]["engine"] == "restic"
    assert payload["repository"]["encrypted"] is True
    assert "raw API tokens" in payload["what_will_not_be_backed_up"]
    assert "backup_now" in payload["actions"]
    assert "restore_latest" in payload["planned_actions"]


def test_lite_backup_create_writes_manifest_and_receipt(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_backup, lite_backup_manifest

    deps.core.write_json_file(
        deps.settings().state_dir / "fleet_agents.json",
        {"agents": {"phone-2": {"status": "healthy"}}},
    )

    result = lite_backup.create_backup({"command_id": "test-backup-001", "reason": "unit-test"})
    assert result["status"] == "succeeded"
    assert result["snapshot_id"] == "deadbeefcafebabe"

    manifest = lite_backup_manifest.read_manifest("test-backup-001")
    receipt = lite_backup_manifest.read_receipt("test-backup-001")
    assert manifest is not None
    assert receipt is not None
    assert manifest["engine"] == "restic"
    assert manifest["repository"]["encrypted"] is True
    assert manifest["manifest_checksum"]
    assert manifest["verification_status"] == "not_verified"
    assert any(item["relative_path"] == "state/fleet_agents.json" for item in manifest["included_files"])
    assert receipt["evidence_saved"] is True
    assert "pocketlab.audit.lite.backup.created" in receipt["evidence_references"]


def test_lite_recovery_backup_history_endpoints(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_backup

    deps.core.write_json_file(deps.settings().state_dir / "fleet_agent_commands.json", {"commands": []})
    lite_backup.create_backup({"command_id": "test-backup-002", "reason": "endpoint-test"})

    list_response = client().get("/api/lite/recovery/backups")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["latest_backup"]["backup_id"] == "test-backup-002"

    item_response = client().get("/api/lite/recovery/backups/latest")
    assert item_response.status_code == 200
    assert item_response.json()["backup_id"] == "test-backup-002"

    receipt_response = client().get("/api/lite/recovery/receipts/latest")
    assert receipt_response.status_code == 200
    assert receipt_response.json()["summary"] == "Evidence saved"


def test_lite_restore_confirmed_fails_closed_until_preview_exists():
    response = client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "latest", "preview_id": "missing", "confirm": True},
    )
    assert response.status_code == 501
    assert response.json()["status"] == "restore_not_implemented"


def test_lite_recovery_latest_endpoints_are_script_friendly_before_first_backup(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)

    list_response = client().get("/api/lite/recovery/backups")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 0
    assert list_payload["status"] in {"degraded", "unavailable"}
    assert list_payload["latest_backup"] is None

    latest_response = client().get("/api/lite/recovery/backups/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["status"] == "not_created"
    assert latest_payload["latest_backup_available"] is False

    receipt_response = client().get("/api/lite/recovery/receipts/latest")
    assert receipt_response.status_code == 200
    receipt_payload = receipt_response.json()
    assert receipt_payload["status"] == "not_created"
    assert receipt_payload["latest_backup_available"] is False


def test_lite_recovery_pending_backup_is_visible_until_worker_finishes(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    pending = lite_backup.record_backup_request({"command_id": "queued-backup-001", "reason": "queued-test"})
    assert pending["backup_id"] == "queued-backup-001"

    latest_response = client().get("/api/lite/recovery/backups/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["backup_id"] == "queued-backup-001"
    assert latest_payload["status"] == "queued"
    assert latest_payload["pending"] is True

    history_response = client().get("/api/lite/recovery/backups")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["status"] == "queued"
    assert history_payload["pending_backup"]["backup_id"] == "queued-backup-001"


def test_lite_backup_queue_failure_does_not_create_pending_state(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    response = client().post(
        "/api/lite/recovery/backup",
        json={"include_app_data": False, "reason": "queue-failure-test"},
    )
    assert response.status_code in {403, 503}
    assert lite_backup.pending_backup() is None


def test_lite_recovery_pending_backup_is_not_reported_as_last_backup(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    lite_backup.record_backup_request({"command_id": "queued-backup-003", "reason": "queued-test"})
    payload = lite_backup.recovery_status()
    assert payload["last_backup"] is None
    assert payload["last_backup_time"] is None
    assert payload["pending_backup"]["backup_id"] == "queued-backup-003"
