from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_s8_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("POCKETLAB_LITE_RESTORE_QUIESCE_SECONDS", "0")
    yield


def _repository():
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    return SecuritySQLiteRepository()


def _terminal_run(repo, run_id: str, *, completed_at: str, evidence_refs=None, profile="quick", app_id=None):
    repo.reserve_scan(run_id=run_id, profile=profile, app_id=app_id, requested_at=completed_at)
    repo.mark_running(run_id, started_at=completed_at)
    return repo.complete_run(
        run_id,
        completed_at=completed_at,
        score=99,
        summary="Completed",
        evidence_refs=evidence_refs or [],
    )


def _iso_days_ago(days: int, seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days, seconds=seconds)).isoformat().replace("+00:00", "Z")


def test_s8_migration_and_database_package_contract(tmp_path):
    from api_fastapi.db.migrations import apply_migrations, current_schema_version
    from api_fastapi.services import lite_database_recovery

    assert apply_migrations() == [1, 2, 3, 4]
    assert current_schema_version() == 4
    _terminal_run(_repository(), "security-s8-backup-a", completed_at=_iso_days_ago(2))
    result = lite_database_recovery.create_database_backup({"command_id": "db-backup-s8-a"})

    assert result["status"] == "verified"
    package = lite_database_recovery.database_backup_package("db-backup-s8-a")
    expected = {
        "manifest.json",
        "schema.json",
        "migrations.json",
        "hashes.json",
        "evidence-manifest.json",
        "restore-preview.json",
        "receipt.json",
    }
    assert expected.issubset({item.name for item in package.iterdir()})
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["verification"]["integrity_check"] == "ok"
    assert manifest["verification"]["quick_check"] == "ok"
    assert manifest["verification"]["migration_checksums_valid"] is True
    assert manifest["verification"]["missing_core_tables"] == []
    assert manifest["database_sha256"] == hashlib.sha256(
        (package / manifest["database_file"]).read_bytes()
    ).hexdigest()
    hashes = json.loads((package / "hashes.json").read_text(encoding="utf-8"))
    assert manifest["backup_sha256"] == hashes["backup_sha256"]
    assert manifest["database_file"] in hashes["artifact_sha256"]
    assert "password" not in json.dumps(result).lower()


def test_s8_backup_verification_fails_closed_on_hash_mismatch():
    from api_fastapi.services import lite_database_recovery

    _terminal_run(_repository(), "security-s8-hash-a", completed_at=_iso_days_ago(2))
    lite_database_recovery.create_database_backup({"command_id": "db-backup-s8-hash"})
    package = lite_database_recovery.database_backup_package("db-backup-s8-hash")
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    with (package / manifest["database_file"]).open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(RuntimeError, match="hash"):
        lite_database_recovery.verify_database_backup("db-backup-s8-hash")


def test_s8_database_recovery_rejects_path_traversal_identifiers():
    from api_fastapi.services import lite_database_recovery

    assert lite_database_recovery.get_database_backup("../../outside") is None
    assert lite_database_recovery.get_database_restore_preview("../preview") is None
    assert lite_database_recovery.get_database_restore_run("../restore") is None
    with pytest.raises(RuntimeError, match="not found"):
        lite_database_recovery.verify_database_backup("../../outside")


