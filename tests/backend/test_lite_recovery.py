from __future__ import annotations

import json
import os
import subprocess
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
if 'snapshots' in args:
    print(json.dumps([{'id': 'deadbeefcafebabe', 'short_id': 'deadbeef'}]))
    raise SystemExit(0)
if 'check' in args:
    print(json.dumps({'message_type': 'status', 'status': 'ok'}))
    raise SystemExit(0)
if 'ls' in args:
    for item in [
        {'path': '/', 'type': 'dir'},
        {'path': '/state/fleet_agents.json', 'type': 'file', 'size': 16},
        {'path': '/backup-metadata/scope.json', 'type': 'file', 'size': 32},
    ]:
        print(json.dumps(item))
    raise SystemExit(0)
if 'restore' in args:
    target = pathlib.Path(args[args.index('--target') + 1])
    (target / 'state').mkdir(parents=True, exist_ok=True)
    (target / 'state' / 'fleet_agents.json').write_text(json.dumps({'agents': {}}, indent=2, ensure_ascii=False), encoding='utf-8')
    print('restore completed')
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
    assert "restore_latest" not in payload["actions"]


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


def test_lite_restore_requires_existing_preview_after_confirmation():
    unconfirmed = client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "latest", "preview_id": "missing", "confirm": False},
    )
    assert unconfirmed.status_code == 409

    response = client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "latest", "preview_id": "missing", "confirm": True},
    )
    assert response.status_code == 404
    assert response.json()["status"] == "preview_not_found"


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
    from api_fastapi.services.nats_bus import BUS

    BUS.connected = False
    BUS.nc = None
    BUS.js = None

    async def fail_start():
        raise RuntimeError("unit-test NATS unavailable")

    monkeypatch.setattr(BUS, "start", fail_start)

    response = client().post(
        "/api/lite/recovery/backup",
        json={"include_app_data": False, "reason": "queue-failure-test"},
    )
    assert response.status_code == 503
    assert lite_backup.pending_backup() is None


