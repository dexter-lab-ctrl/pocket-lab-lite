from __future__ import annotations

import json
import os
import shutil
import subprocess
import sqlite3
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture(autouse=True)
def isolate_lite_recovery_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    database = prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    state = database.parent
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
    assert manifest["format_version"] == 2
    assert manifest["restorable"] is False
    assert manifest["component_results"]["control_plane_database"]["status"] == "validated"
    assert manifest["component_results"]["media_exclusion"]["status"] == "validated"
    assert any(item["relative_path"] == "state/fleet_agents.json" for item in manifest["included_files"])
    assert receipt["evidence_saved"] is True
    assert "pocketlab.audit.lite.backup.created" in receipt["evidence_references"]


def test_manifest_history_releases_full_inventory_and_reuses_cached_summary(tmp_path, monkeypatch):
    from api_fastapi.services import lite_backup_manifest

    backup_id = "history-summary-cache"
    lite_backup_manifest.write_manifest({
        "backup_id": backup_id,
        "created_at": "2026-09-09T00:00:00Z",
        "format_version": 2,
        "engine": "restic",
        "verification_status": "verified",
        "restorable": True,
        "size_bytes": 1234,
        "included_sets": ["Pocket Lab settings"],
        "included_files": [
            {"relative_path": f"state/event-{index}.json", "size_bytes": 1}
            for index in range(4096)
        ],
    })

    reads: list[Path] = []
    original_read_json = lite_backup_manifest._read_json

    def recording_read_json(path: Path, default):
        reads.append(path)
        return original_read_json(path, default)

    monkeypatch.setattr(lite_backup_manifest, "_read_json", recording_read_json)
    first = lite_backup_manifest.list_manifests_page(limit=1)
    assert first["items"][0]["included_file_count"] == 4096
    assert "included_files" not in first["items"][0]
    assert len(reads) == 1

    reads.clear()
    second = lite_backup_manifest.list_manifests_page(limit=1)
    assert second["items"][0]["backup_id"] == backup_id
    assert reads == []