def test_s8_missing_manifest_and_invalid_migration_fail_closed():
    from api_fastapi.services import lite_database_recovery

    missing_package = lite_database_recovery.database_backup_package("db-backup-missing-manifest")
    missing_package.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="manifest"):
        lite_database_recovery.verify_database_backup("db-backup-missing-manifest")

    _terminal_run(_repository(), "security-s8-migration", completed_at=_iso_days_ago(2))
    lite_database_recovery.create_database_backup({"command_id": "db-backup-invalid-migration"})
    package = lite_database_recovery.database_backup_package("db-backup-invalid-migration")
    manifest_path = package / "manifest.json"
    hashes_path = package / "hashes.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database_file = package / manifest["database_file"]
    with sqlite3.connect(database_file) as conn:
        conn.execute("UPDATE schema_migrations SET checksum='invalid' WHERE version=4")
        conn.commit()
    validation = lite_database_recovery.validate_database_file(database_file)
    assert validation["valid"] is False
    assert validation["migration_checksums_valid"] is False

    hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    database_hash = hashlib.sha256(database_file.read_bytes()).hexdigest()
    hashes["database_sha256"] = database_hash
    hashes["artifact_sha256"][manifest["database_file"]] = database_hash
    hashes["backup_sha256"] = lite_database_recovery._package_fingerprint(
        hashes["artifact_sha256"]
    )
    hashes_path.write_text(json.dumps(hashes), encoding="utf-8")
    manifest["database_sha256"] = database_hash
    manifest["backup_sha256"] = hashes["backup_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="validation"):
        lite_database_recovery.verify_database_backup("db-backup-invalid-migration")


def test_s8_interrupted_backup_removes_incomplete_package(monkeypatch):
    from api_fastapi.services import lite_database_recovery

    _terminal_run(_repository(), "security-s8-interrupted", completed_at=_iso_days_ago(2))

    def fail_backup(destination, **_kwargs):
        Path(destination).write_bytes(b"incomplete")
        raise RuntimeError("injected backup interruption")

    monkeypatch.setattr(lite_database_recovery, "online_backup", fail_backup)
    with pytest.raises(RuntimeError, match="interruption"):
        lite_database_recovery.create_database_backup({"command_id": "db-backup-interrupted"})

    root = lite_database_recovery.database_backup_root()
    assert not lite_database_recovery.database_backup_package("db-backup-interrupted").exists()
    assert not any(item.name.startswith(".db-backup-interrupted.tmp-") for item in root.iterdir())


def test_s8_concurrent_database_backups_fail_safely(monkeypatch):
    from api_fastapi.services import lite_database_recovery

    _terminal_run(_repository(), "security-s8-concurrent", completed_at=_iso_days_ago(2))
    original_backup = lite_database_recovery.online_backup
    started = threading.Event()
    release = threading.Event()
    result: dict[str, object] = {}

    def blocked_backup(destination, **kwargs):
        started.set()
        assert release.wait(timeout=5)
        return original_backup(destination, **kwargs)

    monkeypatch.setattr(lite_database_recovery, "online_backup", blocked_backup)

    def first_backup():
        result.update(
            lite_database_recovery.create_database_backup(
                {"command_id": "db-backup-concurrent-a"}
            )
        )

    thread = threading.Thread(target=first_backup, daemon=True)
    thread.start()
    assert started.wait(timeout=5)
    with pytest.raises(RuntimeError, match="already running"):
        lite_database_recovery.create_database_backup(
            {"command_id": "db-backup-concurrent-b"}
        )
    release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert result["status"] == "verified"
    assert not lite_database_recovery.database_backup_package(
        "db-backup-concurrent-b"
    ).exists()


def test_s8_retention_is_bounded_preserves_protected_runs_and_never_deletes_evidence(monkeypatch):
    from api_fastapi import deps
    from api_fastapi.db.connection import database_path
    from api_fastapi.services import lite_security_maintenance

    repo = _repository()
    evidence_path = deps.settings().state_dir / "security" / "evidence" / "security-retain-00" / "summary.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"status":"safe"}\n', encoding="utf-8")
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    for index in range(25):
        refs = []
        if index == 0:
            refs = [{"relative_path": "summary.json", "sha256": evidence_sha, "size_bytes": evidence_path.stat().st_size}]
        _terminal_run(
            repo,
            f"security-retain-{index:02d}",
            completed_at=_iso_days_ago(200, seconds=index),
            evidence_refs=refs,
        )
    repo.reserve_scan(run_id="security-retain-active", profile="quick")
    repo.mark_running("security-retain-active")

    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_MAX_RUNS", "20")
    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_MIN_PER_PROFILE", "2")
    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_BATCH_SIZE", "10")
    before_bytes = evidence_path.read_bytes()
    with sqlite3.connect(database_path()) as conn:
        before_count = conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0]

    dry_run = lite_security_maintenance.run_retention(dry_run=True, max_batches=1)
    assert dry_run["runs_deleted"] == 0
    with sqlite3.connect(database_path()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0] == before_count

    applied = lite_security_maintenance.run_retention(dry_run=False, max_batches=1)
    assert 0 < applied["runs_deleted"] <= 10
    assert applied["quick_check"] == "ok"
    assert applied["evidence_files_deleted"] == 0
    assert evidence_path.read_bytes() == before_bytes
    with sqlite3.connect(database_path()) as conn:
        active = conn.execute(
            "SELECT status FROM security_scan_runs WHERE run_id='security-retain-active'"
        ).fetchone()
        latest = conn.execute(
            "SELECT run_id FROM security_scan_runs WHERE status='succeeded' ORDER BY completed_at_epoch_ms DESC LIMIT 2"
        ).fetchall()
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        snapshot_orphans = conn.execute(
            """
            SELECT COUNT(*) FROM security_profile_snapshots AS snapshots
            LEFT JOIN security_scan_runs AS runs ON runs.run_id=snapshots.latest_run_id
            WHERE runs.run_id IS NULL
            """
        ).fetchone()[0]
    assert active and active[0] == "running"
    assert len(latest) == 2
    assert foreign_key_violations == []
    assert snapshot_orphans == 0
    snapshot = repo.get_profile_snapshot("quick")
    assert snapshot and snapshot["latest_run_id"]
    previous = repo.get_previous_comparable_run(latest[0][0], profile="quick")
    assert previous is not None
    assert applied["orphan_evidence"]["automatic_deletion_enabled"] is False


