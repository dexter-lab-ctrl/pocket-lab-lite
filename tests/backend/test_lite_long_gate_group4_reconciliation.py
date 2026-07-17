from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group4.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group4_reconciliation", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def context(tool, tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    run = tmp_path / "run"
    run.mkdir()
    return tool.g2.Context(
        repo_root=ROOT,
        run_dir=run,
        run_id="pocketlab-long-gates-group4-test",
        gate_id="wal-pressure",
        state_dir=state,
        db_path=state / "pocketlab-lite.sqlite3",
        proxy_base_url="http://127.0.0.1:9",
        direct_base_url="http://127.0.0.1:9",
        connect_timeout=0.1,
        http_timeout=0.1,
        report_limit_bytes=1024 * 1024,
        resume=False,
    )


def test_bounded_parity_reconciliation_retries_mismatch_then_matches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = load_tool()
    ctx = context(tool, tmp_path)
    samples = iter([
        {"quick_check": "ok", "matched": False, "mismatch_fields": ["status"]},
        {"quick_check": "ok", "matched": True, "mismatch_fields": []},
    ])
    monkeypatch.setattr(tool.g2, "run_sqlite_tools", lambda *_args: next(samples))
    monkeypatch.setattr(tool.time, "sleep", lambda _seconds: None)

    result = tool.bounded_parity_reconciliation(ctx, timeout_seconds=5, interval_seconds=0.1)

    assert result["quick_check"] == "ok"
    assert result["parity_matched"] is True
    assert result["reconciliation_attempts"] == 2
    assert result["reconciliation_status"] == "matched"


@pytest.mark.parametrize(
    "payload",
    [
        {"quick_check": "ok", "matched": True, "mismatch_fields": []},
        {"quick_check": "ok", "parity_matched": True, "mismatch_fields": []},
    ],
)
def test_bounded_parity_reconciliation_accepts_supported_match_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, object],
):
    tool = load_tool()
    ctx = context(tool, tmp_path)
    monkeypatch.setattr(tool.g2, "run_sqlite_tools", lambda *_args: dict(payload))

    result = tool.bounded_parity_reconciliation(ctx, timeout_seconds=0)

    assert result["quick_check"] == "ok"
    assert result["parity_matched"] is True
    assert result["reconciliation_status"] == "matched"


def test_bounded_parity_reconciliation_fails_fast_on_quick_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = load_tool()
    ctx = context(tool, tmp_path)
    calls = 0

    def unhealthy(*_args):
        nonlocal calls
        calls += 1
        return {"quick_check": "database disk image is malformed", "parity_matched": False}

    monkeypatch.setattr(tool.g2, "run_sqlite_tools", unhealthy)
    result = tool.bounded_parity_reconciliation(ctx, timeout_seconds=30)

    assert calls == 1
    assert result["reconciliation_status"] == "sqlite_unhealthy"


def test_high_free_space_threshold_uses_percentage_guard():
    tool = load_tool()
    free_bytes = 142_895_362_048
    free_percent = 59.712

    floor_bytes, floor_percent = tool.low_storage_test_thresholds(
        free_bytes=free_bytes,
        free_percent=free_percent,
        configured_floor_percent=3.0,
    )

    assert floor_bytes == 16 * 1024 * 1024 * 1024
    assert floor_bytes < free_bytes
    assert floor_percent > free_percent
    assert floor_percent == pytest.approx(60.212)


def test_post_terminal_reconciliation_fail_closed_cases():
    tool = load_tool()
    terminal_at = "2026-07-17T06:50:00Z"
    base = {
        "backend_run_id": "run-1",
        "backend_revision": "rev-2",
        "backend_reconciliation_count": 4,
        "captured_at": "2026-07-17T06:50:01Z",
    }

    assert not tool.is_post_terminal_reconciliation(
        {"captured_at": "2026-07-17T06:50:01Z"},
        run_id="run-1",
        baseline_reconciliations=3,
        terminal_at=terminal_at,
    )
    assert not tool.is_post_terminal_reconciliation(
        {**base, "backend_run_id": "run-2"},
        run_id="run-1",
        baseline_reconciliations=3,
        terminal_at=terminal_at,
    )
    assert not tool.is_post_terminal_reconciliation(
        {**base, "captured_at": "2026-07-17T06:49:59Z"},
        run_id="run-1",
        baseline_reconciliations=3,
        terminal_at=terminal_at,
    )
    assert tool.is_post_terminal_reconciliation(
        base,
        run_id="run-1",
        baseline_reconciliations=3,
        terminal_at=terminal_at,
    )


def test_process_eviction_requires_new_session_and_visibility_only_does_not_reconcile():
    tool = load_tool()
    reports = [
        {"frontend_session_id": "session-a", "visibility_state": "hidden", "backend_reconciliation_count": 0},
        {"frontend_session_id": "session-b", "visibility_state": "visible", "backend_reconciliation_count": 1},
    ]
    result = tool.analyze_frontend_reports(reports)
    assert result["process_recreated"] is True
    assert result["backend_state_reconciled"] is True

    visibility_only = tool.analyze_frontend_reports([
        {"frontend_session_id": "session-a", "visibility_state": "hidden"},
        {"frontend_session_id": "session-a", "visibility_state": "visible"},
    ])
    assert visibility_only["process_recreated"] is False
    assert visibility_only["backend_state_reconciled"] is False


def test_group4_source_preserves_fail_closed_final_checks():
    source = TOOL.read_text(encoding="utf-8")
    assert 'failures.append("final_sqlite_quick_check")' in source
    assert 'failures.append("final_parity_mismatch")' in source
    assert 'failures.append("backend_terminal_state_missing")' in source
    assert 'failures.append("frontend_post_terminal_reconciliation_missing")' in source
    assert "Low-storage guard did not reject before durable run creation." in source
