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