def test_s8_retention_keeps_twenty_per_profile_identity_and_recent_failures(monkeypatch):
    from api_fastapi.db.connection import database_path
    from api_fastapi.services import lite_security_maintenance

    repo = _repository()
    identities = (("quick", None), ("full", None), ("app", "photoprism"))
    for profile, app_id in identities:
        for index in range(21):
            _terminal_run(
                repo,
                f"security-{profile}-{app_id or 'local'}-{index:02d}",
                profile=profile,
                app_id=app_id,
                completed_at=_iso_days_ago(200, seconds=index),
            )
    recent_failed = "security-recent-failed"
    repo.reserve_scan(run_id=recent_failed, profile="quick", requested_at=_iso_days_ago(10))
    repo.mark_running(recent_failed, started_at=_iso_days_ago(10))
    repo.fail_run(
        recent_failed,
        failure_code="bounded_test_failure",
        failure_message="Sanitized failure",
        completed_at=_iso_days_ago(10),
    )

    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_MAX_RUNS", "20")
    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_MIN_PER_PROFILE", "20")
    monkeypatch.setenv("POCKETLAB_SECURITY_RETENTION_BATCH_SIZE", "50")
    result = lite_security_maintenance.run_retention(dry_run=False, max_batches=5)
    assert result["quick_check"] == "ok"

    with sqlite3.connect(database_path()) as conn:
        counts = {
            (row[0], row[1] or ""): row[2]
            for row in conn.execute(
                """
                SELECT profile, COALESCE(app_id, ''), COUNT(*)
                FROM security_scan_runs
                GROUP BY profile, COALESCE(app_id, '')
                """
            ).fetchall()
        }
        failed_exists = conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id=?",
            (recent_failed,),
        ).fetchone()[0]
    assert counts[("quick", "")] >= 20
    assert counts[("full", "")] >= 20
    assert counts[("app", "photoprism")] >= 20
    assert failed_exists == 1


def test_s8_wal_checkpoint_requires_owned_and_explicit_maintenance(monkeypatch):
    from api_fastapi.services import lite_security_maintenance

    _terminal_run(_repository(), "security-s8-wal", completed_at=_iso_days_ago(1))
    passive = lite_security_maintenance.run_wal_checkpoint(mode="PASSIVE")
    assert passive["status"] == "succeeded"
    assert passive["manual_wal_file_deletion"] is False

    operation_id = "wal-s8-controlled"
    lite_security_maintenance.enter_maintenance(
        operation_id=operation_id,
        kind="wal_maintenance",
        writers_stopped=True,
    )
    truncated = lite_security_maintenance.run_wal_checkpoint(
        mode="TRUNCATE", operation_id=operation_id, writers_stopped=True
    )
    assert truncated["status"] == "succeeded"
    assert truncated["checkpoint_mode"] == "truncate"
    assert truncated["manual_wal_file_deletion"] is False
    lite_security_maintenance.leave_maintenance(operation_id)


def test_s8_active_security_scan_blocks_restore():
    from api_fastapi.services import lite_database_recovery

    repo = _repository()
    _terminal_run(repo, "security-before-active-restore", completed_at=_iso_days_ago(3))
    lite_database_recovery.create_database_backup({"command_id": "db-backup-active-block"})
    repo.reserve_scan(run_id="security-active-restore-block", profile="quick")
    repo.mark_running("security-active-restore-block")
    preview = lite_database_recovery.create_database_restore_preview(
        "db-backup-active-block"
    )
    assert preview["status"] == "blocked"
    assert preview["restore_allowed"] is False
    with pytest.raises(RuntimeError, match="not ready"):
        lite_database_recovery.restore_database_backup(
            {
                "command_id": "db-restore-active-block",
                "backup_id": "db-backup-active-block",
                "preview_id": preview["preview_id"],
                "confirm": True,
            }
        )