def test_lite_recovery_pending_backup_is_not_reported_as_last_backup(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    lite_backup.record_backup_request({"command_id": "queued-backup-003", "reason": "queued-test"})
    payload = lite_backup.recovery_status()
    assert payload["last_backup"] is None
    assert payload["last_backup_time"] is None
    assert payload["pending_backup"]["backup_id"] == "queued-backup-003"


def test_lite_backup_failure_records_failed_pending_state(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin-failing-restic"
    bin_dir.mkdir()
    restic = bin_dir / "restic"
    restic.write_text(
        """#!/usr/bin/env python3
import os
import pathlib
import sys
args = sys.argv[1:]
repo = pathlib.Path(os.environ.get('RESTIC_REPOSITORY', ''))
if 'init' in args:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'config').write_text('{}', encoding='utf-8')
    raise SystemExit(0)
if 'backup' in args:
    print('{"message_type":"error","error":{"message":"xattr denied"}}')
    raise SystemExit(3)
print('restic 0.16.0')
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    restic.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from api_fastapi.services import lite_backup

    lite_backup.record_backup_request({"command_id": "test-backup-fail", "reason": "unit-fail"})
    with pytest.raises(RuntimeError):
        lite_backup.create_backup({"command_id": "test-backup-fail", "reason": "unit-fail"})

    pending = lite_backup.pending_backup()
    assert pending is not None
    assert pending["backup_id"] == "test-backup-fail"
    assert pending["status"] == "failed"
    assert "restic backup failed" in pending["error"]


def test_lite_backup_uses_relative_restic_source(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin-capturing-restic"
    bin_dir.mkdir()
    restic = bin_dir / "restic"
    capture = tmp_path / "restic-capture.json"
    restic.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import pathlib
import sys
args = sys.argv[1:]
repo = pathlib.Path(os.environ.get('RESTIC_REPOSITORY', ''))
if 'init' in args:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'config').write_text('{{}}', encoding='utf-8')
    raise SystemExit(0)
if 'backup' in args:
    pathlib.Path({str(capture)!r}).write_text(json.dumps({{'args': args, 'cwd': os.getcwd()}}), encoding='utf-8')
    print(json.dumps({{'message_type': 'summary', 'snapshot_id': 'relative-snapshot'}}))
    raise SystemExit(0)
print('restic 0.16.0')
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    restic.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from api_fastapi import deps
    from api_fastapi.services import lite_backup

    deps.core.write_json_file(deps.settings().state_dir / "fleet_agents.json", {"agents": {}})
    lite_backup.create_backup({"command_id": "test-backup-relative", "reason": "unit-relative"})

    captured = __import__("json").loads(capture.read_text(encoding="utf-8"))
    assert captured["args"][0:2] == ["backup", "."]
    assert "/data/data" not in captured["args"]



def test_lite_backup_verify_updates_manifest_and_receipt(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_backup, lite_backup_manifest

    deps.core.write_json_file(deps.settings().state_dir / "fleet_agents.json", {"agents": {}})
    lite_backup.create_backup({"command_id": "test-backup-verify", "reason": "unit-verify"})

    result = lite_backup.verify_backup("test-backup-verify", reason="unit-verify")
    assert result["status"] == "verified"
    assert result["verified_at"]
    assert all(check["status"] == "passed" for check in result["checks"])

    manifest = lite_backup_manifest.read_manifest("test-backup-verify")
    receipt = lite_backup_manifest.read_receipt("test-backup-verify")
    assert manifest is not None
    assert receipt is not None
    assert manifest["verification_status"] == "verified"
    assert manifest["verified_at"] == result["verified_at"]
    assert manifest["verification"]["status"] == "verified"
    assert receipt["verification_status"] == "verified"
    assert receipt["verification_checks"]

    status = lite_backup.recovery_status()
    assert status["last_verification_result"] == "verified"
    assert "verify_backup" in status["actions"]
    assert "preview_restore" in status["actions"]


def test_lite_restore_preview_writes_preview_without_restore(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_backup

    deps.core.write_json_file(deps.settings().state_dir / "fleet_agents.json", {"agents": {}})
    lite_backup.create_backup({"command_id": "test-backup-preview", "reason": "unit-preview"})
    lite_backup.verify_backup("test-backup-preview", reason="unit-preview")

    preview = lite_backup.create_restore_preview("test-backup-preview", reason="unit-preview")
    assert preview["status"] == "ready"
    assert preview["restore_allowed"] is True
    assert preview["restore_supported"] is True
    assert preview["verification_status"] == "verified"
    assert preview["change_count"] > 0
    assert preview["restic_item_count"] >= 1
    assert any(change["relative_path"] == "state/fleet_agents.json" for change in preview["changes"])

    loaded = lite_backup.get_restore_preview(preview["preview_id"])
    assert loaded is not None
    assert loaded["preview_id"] == preview["preview_id"]

    status = lite_backup.recovery_status()
    assert status["latest_restore_preview"]["preview_id"] == preview["preview_id"]


def test_lite_restore_apply_requires_confirmation_and_ready_preview(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    preview_id = "preview-guard"
    preview = {
        "preview_id": preview_id,
        "backup_id": "backup-guard",
        "snapshot_id": "deadbeefcafebabe",
        "status": "ready",
        "verification_status": "verified",
        "restore_allowed": False,
        "restore_supported": True,
        "changes": [],
    }
    path = lite_backup.restore_preview_path(preview_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview), encoding="utf-8")

    with pytest.raises(RuntimeError, match="explicit confirmation"):
        lite_backup.apply_restore(
            {
                "command_id": "test-restore-guard",
                "backup_id": "backup-guard",
                "preview_id": preview_id,
                "confirm": False,
            }
        )

    with pytest.raises(RuntimeError, match="not marked as restorable"):
        lite_backup.apply_restore(
            {
                "command_id": "test-restore-guard-2",
                "backup_id": "backup-guard",
                "preview_id": preview_id,
                "confirm": True,
            }
        )