def test_lite_backup_create_reuses_completed_manifest_on_command_redelivery(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    calls = []
    original_run_restic = lite_backup._run_restic

    def counting_run_restic(*args, **kwargs):
        calls.append(args[0])
        return original_run_restic(*args, **kwargs)

    monkeypatch.setattr(lite_backup, "_run_restic", counting_run_restic)
    first = lite_backup.create_backup({"command_id": "test-backup-redelivery", "reason": "unit-retry"})
    call_count = len(calls)

    replay = lite_backup.create_backup({"command_id": "test-backup-redelivery", "reason": "unit-retry"})

    assert call_count > 0
    assert len(calls) == call_count
    assert replay["status"] == "succeeded"
    assert replay["idempotent_replay"] is True
    assert replay["snapshot_id"] == first["snapshot_id"]


def test_lite_backup_streams_registered_event_state_and_honors_exclusion_flag(
    tmp_path, monkeypatch
):
    from api_fastapi import deps
    from api_fastapi.services import lite_backup_policy

    state_dir = deps.settings().state_dir
    (state_dir / "catalog.json").write_text("{}", encoding="utf-8")
    (state_dir / "events").mkdir()
    (state_dir / "events" / "event-1.json").write_text("{}", encoding="utf-8")
    (state_dir / "events" / "nested").mkdir()
    (state_dir / "events" / "nested" / "event-2.json").write_text("{}", encoding="utf-8")

    selected = list(lite_backup_policy.iter_state_sources(include_event_journal=True))
    excluded = list(lite_backup_policy.iter_state_sources(include_event_journal=False))

    assert {item["relative_path"] for item in selected} >= {
        "state/catalog.json",
        "state/events/event-1.json",
        "state/events/nested/event-2.json",
    }
    assert {item["relative_path"] for item in excluded} == {"state/catalog.json"}


def test_lite_backup_does_not_buffer_restic_backup_progress(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    calls = []
    original_run_restic = lite_backup._run_restic

    def recording_run_restic(*args, **kwargs):
        calls.append((list(args[0]), kwargs.get("capture_stdout", True)))
        return original_run_restic(*args, **kwargs)

    monkeypatch.setattr(lite_backup, "_run_restic", recording_run_restic)
    result = lite_backup.create_backup(
        {"command_id": "test-backup-streaming", "include_event_journal": False}
    )

    assert result["status"] == "succeeded"
    backup_calls = [item for item in calls if "backup" in item[0]]
    assert backup_calls and backup_calls[0][1] is False
    assert result["manifest"]["include_event_journal"] is False


def test_restore_point_metadata_is_bounded_and_media_paths_fail_closed(tmp_path, monkeypatch):
    from api_fastapi.services import lite_backup_manifest, lite_backup_policy

    assert lite_backup_policy.is_excluded_media_path(Path("/storage/emulated/0/DCIM/photo.jpg"))
    assert lite_backup_policy.is_excluded_media_path(Path("/data/photoprism/originals/photo.jpg"))
    assert not lite_backup_policy.is_excluded_media_path(Path("state/opa.json"))
    assert lite_backup_manifest.resolve_backup_id("../private") is None
    with pytest.raises(ValueError):
        lite_backup_manifest.manifest_path("../private")

    public = lite_backup_manifest.api_manifest({
        "backup_id": "safe-1",
        "format_version": 2,
        "repository": {"location": "/home/private/restic", "encrypted": True},
        "included_files": [],
        "verification_status": "verified",
        "restorable": True,
    })
    assert public["repository"]["location"] == "Configured encrypted repository"
    assert "/home/private" not in json.dumps(public)
    assert "restic_password" not in json.dumps(public).lower()


def test_recovery_freshness_contract_has_bounded_source_and_cache_windows():
    from api_fastapi.services import lite_core_projections, lite_recovery_subprojections, lite_semantic_revisions

    summary = lite_semantic_revisions.contract_for("recovery", "summary")
    details = lite_semantic_revisions.contract_for("recovery", "details")
    assert summary is not None and details is not None
    assert summary.max_probe_seconds <= lite_recovery_subprojections.RECOVERY_SUMMARY_TTL_SECONDS
    assert details.max_probe_seconds <= lite_recovery_subprojections.RECOVERY_DETAILS_TTL_SECONDS
    assert lite_core_projections.RECOVERY_SUMMARY_STALE_AFTER_MS == 10_000
    assert lite_core_projections.RECOVERY_DETAILS_STALE_AFTER_MS == 15_000
    assert lite_core_projections.RECOVERY_SUMMARY_MAX_STALE_MS == 60_000
    assert lite_core_projections.RECOVERY_DETAILS_MAX_STALE_MS == 90_000


def test_recovery_base_bootstrap_does_not_launch_fence_sensitive_collector(monkeypatch):
    from api_fastapi.services import lite_core_projections, lite_status

    with lite_core_projections._RECOVERY_BASE_LOCK:
        lite_core_projections._RECOVERY_BASE_VALUE = None
        lite_core_projections._RECOVERY_BASE_FAILURES = 0
        lite_core_projections._RECOVERY_BASE_NEXT_ALLOWED = 0.0
        lite_core_projections._RECOVERY_BASE_FUTURE = None

    def deep_collector_must_not_run():
        raise AssertionError("Recovery bootstrap invoked the deep details collector")

    monkeypatch.setattr(lite_status, "lite_recovery_details", deep_collector_must_not_run)
    monkeypatch.setattr(
        lite_core_projections.CONTROL_PLANE,
        "prepared_payload",
        lambda _key: None,
    )

    def submit_must_not_run(_callback):
        raise AssertionError("Recovery bootstrap submitted a fence-sensitive collector")

    monkeypatch.setattr(lite_core_projections._RECOVERY_BASE_EXECUTOR, "submit", submit_must_not_run)

    payload = lite_core_projections.recovery_base_subprojection()

    assert payload["status"] == "degraded"
    assert payload["read_degraded"] is True
    assert payload["refresh_pending"] is False


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

    missing_backup = client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "latest", "preview_id": "missing", "confirm": True},
    )
    assert missing_backup.status_code == 409
    assert missing_backup.json()["status"] == "backup_required"

    response = client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "backup-missing", "preview_id": "missing", "confirm": True},
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
if 'snapshots' in args:
    print(json.dumps([{{'id': 'relative-snapshot'}}]))
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

    # A failed repository-integrity check is derived by the verifier.  A
    # later verification must be able to recover once the repository is
    # healthy instead of treating the previous derived failure as a source
    # component failure.
    manifest["component_results"]["repository_integrity"] = {
        "status": "failed",
        "required": True,
    }
    lite_backup_manifest.write_manifest(manifest)
    retry = lite_backup.verify_backup("test-backup-verify", reason="retry after repository recovery")
    assert retry["status"] == "verified"
    assert all(check["status"] == "passed" for check in retry["checks"])