def test_s8_restore_preview_is_non_destructive_and_restore_is_atomic_with_rollback():
    from api_fastapi.db.connection import database_path
    from api_fastapi.services import lite_database_recovery

    repo = _repository()
    _terminal_run(repo, "security-state-a", completed_at=_iso_days_ago(4))
    assert lite_database_recovery._refresh_security_projections()["status"] == "passed"
    lite_database_recovery.create_database_backup({"command_id": "db-backup-state-a"})

    _terminal_run(repo, "security-state-b", completed_at=_iso_days_ago(1))
    assert lite_database_recovery._refresh_security_projections()["status"] == "passed"
    before_preview_hash = hashlib.sha256(database_path().read_bytes()).hexdigest()
    preview = lite_database_recovery.create_database_restore_preview("db-backup-state-a")
    assert preview["status"] == "ready"
    assert preview["destructive_changes_applied"] is False
    assert hashlib.sha256(database_path().read_bytes()).hexdigest() == before_preview_hash

    with pytest.raises(RuntimeError, match="confirmation"):
        lite_database_recovery.restore_database_backup(
            {"backup_id": "db-backup-state-a", "preview_id": preview["preview_id"], "confirm": False}
        )

    result = lite_database_recovery.restore_database_backup(
        {
            "command_id": "db-restore-state-a",
            "backup_id": "db-backup-state-a",
            "preview_id": preview["preview_id"],
            "confirm": True,
        }
    )
    assert result["status"] == "completed"
    assert result["rollback_available"] is True
    assert result["verification"]["integrity_check"] == "ok"
    assert result["verification"]["quick_check"] == "ok"
    assert result["projection"]["status"] == "passed"
    assert result["parity"]["matched"] is True
    assert result["manual_wal_file_deletion"] is False
    with sqlite3.connect(database_path()) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id='security-state-a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id='security-state-b'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM security_database_backups WHERE backup_id='db-backup-state-a'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM security_database_restores WHERE restore_id='db-restore-state-a'"
        ).fetchone()[0] == 1



def test_s8_failed_post_replace_verification_rolls_back_prior_database(monkeypatch):
    from api_fastapi.db.connection import database_path
    from api_fastapi.services import lite_database_recovery

    repo = _repository()
    _terminal_run(repo, "security-fault-state-a", completed_at=_iso_days_ago(4))
    assert lite_database_recovery._refresh_security_projections()["status"] == "passed"
    lite_database_recovery.create_database_backup({"command_id": "db-backup-fault-a"})
    _terminal_run(repo, "security-fault-state-b", completed_at=_iso_days_ago(1))
    assert lite_database_recovery._refresh_security_projections()["status"] == "passed"
    preview = lite_database_recovery.create_database_restore_preview("db-backup-fault-a")

    monkeypatch.setenv("POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS", "1")
    with pytest.raises(RuntimeError, match="Automatic rollback"):
        lite_database_recovery.restore_database_backup(
            {
                "command_id": "db-restore-fault-a",
                "backup_id": "db-backup-fault-a",
                "preview_id": preview["preview_id"],
                "confirm": True,
                "gate_fail_after_replace": True,
            }
        )
    failed = lite_database_recovery.get_database_restore_run("db-restore-fault-a")
    assert failed["status"] == "failed"
    assert failed["rollback"]["status"] == "completed"
    with sqlite3.connect(database_path()) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM security_scan_runs WHERE run_id='security-fault-state-b'"
        ).fetchone()[0] == 1
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        restore_row = conn.execute(
            "SELECT state FROM security_database_restores WHERE restore_id='db-restore-fault-a'"
        ).fetchone()
    assert restore_row and restore_row[0] == "failed"


def test_s8_architecture_and_ui_contracts_are_preserved():
    router = Path("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text(encoding="utf-8")
    worker = Path("pocket-lab-final-structure/runtime/workers/pocketlab_worker.py").read_text(encoding="utf-8")
    supervisor = Path("pocket-lab-final-structure/runtime/supervisors/pocketlab_core_supervisor.py").read_text(encoding="utf-8")
    recovery_ui = Path("src/lite/LiteRecovery.jsx").read_text(encoding="utf-8")
    api = Path("src/lib/liteApi.js").read_text(encoding="utf-8")
    maintenance = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_maintenance.py"
    ).read_text(encoding="utf-8")

    for subject in (
        "pocketlab.commands.lite.database.backup",
        "pocketlab.commands.lite.database.restore",
        "pocketlab.commands.lite.maintenance.retention",
        "pocketlab.commands.lite.maintenance.checkpoint",
    ):
        assert subject in router
    assert "worker_command_allowed" in worker
    assert "maintenance-state.json" in supervisor
    assert "Back Up Pocket Lab" in recovery_ui
    assert "Preview restore" in recovery_ui
    assert "Restore Pocket Lab" in recovery_ui
    assert "databaseRecovery:" in api
    assert "unlink" not in maintenance.split("def run_wal_checkpoint", 1)[1].split("def maintenance_status", 1)[0]
    assert "sqlite3" not in recovery_ui
    assert "nats" not in recovery_ui.lower()
    assert "child_process" not in recovery_ui
    assert "exec(" not in recovery_ui
