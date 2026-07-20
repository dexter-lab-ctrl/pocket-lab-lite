from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8_restore_fault_hygiene", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


def test_sanitized_restore_result_exposes_only_bounded_diagnostics():
    result = long_gate_s8.sanitized_restore_result(
        {
            "restore_id": "restore-1",
            "backup_id": "backup-1",
            "status": "failed",
            "error_type": "RuntimeError",
            "summary": "Database restore failed.",
            "rollback": {"attempted": True, "status": "completed", "secret": "no"},
            "token": "must-not-leak",
        }
    )

    assert result["rollback_status"] == "completed"
    assert result["rollback_attempted"] is True
    assert result["sanitized"] is True
    assert "token" not in result
    assert "secret" not in result


def test_wait_restore_preserves_sanitized_failure_detail(monkeypatch):
    monkeypatch.setattr(
        long_gate_s8,
        "poll",
        lambda *args, **kwargs: {
            "restore_id": "restore-2",
            "status": "failed",
            "phase": "rolled_back",
            "rollback_status": "rolled_back",
            "api_worker_restart_allowed": True,
        },
    )

    try:
        long_gate_s8.wait_restore(SimpleNamespace(), "restore-2", 1, "completed")
    except long_gate_s8.RestoreExpectationError as exc:
        assert exc.detail["restore_id"] == "restore-2"
        assert exc.detail["phase"] == "rolled_back"
        assert exc.detail["api_worker_restart_allowed"] is True
    else:
        raise AssertionError("expected RestoreExpectationError")


def test_worker_fault_environment_reads_only_sanitized_pm2_fields(monkeypatch):
    payload = [
        {
            "name": "pocket-worker",
            "pm2_env": {
                "env": {
                    "POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS": "1",
                    "POCKETLAB_LITE_S8_FAULT_POINT": "after_sqlite_promotion",
                    "POCKETLAB_API_TOKEN": "must-not-leak",
                }
            },
        }
    ]
    monkeypatch.setattr(
        long_gate_s8.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )

    state = long_gate_s8.worker_fault_environment()

    assert state == {
        "checked": True,
        "enabled": True,
        "point": "after_sqlite_promotion",
        "sanitized": True,
    }


def test_ensure_worker_fault_disabled_restarts_only_for_stale_fault(monkeypatch):
    states = iter(
        [
            {"checked": True, "enabled": True, "point": "after_sqlite_promotion"},
            {"checked": True, "enabled": False, "point": None},
        ]
    )
    calls: list[object] = []
    monkeypatch.setattr(long_gate_s8, "worker_fault_environment", lambda: next(states))
    monkeypatch.setattr(long_gate_s8, "configure_worker_fault", lambda point: calls.append(point))

    result = long_gate_s8.ensure_worker_fault_disabled()

    assert calls == [None]
    assert result["stale_fault_detected"] is True
    assert result["worker_restarted"] is True
    assert result["fault_disabled"] is True