def test_recovery_uses_durable_worker_reconciliation_for_idle_freshness(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import projection_scheduler
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    old = "2026-07-01T00:00:00Z"
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    CONTROL_PLANE.project_recovery(
        {"status": "healthy", "summary": "Saved recovery state.", "updated_at": old}
    )
    reconciled_at = deps.now_utc_iso()
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain, generation, committed_generation, dirty, active,
                last_completed_at, last_error_type, updated_at
            ) VALUES (?, 1, 1, 0, 0, ?, '', ?)
            ON CONFLICT(domain) DO UPDATE SET
                generation=1, committed_generation=1, dirty=0, active=0,
                last_completed_at=excluded.last_completed_at,
                last_error_type='', updated_at=excluded.updated_at
            """,
            ("recovery.summary", reconciled_at, reconciled_at),
        )

    class SchedulerStub:
        def status(self, _domain):
            return {
                "registered": True,
                "refresh_pending": True,
                "dirty": False,
                "active": False,
                "queued": False,
                "last_error_type": "",
                "source_revision": 1,
            }

        def mark_dirty(self, *_args, **_kwargs):
            return {"accepted": True, "refresh_pending": False, "retry_after_seconds": 0}

    monkeypatch.setattr(projection_scheduler, "PROJECTION_SCHEDULER", SchedulerStub())
    store = ControlPlaneProjectionStore()
    read = store.prepared_only_read(
        domain="recovery",
        key="summary",
        snapshot_builder=CONTROL_PLANE.recovery_projection_snapshot,
        builder=lambda: (_ for _ in ()).throw(AssertionError("collector must not run")),
        projector=CONTROL_PLANE.project_recovery,
        stale_after_ms=10_000,
        max_stale_ms=60_000,
    )
    assert read.read_degraded is False
    assert read.projection_age_ms < 10_000
    assert read.degraded_reason == ""


def test_recovery_summary_and_details_use_independent_worker_completion_timestamps(
    tmp_path, monkeypatch
):
    from api_fastapi import deps
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    CONTROL_PLANE.project_recovery(
        {"status": "healthy", "summary": "Saved recovery state.", "updated_at": "2026-07-01T00:00:00Z"}
    )
    now = deps.now_utc_iso()
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        for domain, completed_at in (
            ("recovery.summary", now),
            ("recovery.details", "2026-07-01T00:00:01Z"),
        ):
            conn.execute(
                """
                INSERT INTO projection_refresh_state(
                    domain, generation, committed_generation, dirty, active,
                    last_completed_at, last_error_type, updated_at
                ) VALUES (?, 1, 1, 0, 0, ?, '', ?)
                ON CONFLICT(domain) DO UPDATE SET
                    generation=1, committed_generation=1, dirty=0, active=0,
                    last_completed_at=excluded.last_completed_at,
                    last_error_type='', updated_at=excluded.updated_at
                """,
                (domain, completed_at, completed_at),
            )

    summary = CONTROL_PLANE.recovery_projection_snapshot(details=False)
    details = CONTROL_PLANE.recovery_projection_snapshot(details=True)
    assert summary is not None and details is not None
    assert summary["updated_at"] == now
    assert details["updated_at"] == "2026-07-01T00:00:01Z"


def test_recovery_existing_api_cache_advances_from_newer_worker_completion(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import projection_scheduler
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, CONTROL_PLANE

    CONTROL_PLANE.project_recovery(
        {"status": "healthy", "summary": "Saved recovery state.", "updated_at": "2026-07-01T00:00:00Z"}
    )
    old_completed = "2026-07-01T00:00:01Z"
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain,generation,committed_generation,dirty,active,
                last_completed_at,last_error_type,updated_at
            ) VALUES (?,1,1,0,0,?,'',?)
            ON CONFLICT(domain) DO UPDATE SET
                generation=1,committed_generation=1,dirty=0,active=0,
                last_completed_at=excluded.last_completed_at,
                last_error_type='',updated_at=excluded.updated_at
            """,
            ("recovery.summary", old_completed, old_completed),
        )

    class SchedulerStub:
        def status(self, _domain):
            return {"registered": True, "refresh_pending": False, "dirty": False, "active": False, "queued": False}

        def mark_dirty(self, *_args, **_kwargs):
            return {"accepted": True, "refresh_pending": False, "retry_after_seconds": 0}

    monkeypatch.setattr(projection_scheduler, "PROJECTION_SCHEDULER", SchedulerStub())
    store = ControlPlaneProjectionStore()
    first = store.prepared_only_read(
        domain="recovery", key="summary", snapshot_builder=CONTROL_PLANE.recovery_projection_snapshot,
        builder=lambda: (_ for _ in ()).throw(AssertionError("collector must not run")),
        projector=CONTROL_PLANE.project_recovery, stale_after_ms=10_000, max_stale_ms=60_000,
    )
    assert first.read_degraded is True

    fresh_completed = deps.now_utc_iso()
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        conn.execute(
            "UPDATE projection_refresh_state SET last_completed_at=?,updated_at=?,last_error_type='' WHERE domain=?",
            (fresh_completed, fresh_completed, "recovery.summary"),
        )
    second = store.prepared_only_read(
        domain="recovery", key="summary", snapshot_builder=CONTROL_PLANE.recovery_projection_snapshot,
        builder=lambda: (_ for _ in ()).throw(AssertionError("collector must not run")),
        projector=CONTROL_PLANE.project_recovery, stale_after_ms=10_000, max_stale_ms=60_000,
    )
    assert second.read_degraded is False
    assert second.projection_age_ms < 10_000


