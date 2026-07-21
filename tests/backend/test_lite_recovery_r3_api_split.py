from __future__ import annotations

import os
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_recovery_r3_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ROOT", str(tmp_path / "lite-backups"))
    yield


def test_recovery_summary_is_compact_conditional_and_sanitized(monkeypatch):
    from api_fastapi.routers import lite

    monkeypatch.setattr(lite.lite_status, "lite_recovery_summary", lambda: {
        "view_model": "recovery-summary-r3-v1",
        "status": "healthy",
        "summary": "Recovery Ready",
        "last_backup": {
            "backup_id": "backup-a",
            "created_at": "2026-07-21T10:00:00Z",
            "verification_status": "verified",
        },
        "recent_activity": [{
            "id": "backup-a",
            "kind": "backup",
            "status": "verified",
            "summary": "Backup verified",
            "occurred_at": "2026-07-21T10:00:00Z",
        }],
        "updated_at": "2026-07-21T10:00:00Z",
        "sanitized": True,
    })
    monkeypatch.setattr(lite.lite_database_recovery, "database_recovery_summary", lambda: {
        "view_model": "database-recovery-summary-r3-v1",
        "status": "healthy",
        "summary": "Database protection is ready.",
        "latest_backup": {"backup_id": "db-a", "verification_status": "verified"},
        "updated_at": "2026-07-21T10:00:00Z",
        "sanitized": True,
    })
    monkeypatch.setattr(lite.lite_security_maintenance, "maintenance_state", lambda: {"active": False, "state": "ready"})

    response = client().get("/api/lite/recovery/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_model"] == "recovery-summary-r3-v1"
    assert payload["last_backup"]["backup_id"] == "backup-a"
    assert payload["database_protection"]["latest_backup"]["backup_id"] == "db-a"
    assert "backup_history" not in payload
    assert "app_backups" not in payload
    assert "backup_targets" not in payload
    assert response.headers["cache-control"] == "no-cache"
    etag = response.headers["etag"]

    not_modified = client().get("/api/lite/recovery/summary", headers={"If-None-Match": etag})
    assert not_modified.status_code == 304


def test_recovery_details_preserves_existing_full_contract(monkeypatch):
    from api_fastapi.routers import lite

    monkeypatch.setattr(lite.lite_status, "lite_recovery_details", lambda: {
        "status": "healthy",
        "summary": "Recovery Ready",
        "backup_history": [{"backup_id": "backup-a"}],
    })
    monkeypatch.setattr(lite.lite_app_profiles, "app_backup_profiles", lambda: {"apps": [{"app_id": "photoprism"}]})
    monkeypatch.setattr(lite.lite_app_lifecycle, "app_lifecycle_profiles", lambda: {"apps": [{"app_id": "photoprism"}]})
    monkeypatch.setattr(lite.lite_app_backup_targets, "backup_targets", lambda: {"targets": [{"device_id": "phone-2"}]})
    monkeypatch.setattr(lite.lite_database_recovery, "database_recovery_status", lambda: {"status": "healthy", "backup_history": []})
    monkeypatch.setattr(lite.lite_security_maintenance, "maintenance_state", lambda: {"active": False, "state": "ready"})

    response = client().get("/api/lite/recovery/details")
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_model"] == "recovery-details-r3-v1"
    assert payload["app_backups"][0]["app_id"] == "photoprism"
    assert payload["backup_targets"][0]["device_id"] == "phone-2"
    assert payload["database_protection"]["status"] == "healthy"


def test_recovery_backup_history_uses_bounded_cursor_pages(tmp_path):
    from api_fastapi.services import lite_backup_manifest

    for index in range(1, 4):
        backup_id = f"backup-{index}"
        lite_backup_manifest.write_manifest({
            "backup_id": backup_id,
            "created_at": f"2026-07-21T10:0{index}:00Z",
            "engine": "restic",
            "verification_status": "verified",
            "included_files": [],
        })
        stamp = 1_784_600_000 + index
        os.utime(lite_backup_manifest.manifest_path(backup_id), (stamp, stamp))

    first = client().get("/api/lite/recovery/backups?limit=1")
    assert first.status_code == 200
    first_payload = first.json()
    assert [item["backup_id"] for item in first_payload["backups"]] == ["backup-3"]
    assert first_payload["has_more"] is True
    assert first_payload["next_cursor"]
    assert first_payload["next_cursor"] != "backup-3"

    second = client().get(f"/api/lite/recovery/backups?limit=1&cursor={first_payload['next_cursor']}")
    assert second.status_code == 200
    second_payload = second.json()
    assert [item["backup_id"] for item in second_payload["backups"]] == ["backup-2"]
    assert second_payload["next_cursor"]
    assert set(item["backup_id"] for item in first_payload["backups"]).isdisjoint(
        item["backup_id"] for item in second_payload["backups"]
    )

    invalid = client().get("/api/lite/recovery/backups?limit=1&cursor=missing-backup")
    assert invalid.status_code == 400
    assert invalid.json()["status"] == "invalid_cursor"


