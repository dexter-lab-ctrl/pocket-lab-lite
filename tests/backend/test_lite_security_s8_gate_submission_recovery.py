from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


class FakeApi:
    timeout = 10.0

    def __init__(self, *, timeout_on_post: bool = True) -> None:
        self.timeout_on_post = timeout_on_post
        self.post_calls = 0
        self.progress_reads = 0

    def get(self, path: str):
        if path == "/api/lite/security/summary":
            return {"history": []}
        assert path == "/api/lite/security/progress"
        self.progress_reads += 1
        if self.progress_reads == 1:
            return {
                "active_scan": False,
                "run_id": "old-run",
                "requested_at_epoch_ms": 1000,
                "profile": "quick",
                "status": "succeeded",
            }
        if self.progress_reads == 2:
            return {
                "active_scan": True,
                "run_id": "new-run",
                "requested_at_epoch_ms": 9_999_999_999_999,
                "profile": "quick",
                "status": "running",
            }
        return {
            "active_scan": False,
            "run_id": "new-run",
            "requested_at_epoch_ms": 9_999_999_999_999,
            "profile": "quick",
            "status": "succeeded",
            "percent": 100,
        }

    def post(self, path: str, payload: dict):
        assert path == "/api/lite/security/check"
        assert payload == {"profile": "quick"}
        self.post_calls += 1
        if self.timeout_on_post:
            raise long_gate_s8.ApiTransportError("POST", path, "TimeoutError")
        return {"run_id": "new-run"}


def test_quick_scan_adopts_new_run_after_submission_timeout(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = FakeApi(timeout_on_post=True)

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result == {
        "run_id": "new-run",
        "status": "succeeded",
        "percent": 100,
        "submission_recovered": True,
    }
    assert api.post_calls == 1


def test_quick_scan_keeps_normal_submission_path(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = FakeApi(timeout_on_post=False)

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result["run_id"] == "new-run"
    assert result["submission_recovered"] is False
    assert api.post_calls == 1


def test_quick_scan_waits_for_existing_scan_to_clear(monkeypatch):
    api = FakeApi(timeout_on_post=False)
    reads = {"count": 0}

    def active_then_idle(path: str):
        if path == "/api/lite/security/summary":
            if api.post_calls:
                return {
                    "last_run": {
                        "run_id": "new-run",
                        "requested_at_epoch_ms": 9_999_999_999_999,
                        "scan_profile": "quick",
                        "status": "succeeded",
                        "percent": 100,
                    },
                    "history": [],
                }
            return {"history": []}
        if api.post_calls:
            return {
                "active_scan": False,
                "run_id": "new-run",
                "requested_at_epoch_ms": 9_999_999_999_999,
                "profile": "quick",
                "status": "succeeded",
                "percent": 100,
            }
        reads["count"] += 1
        if reads["count"] < 3:
            return {"active_scan": True, "run_id": "existing", "profile": "quick", "status": "running"}
        return {"active_scan": False, "run_id": "existing", "profile": "quick", "status": "succeeded"}

    api.get = active_then_idle
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result["run_id"] == "new-run"
    assert api.post_calls == 1


def test_quick_scan_fails_closed_when_active_scan_never_clears(monkeypatch):
    api = FakeApi(timeout_on_post=False)

    def active(path: str):
        if path == "/api/lite/security/summary":
            return {"history": []}
        return {"active_scan": True, "run_id": "existing", "profile": "quick", "status": "running"}

    api.get = active
    monkeypatch.setenv("POCKETLAB_S8_GATE_SECURITY_IDLE_TIMEOUT", "15")
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    try:
        long_gate_s8.run_quick_scan(api, timeout=0.01)
    except long_gate_s8.GateError as exc:
        assert "Security scan idle precondition" in str(exc)
    else:
        raise AssertionError("expected GateError")

    assert api.post_calls == 0


class StaleProgressApi:
    timeout = 10.0

    def __init__(self) -> None:
        self.summary_reads = 0

    def get(self, path: str):
        if path == "/api/lite/security/progress":
            return {
                "active_scan": False,
                "run_id": "old-run",
                "requested_at_epoch_ms": 1000,
                "profile": "quick",
                "status": "succeeded",
            }
        assert path == "/api/lite/security/summary"
        self.summary_reads += 1
        status = "running" if self.summary_reads == 1 else "succeeded"
        return {
            "last_run": {
                "run_id": "new-run",
                "requested_at_epoch_ms": 9_999_999_999_999,
                "scan_profile": "quick",
                "status": status,
                "percent": 100 if status == "succeeded" else 20,
            },
            "history": [],
        }

    def post(self, path: str, payload: dict):
        raise long_gate_s8.ApiTransportError("POST", path, "TimeoutError")


def test_quick_scan_recovers_from_summary_when_progress_is_stale(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = StaleProgressApi()

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result["run_id"] == "new-run"
    assert result["status"] == "succeeded"
    assert result["submission_recovered"] is True


def test_state_file_hashes_include_run_projections(tmp_path):
    state_dir = tmp_path / "state"
    security = state_dir / "security"
    runs = security / "runs"
    compact = security / "compact"
    runs.mkdir(parents=True)
    compact.mkdir(parents=True)
    (security / "security_state.json").write_text('{"state":1}\n', encoding="utf-8")
    (runs / "run-a.json").write_text('{"run_id":"run-a"}\n', encoding="utf-8")
    (compact / "security_summary.json").write_text('{"status":"healthy"}\n', encoding="utf-8")

    hashes = long_gate_s8.state_file_hashes(state_dir)

    assert set(hashes) == {
        "security/security_state.json",
        "security/runs/run-a.json",
        "security/compact/security_summary.json",
    }


def test_failed_restore_expected_snapshot_is_captured_after_fault_restart():
    source = MODULE_PATH.read_text(encoding="utf-8")
    gate_start = source.index("def failed_restore_gate()")
    gate_end = source.index('record("gate-6-failed-restore-rollback"', gate_start)
    gate_source = source[gate_start:gate_end]

    configure_at = gate_source.index('configure_worker_fault("after_sqlite_promotion")')
    settle_at = gate_source.index("settled_progress = wait_security_idle", configure_at)
    database_at = gate_source.index("pre_database = database_state(db_path)", settle_at)
    files_at = gate_source.index("pre_files = state_file_hashes(state_dir)", database_at)
    submit_at = gate_source.index("submitted_restore = api.post", files_at)

    assert configure_at < settle_at < database_at < files_at < submit_at