def test_recovery_durable_reconciliation_does_not_bypass_stuck_projection_fence(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import projection_scheduler
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, CONTROL_PLANE

    CONTROL_PLANE.project_recovery(
        {"status": "healthy", "summary": "Old recovery state.", "updated_at": "2026-07-01T00:00:00Z"}
    )
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain, generation, committed_generation, dirty, active,
                last_completed_at, last_error_type, updated_at
            ) VALUES (?, 1, 1, 0, 0, ?, '', ?)
            ON CONFLICT(domain) DO UPDATE SET
                last_completed_at=excluded.last_completed_at,
                dirty=0, active=0, last_error_type=''
            """,
            ("recovery.summary", "2026-07-01T00:00:01Z", "2026-07-01T00:00:01Z"),
        )

    class SchedulerStub:
        def status(self, _domain):
            return {"registered": True, "refresh_pending": False, "dirty": False, "active": False, "queued": False}

        def mark_dirty(self, *_args, **_kwargs):
            return {"accepted": True, "refresh_pending": True, "retry_after_seconds": 0}

    monkeypatch.setattr(projection_scheduler, "PROJECTION_SCHEDULER", SchedulerStub())
    store = ControlPlaneProjectionStore()
    read = store.prepared_only_read(
        domain="recovery",
        key="summary",
        snapshot_builder=CONTROL_PLANE.recovery_projection_snapshot,
        builder=lambda: {"status": "healthy"},
        projector=CONTROL_PLANE.project_recovery,
        stale_after_ms=10_000,
        max_stale_ms=60_000,
    )
    assert read.read_degraded is True
    assert read.degraded_reason == "projection_too_old"
    assert read.projection_age_ms > 60_000


def test_recovery_details_revision_ignores_unrelated_fleet_heartbeat(monkeypatch):
    from api_fastapi.services import lite_semantic_revisions

    def read_rows(sql, params=()):
        if "domain_revisions" in sql:
            raise AssertionError("details revision must not depend on fleet revisions")
        return []

    monkeypatch.setattr(
        lite_semantic_revisions,
        "_read_json_semantics",
        lambda path: {"file": path.name, "state": "ready", "value": {}},
    )
    monkeypatch.setattr(lite_semantic_revisions, "_read_rows", read_rows)
    first = lite_semantic_revisions.recovery_details_source_revision()
    second = lite_semantic_revisions.recovery_details_source_revision()
    assert second == first


def test_recovery_target_revision_ignores_command_lifecycle_churn(monkeypatch):
    from api_fastapi.services import lite_semantic_revisions

    commands = [{"command_id": "preview-command", "status": "running"}]
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_recovery_rows",
        lambda: {"commands": list(commands), "database_backups": []},
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_read_json_semantics",
        lambda path: {"file": Path(path).name, "state": "ready"},
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_manifest_semantics",
        lambda: {"state": "ready", "rows": []},
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "app_semantic_material",
        lambda **_kwargs: {"state": "ready"},
    )

    first = lite_semantic_revisions.recovery_target_revision()
    commands[0]["status"] = "completed"
    second = lite_semantic_revisions.recovery_target_revision()

    assert second == first


def test_recovery_target_revision_ignores_restore_progress_files(monkeypatch):
    from api_fastapi.services import lite_semantic_revisions

    values = {"latest_restore_preview": {"preview_id": "old"}}
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_recovery_rows",
        lambda: {"database_backups": [], "database_restores": []},
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_read_json_semantics",
        lambda path: {
            "file": Path(path).name,
            "state": "ready",
            "value": dict(values) if Path(path).name == "backup_state.json" else {},
        },
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "_manifest_semantics",
        lambda: {"state": "ready", "rows": []},
    )
    monkeypatch.setattr(
        lite_semantic_revisions,
        "app_semantic_material",
        lambda **_kwargs: {"state": "ready"},
    )

    first = lite_semantic_revisions.recovery_target_revision()
    values["latest_restore_preview"] = {"preview_id": "new"}
    values["last_restore"] = {"restore_id": "restore-progress"}
    second = lite_semantic_revisions.recovery_target_revision()

    assert second == first


def test_recovery_scheduler_cadence_stays_inside_prepared_read_fences():
    from api_fastapi.services.adaptive_runtime import DOMAIN_CADENCE_SECONDS

    for domain, max_stale_ms in (("recovery.summary", 60_000), ("recovery.details", 90_000)):
        _active, stable, maximum = DOMAIN_CADENCE_SECONDS[domain]
        assert stable * 1.04 < max_stale_ms / 1000
        assert maximum * 1.04 < max_stale_ms / 1000


def test_prepared_projection_cadences_stay_inside_all_runtime_read_fences():
    from api_fastapi.services.adaptive_runtime import DOMAIN_CADENCE_SECONDS

    fences = {
        "fleet.summary": 300,
        "apps.catalog": 300,
        "apps.lifecycle": 90,
        "apps.actions:photoprism": 90,
        "security.progress": 300,
        "security.summary": 300,
        "system.status": 300,
        "system.health": 300,
        "system.processes": 300,
        "system.agent": 300,
        "system.supervisor": 300,
        "system.remote_access": 300,
        "system.nats_remote": 300,
        "system.fleet_probe": 300,
        "system.telemetry_thresholds": 600,
        "system.storage_pressure": 600,
        "system.sqlite_health": 600,
        "system.activity_current": 600,
        "system.activity_history": 600,
        "system.activity_summary": 600,
    }
    for domain, max_stale_seconds in fences.items():
        _active, stable, maximum = DOMAIN_CADENCE_SECONDS[domain]
        assert stable * 1.04 < max_stale_seconds
        assert maximum * 1.04 < max_stale_seconds


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
    assert "Lite runtime state" in preview["included_components"]
    assert preview["excluded_components"]
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

    with pytest.raises(RuntimeError, match="explicit backup_id"):
        lite_backup.apply_restore(
            {
                "command_id": "test-restore-guard-missing-backup",
                "backup_id": "latest",
                "preview_id": preview_id,
                "confirm": True,
            }
        )

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



def test_lite_restore_service_restart_and_health_helpers(monkeypatch):
    from api_fastapi.services import lite_backup

    assert lite_backup._restore_service_restart_if_needed([])["status"] == "not_required"

    monkeypatch.setenv("POCKETLAB_LITE_RESTORE_ALLOW_SERVICE_RESTART", "1")
    monkeypatch.setattr(lite_backup.shutil, "which", lambda _name: "/termux/bin/pm2")
    restart_calls = []
    monkeypatch.setattr(
        lite_backup.subprocess,
        "run",
        lambda args, **_kwargs: (
            restart_calls.append(list(args))
            or subprocess.CompletedProcess(args, 0, "", "")
        ),
    )
    restarted = lite_backup._restore_service_restart_if_needed(
        [{"relative_path": "state/catalog.json"}]
    )
    assert restarted["status"] == "succeeded"
    assert restart_calls == [["/termux/bin/pm2", "restart", "pocket-api"]]

    class Response:
        status = 200
        payload = b'{"status":"healthy"}'

        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self, _limit):
            return self.payload

    requested = []
    monkeypatch.setattr(
        lite_backup.urllib.request,
        "urlopen",
        lambda request, **kwargs: (requested.append(str(request.full_url if hasattr(request, "full_url") else request)) or Response()),
    )
    result = lite_backup._validate_lite_api_health()
    assert result["status"] == "passed"
    assert result["recovery_status"] == "healthy"
    assert requested == ["http://127.0.0.1:8443/health"]

    monkeypatch.setenv("POCKETLAB_LITE_RESTORE_HEALTH_ATTEMPTS", "2")
    Response.payload = b'{"status":"healthy","read_degraded":true,"degraded_reason":"projection_too_old"}'
    degraded = lite_backup._validate_lite_api_health()
    assert degraded["status"] == "failed"
    assert degraded["degraded_reason"] == "projection_too_old"


def test_restore_validation_failure_keeps_only_bounded_safe_checks():
    from api_fastapi.services.lite_backup import RestoreValidationError

    error = RestoreValidationError(
        {
            "service_restart": {"status": "succeeded", "path": "/private/runtime"},
            "health_validation": {
                "status": "failed",
                "http_status": 200,
                "read_degraded": True,
                "degraded_reason": "projection_too_old",
                "url": "http://127.0.0.1/private",
            },
            "application_validation": {
                "status": "failed",
                "running": True,
                "reachable": False,
                "attempt_count": 6,
            },
        }
    )

    assert error.safe_checks == {
        "service_restart_status": "succeeded",
        "health_status": "failed",
        "health_http_status": 200,
        "health_read_degraded": True,
        "health_degraded_reason": "projection_too_old",
        "application_status": "failed",
        "application_running": True,
        "application_reachable": False,
        "application_attempt_count": 6,
        "sanitized": True,
    }
    encoded = json.dumps(error.safe_checks)
    assert "/private" not in encoded
    assert "127.0.0.1" not in encoded


def test_selected_full_restore_uses_canonical_sqlite_transaction(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_backup, lite_backup_manifest, lite_database_recovery
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    repo.reserve_scan(
        run_id="full-restore-source",
        profile="quick",
        requested_at="2026-09-01T00:00:00Z",
    )
    repo.mark_running("full-restore-source", started_at="2026-09-01T00:00:01Z")
    repo.complete_run(
        "full-restore-source",
        completed_at="2026-09-01T00:00:02Z",
        score=100,
        summary="Source state",
    )
    assert lite_database_recovery._refresh_security_projections()["status"] == "passed"
    deps.core.write_json_file(
        deps.settings().state_dir / "fleet_agents.json",
        {"agents": {"server": {"status": "healthy"}}},
    )

    backup_id = "full-restore-selected"
    lite_backup.create_backup({"command_id": backup_id, "reason": "selected restore test"})
    assert lite_backup.verify_backup(backup_id)["status"] == "verified"
    manifest = lite_backup_manifest.read_manifest(backup_id)
    assert manifest is not None

    # Preserve the source tree that a real restic restore would materialize.
    saved_snapshot = tmp_path / "saved-snapshot"
    saved_snapshot.mkdir()
    for item in manifest.get("included_files") or []:
        relative = str(item.get("relative_path") or "")
        if not relative.startswith("state/"):
            continue
        source = deps.settings().state_dir / Path(relative).relative_to("state")
        if source.is_file():
            target = saved_snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    saved_package = tmp_path / "saved-database-backup"
    shutil.copytree(
        lite_database_recovery.database_backup_package(f"{backup_id}-database"),
        saved_package,
    )

    # Add state after the backup. The selected restore must remove it from the
    # canonical database rather than silently restoring only JSON files.
    repo.reserve_scan(
        run_id="full-restore-future",
        profile="quick",
        requested_at="2026-09-02T00:00:00Z",
    )
    repo.mark_running("full-restore-future", started_at="2026-09-02T00:00:01Z")
    repo.complete_run(
        "full-restore-future",
        completed_at="2026-09-02T00:00:02Z",
        score=90,
        summary="Future state",
    )
    preview = lite_backup.create_restore_preview(backup_id, reason="selected restore test")

    original_run_restic = lite_backup._run_restic

    def restore_saved_snapshot(args, *, env, timeout=180, cwd=None, capture_stdout=True):
        if "restore" in args:
            target = Path(args[args.index("--target") + 1])
            if saved_snapshot.exists():
                for source in saved_snapshot.rglob("*"):
                    if source.is_file():
                        destination = target / source.relative_to(saved_snapshot)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
            shutil.copytree(saved_package, target / "database-backup")
            return subprocess.CompletedProcess(args, 0, "restore completed", "")
        return original_run_restic(
            args,
            env=env,
            timeout=timeout,
            cwd=cwd,
            capture_stdout=capture_stdout,
        )

    monkeypatch.setattr(lite_backup, "_run_restic", restore_saved_snapshot)
    monkeypatch.setattr(
        lite_backup,
        "_restore_service_restart_if_needed",
        lambda _files: {"status": "not_required", "needed": False, "services": []},
    )
    monkeypatch.setattr(
        lite_backup,
        "_validate_lite_api_health",
        lambda: {"status": "passed", "http_status": 200, "recovery_status": "healthy"},
    )

    fence_events = []
    original_projection_fence = lite_database_recovery._database_switch_projection_fence

    def tracking_projection_fence():
        context = original_projection_fence()

        class TrackingFence:
            def __enter__(self):
                fence_events.append("enter")
                return context.__enter__()

            def __exit__(self, exc_type, exc, tb):
                try:
                    return context.__exit__(exc_type, exc, tb)
                finally:
                    fence_events.append("exit")

        return TrackingFence()

    monkeypatch.setattr(
        lite_database_recovery,
        "_database_switch_projection_fence",
        tracking_projection_fence,
    )
    result = lite_backup.apply_restore(
        {
            "command_id": "full-restore-selected-run",
            "backup_id": backup_id,
            "preview_id": preview["preview_id"],
            "confirm": True,
            "reason": "selected restore test",
        }
    )
    assert result["status"] == "succeeded", json.dumps(result, indent=2, default=str)
    assert result["database_restore"]["phase"] == "committed"
    assert fence_events == ["enter", "exit", "enter", "exit"]
    assert result["restored_file_count"] >= 1
    with sqlite3.connect(str(deps.settings().state_dir / "pocketlab-lite.sqlite3")) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id='full-restore-source'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id='full-restore-future'"
        ).fetchone()[0] == 0
    assert not (lite_backup.backup_layout().staging / "restore-full-restore-selected-run").exists()


def test_restore_journal_is_created_before_restic_staging_and_closes_on_failure(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup, lite_restore_transaction

    backup_id = "preflight-journal-backup"
    lite_backup.create_backup({"command_id": backup_id, "reason": "preflight journal test"})
    assert lite_backup.verify_backup(backup_id)["status"] == "verified"
    preview = lite_backup.create_restore_preview(backup_id, reason="preflight journal test")

    original_run_restic = lite_backup._run_restic

    def fail_snapshot_materialization(args, *, env, timeout=180, cwd=None, capture_stdout=True):
        if "restore" in args:
            raise RuntimeError("simulated restic interruption")
        return original_run_restic(
            args,
            env=env,
            timeout=timeout,
            cwd=cwd,
            capture_stdout=capture_stdout,
        )

    monkeypatch.setattr(lite_backup, "_run_restic", fail_snapshot_materialization)
    with pytest.raises(RuntimeError, match="simulated restic interruption"):
        lite_backup.apply_restore(
            {
                "command_id": "preflight-interrupted-restore",
                "backup_id": backup_id,
                "preview_id": preview["preview_id"],
                "confirm": True,
            }
        )

    journal = lite_restore_transaction.read_journal("preflight-interrupted-restore")
    assert journal is not None
    assert journal["restore_stage"] == "restic_restore"
    assert journal["preflight"] is True
    assert journal["phase"] == "rolled_back"
    assert journal["failure_category"] == "restore_interrupted"
    assert journal["api_worker_restart_allowed"] is True
    assert not (
        lite_backup.backup_layout().staging / "restore-preflight-interrupted-restore"
    ).exists()
    assert lite_restore_transaction.guard_status()["unresolved"] is False


def test_startup_recovery_closes_preflight_journal_and_cleans_registered_staging(tmp_path, monkeypatch):
    from api_fastapi.services import lite_backup, lite_database_recovery, lite_restore_transaction

    staging_key = "restore-startup-preflight"
    stage = lite_backup.backup_layout().staging / staging_key
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "partial-artifact").write_text("bounded test artifact", encoding="utf-8")
    lite_restore_transaction.create_journal(
        restore_id="startup-preflight-restore",
        backup_id="startup-preflight-backup",
        preview_id="startup-preflight-preview",
        target_names=["state/catalog.json"],
        preflight=True,
        snapshot_id="startup-preflight-snapshot",
        manifest_checksum="a" * 64,
        staging_key=staging_key,
    )
    lite_restore_transaction.update_journal(
        "startup-preflight-restore",
        phase="staging",
        summary="Simulated worker interruption during restic staging.",
    )

    recovered = lite_database_recovery.recover_restore_transaction("startup-preflight-restore")

    assert recovered["phase"] == "rolled_back"
    assert recovered["failure_category"] == "restore_interrupted"
    assert recovered["rollback_status"] == "not_required"
    assert not stage.exists()
    assert lite_restore_transaction.guard_status()["unresolved"] is False


def test_restore_staging_cleanup_retries_transient_termux_removal_failure(tmp_path, monkeypatch):
    from api_fastapi.services import lite_backup

    stage = lite_backup.backup_layout().staging / "restore-transient-cleanup"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "partial-artifact").write_text("bounded test artifact", encoding="utf-8")
    original_rmtree = lite_backup.shutil.rmtree
    calls = 0

    def transient_failure(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated Termux handle release")
        return original_rmtree(path)

    monkeypatch.setattr(lite_backup.shutil, "rmtree", transient_failure)
    result = lite_backup._cleanup_restore_staging(stage)

    assert result["status"] == "removed"
    assert result["attempts"] == 2
    assert calls == 2
    assert not stage.exists()


def test_restore_command_redelivery_reuses_terminal_result(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import lite_backup

    backup_id = "terminal-redelivery-backup"
    lite_backup.create_backup({"command_id": backup_id, "reason": "terminal replay test"})
    assert lite_backup.verify_backup(backup_id)["status"] == "verified"
    preview = lite_backup.create_restore_preview(backup_id, reason="terminal replay test")
    restore_id = "terminal-redelivery-restore"
    terminal = {
        "status": "failed_with_rollback",
        "restore_id": restore_id,
        "backup_id": backup_id,
        "preview_id": preview["preview_id"],
        "summary": "Restore failed before active state mutation and was recorded.",
    }
    lite_backup._record_restore_run(restore_id, terminal)

    monkeypatch.setattr(
        lite_backup,
        "_restic_snapshot_exists",
        lambda *_args, **_kwargs: pytest.fail("terminal restore replay must not rerun restic"),
    )
    replay = lite_backup.apply_restore(
        {
            "command_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview["preview_id"],
            "confirm": True,
        }
    )

    assert replay == terminal


def test_restore_command_redelivery_reuses_terminal_journal_result(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi.services import (
        lite_backup,
        lite_database_recovery,
        lite_restore_transaction,
    )

    backup_id = "terminal-journal-redelivery-backup"
    lite_backup.create_backup({"command_id": backup_id, "reason": "terminal journal replay test"})
    assert lite_backup.verify_backup(backup_id)["status"] == "verified"
    preview = lite_backup.create_restore_preview(backup_id, reason="terminal journal replay test")
    restore_id = "terminal-journal-redelivery-restore"
    lite_restore_transaction.create_journal(
        restore_id=restore_id,
        backup_id=backup_id,
        preview_id=preview["preview_id"],
        target_names=["state/catalog.json"],
        preflight=True,
        snapshot_id=preview["snapshot_id"],
        manifest_checksum=preview["backup_manifest_checksum"],
        staging_key=f"restore-{restore_id}",
    )
    lite_restore_transaction.update_journal(
        restore_id,
        phase="rolled_back",
        status="failed",
        terminal_status="rolled_back",
        summary="Restore was interrupted while staging.",
        failure_category="restore_interrupted",
        rollback={"status": "not_required", "attempted": False},
    )
    assert lite_database_recovery.get_database_restore_run(restore_id)["phase"] == "rolled_back"

    monkeypatch.setattr(
        lite_backup,
        "_restic_snapshot_exists",
        lambda *_args, **_kwargs: pytest.fail("terminal journal replay must not rerun restic"),
    )
    replay = lite_backup.apply_restore(
        {
            "command_id": restore_id,
            "backup_id": backup_id,
            "preview_id": preview["preview_id"],
            "confirm": True,
        }
    )

    assert replay["status"] == "failed_with_rollback"
    assert replay["idempotent_replay"] is True
    assert replay["database_restore"]["phase"] == "rolled_back"


def test_lite_app_backup_and_restore_preview_are_preview_only(tmp_path, monkeypatch):
    _install_fake_restic(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_app_backup, lite_app_backup_targets

    monkeypatch.setattr(
        lite_app_backup_targets,
        "backup_target_summary",
        lambda _app_id="photoprism": {
            "ready": False,
            "summary": "Join a storage device to save app backups elsewhere.",
            "target_label": None,
            "targets": [],
        },
    )

    deps.core.write_json_file(
        deps.settings().state_dir / "catalog.json",
        {"apps": [{"id": "photoprism", "status": "ready"}]},
    )
    deps.core.write_json_file(
        deps.settings().state_dir / "fleet_agents.json",
        {"agents": {"server": {"status": "healthy"}}},
    )

    command = lite_app_backup.app_backup_command("photoprism", mode="config_only", reason="unit-test app backup")
    backup = lite_app_backup.create_app_backup(command)
    assert backup["status"] in {"succeeded", "review"}
    assert backup["app_id"] == "photoprism"
    assert backup["backup_id"].startswith("app-backup-photoprism-")
    assert backup["media_included"] is False
    assert backup["restore_apply_supported"] is False

    status = lite_app_backup.app_backup_status("photoprism")
    assert status["latest_backup"]["backup_id"] == backup["backup_id"]
    assert status["restore_apply_supported"] is False
    assert status["actions"]["preview_restore"]["enabled"] is True
    assert status["actions"]["backup_to_storage_device"]["enabled"] is False

    preview_command = lite_app_backup.app_restore_preview_command(
        "photoprism",
        backup_id="latest",
        reason="unit-test preview",
    )
    preview = lite_app_backup.create_app_restore_preview(preview_command)
    assert preview["status"] == "ready"
    assert preview["preview_only"] is True
    assert preview["restore_allowed"] is False
    assert preview["restore_apply_supported"] is False
    assert preview["destructive"] is False
    assert any(item["id"] == "app_config" for item in preview["would_restore"])
    assert any(item["id"] == "original_media" for item in preview["would_preserve"])
    assert "/data/data" not in json.dumps(preview)
    assert "restic-password" not in json.dumps(preview).lower()
