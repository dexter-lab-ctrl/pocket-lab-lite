from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "dual")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACCEPTED_STALE_SECONDS", "30")

    from api_fastapi import deps
    from api_fastapi.services import lite_security

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    lite_security.invalidate_security_read_caches()
    return state


def test_stale_accepted_run_compare_and_set_clears_active_key(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-stale-accepted",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    accepted = repo.mark_accepted(
        "security-stale-accepted",
        accepted_at="2020-01-01T00:00:01Z",
        summary="Queued",
    )

    stale = repo.list_stale_accepted_runs(
        now="2020-01-01T00:03:00Z", stale_seconds=30
    )
    assert [item["run_id"] for item in stale] == ["security-stale-accepted"]

    failed = repo.fail_stale_accepted_run(
        "security-stale-accepted",
        expected_updated_at_epoch_ms=accepted["updated_at_epoch_ms"],
        completed_at="2020-01-01T00:03:01Z",
    )
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["active_key"] is None
    assert failed["failure_code"] == "worker_start_timeout"
    assert repo.get_active_scan() is None

    retry = repo.reserve_scan(
        run_id="security-stale-retry",
        profile="quick",
        requested_at="2020-01-01T00:03:02Z",
    )
    assert retry.reserved is True


def test_stale_accepted_recovery_projects_sanitized_evidence(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-stale-project",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_accepted(
        "security-stale-project",
        accepted_at="2020-01-01T00:00:01Z",
        summary="Queued",
    )

    recovered = lite_security.recover_stale_accepted_runs(stale_seconds=30)
    assert recovered == [
        {
            "run_id": "security-stale-project",
            "profile": "quick",
            "status": "failed",
            "failure_code": "worker_start_timeout",
        }
    ]
    stored = repo.get_run("security-stale-project")
    assert stored["status"] == "failed"
    assert stored["active_key"] is None
    assert any(
        item["relative_path"].endswith("worker-start-recovery.json")
        for item in repo.list_evidence_refs("security-stale-project")
    )
    projected = lite_security.read_run("security-stale-project")
    assert projected["status"] == "failed"
    assert "token" not in json.dumps(projected).lower()
    assert (state / "security" / "runs" / "security-stale-project.json").exists()


def _load_worker_module():
    path = Path(
        "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_worker_recovery_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_acks_redelivered_security_command_after_stale_run_terminalized(
    monkeypatch,
):
    ensure_runtime_path()
    worker = _load_worker_module()
    from api_fastapi.services import lite_security

    monkeypatch.setattr(lite_security, "security_run_is_terminal", lambda _run_id: True)

    class FakeBus:
        def __init__(self):
            self.acked = 0

        def delivery_attempt(self, _msg):
            return 2

        async def ack_message(self, _msg):
            self.acked += 1

    fake_bus = FakeBus()
    monkeypatch.setattr(worker, "BUS", fake_bus)

    published = []

    async def fake_publish(subject, event_type, data, *, trace_id=None):
        published.append((subject, event_type, data, trace_id))

    async def should_not_execute(_subject, _command):
        raise AssertionError("terminal command must not execute")

    monkeypatch.setattr(worker, "publish", fake_publish)
    monkeypatch.setattr(worker, "execute_domain_command", should_not_execute)

    class Message:
        subject = "pocketlab.commands.lite.security.scan"
        data = json.dumps(
            {
                "run_id": "security-terminal-redelivery",
                "command_id": "security-terminal-redelivery",
            }
        ).encode()

    asyncio.run(worker.command_callback(Message()))

    assert fake_bus.acked == 1
    assert published[0][1] == "worker.ignored"
    assert published[0][2]["reason"] == "security run is already terminal"