def test_recovery_details_keeps_only_recent_inline_history(tmp_path):
    from api_fastapi.services import lite_backup, lite_backup_manifest

    for index in range(1, 7):
        backup_id = f"history-{index}"
        lite_backup_manifest.write_manifest({
            "backup_id": backup_id,
            "created_at": f"2026-07-21T11:0{index}:00Z",
            "engine": "restic",
            "verification_status": "verified",
            "included_files": [],
        })
        stamp = 1_784_700_000 + index
        os.utime(lite_backup_manifest.manifest_path(backup_id), (stamp, stamp))

    payload = lite_backup.recovery_details()
    assert len(payload["backup_history"]) == 3
    assert [item["backup_id"] for item in payload["backup_history"]] == ["history-6", "history-5", "history-4"]


def test_recovery_summary_keeps_latest_backup_and_exposes_active_operation(monkeypatch):
    from api_fastapi.services import lite_backup

    monkeypatch.setattr(lite_backup, "repository_readiness", lambda: {
        "status": "healthy",
        "summary": "Recovery Ready",
        "restic_available": True,
        "repository": {"type": "local", "engine": "restic", "encrypted": True, "ready": True, "location": "This device"},
    })
    monkeypatch.setattr(lite_backup.lite_backup_manifest, "latest_manifest", lambda: {
        "backup_id": "backup-verified",
        "created_at": "2026-07-21T09:00:00Z",
        "verification_status": "verified",
        "included_files": [],
    })
    monkeypatch.setattr(lite_backup, "pending_backup", lambda: {
        "backup_id": "backup-running",
        "status": "running",
        "requested_at": "2026-07-21T10:00:00Z",
        "summary": "Saving a protected copy.",
    })
    monkeypatch.setattr(lite_backup, "_read_backup_state", lambda: {"updated_at": "2026-07-21T10:00:00Z"})

    payload = lite_backup.recovery_summary()
    assert payload["last_backup"]["backup_id"] == "backup-verified"
    assert payload["current_operation"]["backup_id"] == "backup-running"
    assert payload["status"] == "running"
    assert payload["live"] is True
    assert payload["recommended_action"] == "manage_recovery"


def test_database_recovery_summary_excludes_history_and_deep_restore_details(monkeypatch):
    from api_fastapi.services import lite_database_recovery

    monkeypatch.setattr(lite_database_recovery, "_database_recovery_base", lambda backup_limit: {
        "status": "healthy",
        "summary": "Database protection is ready.",
        "latest_backup": {
            "backup_id": "db-a",
            "verification_status": "verified",
            "restore_preview": {"changes": [1, 2, 3]},
            "verification": {"sha256": "hidden"},
        },
        "backup_history": [{"backup_id": "db-a"}],
        "latest_restore_preview": {"preview_id": "preview-a", "status": "ready", "changes": [1, 2]},
        "last_restore": {"restore_id": "restore-a", "status": "rolled_back", "events": [{"phase": "restore"}]},
        "active_restore": {"restore_id": "restore-b", "phase": "validating", "events": [{"phase": "restore"}]},
        "restore_guard": {"unresolved": False, "internal_path": "/private"},
        "maintenance": {"active": False, "raw": {"secret": True}},
        "wal": {"journal_mode": "wal", "wal_bytes": 0, "raw": "technical"},
        "rollback_available": True,
        "updated_at": "2026-07-21T10:00:00Z",
        "sanitized": True,
    })

    payload = lite_database_recovery.database_recovery_summary()
    assert payload["view_model"] == "database-recovery-summary-r3-v1"
    assert "backup_history" not in payload
    assert "restore_preview" not in payload["latest_backup"]
    assert "verification" not in payload["latest_backup"]
    assert "changes" not in payload["latest_restore_preview"]
    assert "events" not in payload["last_restore"]
    assert "events" not in payload["active_restore"]
    assert "internal_path" not in payload["restore_guard"]
    assert "raw" not in payload["maintenance"]
    assert "raw" not in payload["wal"]


def test_recovery_summary_payload_stays_within_mobile_key_and_size_budget():
    response = client().get("/api/lite/recovery/summary")
    assert response.status_code == 200
    payload = response.json()
    assert len(response.content) < 5_000
    assert len(payload) <= 20
    assert "backup_history" not in payload
    assert "app_backups" not in payload
    assert "backup_targets" not in payload
    assert "what_will_be_backed_up" not in payload
    assert "what_will_not_be_backed_up" not in payload
