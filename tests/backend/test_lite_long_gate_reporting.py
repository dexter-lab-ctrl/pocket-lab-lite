from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
JSON_TOOL = ROOT / "scripts/dev/lib/long_gate_json.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_json_reporting", JSON_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_run(tool, run_dir: Path, run_id: str, mode: str = "framework_self_test"):
    tool.init_run(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            repo_root=str(ROOT),
            gates="framework-self-test",
            mode=mode,
            resume=False,
        )
    )


def minimal_baseline(tool, run_id: str, phase: str):
    return {
        "schema_version": 1,
        "baseline_phase": phase,
        "run_id": run_id,
        "captured_at": tool.utc_now(),
        "status": "captured",
        "sanitized": True,
        "warnings": [],
        "missing_optional_tools": [],
        "failed_required_checks": [],
        "pocket_lab": {
            "security_store_mode": "sqlite",
            "database_health": {
                "reachable": True,
                "schema_current": True,
                "schema_version": 4,
                "expected_schema_version": 4,
                "migration_checksums_valid": True,
                "quick_check": "ok",
            },
            "json_sqlite_parity": {"matched": True, "mismatch_fields": []},
        },
        "process_state": {"processes": []},
    }


def test_baseline_schema_handles_optional_tool_absence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-baseline-schema"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    monkeypatch.setattr(
        tool,
        "database_and_parity",
        lambda *_args, **_kwargs: (
            {
                "security_store_mode": "unknown",
                "database_health": {"reachable": False, "quick_check": "unavailable"},
                "json_sqlite_parity": {"matched": None},
            },
            ["database unavailable"],
            [],
        ),
    )
    monkeypatch.setattr(tool, "pm2_processes", lambda: ([], ["pm2 unavailable"]))
    monkeypatch.setattr(tool, "fetch_json", lambda *_args, **_kwargs: {"ok": False, "sanitized": True})
    monkeypatch.setattr(tool, "scanner_inventory", lambda: [])
    output = run_dir / "baseline.json"
    rc = tool.capture_baseline(
        argparse.Namespace(
            repo_root=str(ROOT),
            run_dir=str(run_dir),
            run_id=run_id,
            state_dir=str(tmp_path / "state"),
            db_path=str(tmp_path / "state/db.sqlite3"),
            base_url="http://127.0.0.1:1",
            phase="before",
            output=str(output),
            require_live=False,
        )
    )
    assert rc == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "captured"
    assert payload["sanitized"] is True
    assert "pm2_process_inventory" in payload["missing_optional_tools"]
    assert payload["failed_required_checks"] == []


def test_required_baseline_failure_is_truthful(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-baseline-failure"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    monkeypatch.setattr(
        tool,
        "database_and_parity",
        lambda *_args, **_kwargs: (
            {"security_store_mode": "sqlite", "database_health": {}, "json_sqlite_parity": {}},
            [],
            ["sqlite_health"],
        ),
    )
    monkeypatch.setattr(tool, "pm2_processes", lambda: ([], []))
    monkeypatch.setattr(tool, "fetch_json", lambda *_args, **_kwargs: {"ok": True, "sanitized": True})
    monkeypatch.setattr(tool, "scanner_inventory", lambda: [])
    output = run_dir / "baseline.json"
    rc = tool.capture_baseline(
        argparse.Namespace(
            repo_root=str(ROOT),
            run_dir=str(run_dir),
            run_id=run_id,
            state_dir=str(tmp_path / "state"),
            db_path=str(tmp_path / "state/db.sqlite3"),
            base_url="http://127.0.0.1:1",
            phase="after",
            output=str(output),
            require_live=True,
        )
    )
    assert rc == 2
    payload = json.loads(output.read_text())
    assert payload["status"] == "failed"
    assert "sqlite_health" in payload["failed_required_checks"]


def test_failed_gate_requires_reason_and_framework_never_false_ready(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-no-false-ready"
    run_dir = tmp_path / run_id
    make_run(tool, run_dir, run_id)
    tool.atomic_write_json(run_dir / "baseline/before.json", minimal_baseline(tool, run_id, "before"))
    tool.atomic_write_json(run_dir / "baseline/after.json", minimal_baseline(tool, run_id, "after"))
    with pytest.raises(ValueError, match="non-empty failure reason"):
        tool.gate_result(
            argparse.Namespace(
                run_dir=str(run_dir),
                run_id=run_id,
                gate_id="framework-self-test",
                status="failed",
                phase5_gate=0,
                framework_validation=1,
                started_at="",
                duration_seconds="0",
                failure_reason="",
                failed_stage="",
                retryable=1,
                resume_safe=1,
                evidence_refs="",
            )
        )
    tool.gate_result(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            gate_id="framework-self-test",
            status="passed",
            phase5_gate=0,
            framework_validation=1,
            started_at="",
            duration_seconds="0",
            failure_reason="",
            failed_stage="",
            retryable=1,
            resume_safe=1,
            evidence_refs="",
        )
    )
    tool.atomic_write_json(
        run_dir / "invariants.json",
        {"schema_version": 1, "run_id": run_id, "required_failures": [], "checks": {}, "sanitized": True},
    )
    tool.atomic_write_json(
        run_dir / "sanitization.json",
        {"schema_version": 1, "run_id": run_id, "sanitized": True, "findings": []},
    )
    output = run_dir / "summary.json"
    assert tool.aggregate(argparse.Namespace(run_dir=str(run_dir), run_id=run_id, output=str(output))) == 0
    summary = json.loads(output.read_text())
    assert summary["status"] == "framework_validated"
    assert summary["real_phase5_gates_executed"] == 0
    assert summary["failure_reason"] == "No real Phase 5 gates were executed."


def test_sanitization_fails_closed_without_echoing_secret(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-sanitize-test"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "unsafe.json").write_text(
        '{"authorization":"Bearer definitely-secret-value"}\n', encoding="utf-8"
    )
    output = run_dir / "sanitization.json"
    assert tool.sanitization_scan(
        argparse.Namespace(run_dir=str(run_dir), run_id=run_id, output=str(output))
    ) == 2
    payload = json.loads(output.read_text())
    assert payload["sanitized"] is False
    assert payload["findings"]
    assert "definitely-secret-value" not in output.read_text()


def test_checksum_manifest_uses_relative_paths_and_excludes_itself(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-checksum-test"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    tool.atomic_write_json(run_dir / "manifest.json", {"sanitized": True})
    tool.atomic_write_json(run_dir / "summary.json", {"sanitized": True})
    output = run_dir / "checksums.json"
    assert tool.checksum_manifest(
        argparse.Namespace(run_dir=str(run_dir), run_id=run_id, output=str(output))
    ) == 0
    payload = json.loads(output.read_text())
    paths = [item["path"] for item in payload["files"]]
    assert paths == ["manifest.json", "summary.json"]
    assert all(not Path(path).is_absolute() for path in paths)
    assert all(len(item["sha256"]) == 64 for item in payload["files"])


def test_invariant_evaluator_marks_unsupported_checks_not_evaluated(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-invariants-test"
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    tool.atomic_write_json(before, minimal_baseline(tool, run_id, "before"))
    tool.atomic_write_json(after, minimal_baseline(tool, run_id, "after"))
    output = tmp_path / "invariants.json"
    assert tool.evaluate_invariants(
        argparse.Namespace(run_id=run_id, before=str(before), after=str(after), output=str(output))
    ) == 0
    payload = json.loads(output.read_text())
    assert payload["checks"]["sqlite_quick_check"]["status"] == "passed"
    assert payload["checks"]["progress_monotonic"]["status"] == "not_evaluated"
    assert payload["checks"]["single_active_security_run"]["status"] == "not_evaluated"


def test_unavailable_real_gate_is_not_ready_and_counted(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-unavailable-test"
    run_dir = tmp_path / run_id
    tool.init_run(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            repo_root=str(ROOT),
            gates="idle-stability",
            mode="gates",
            resume=False,
        )
    )
    tool.atomic_write_json(run_dir / "baseline/before.json", minimal_baseline(tool, run_id, "before"))
    tool.atomic_write_json(run_dir / "baseline/after.json", minimal_baseline(tool, run_id, "after"))
    tool.gate_result(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            gate_id="idle-stability",
            status="unavailable",
            phase5_gate=1,
            framework_validation=0,
            started_at="",
            duration_seconds="0",
            failure_reason="Phase 5 gate is registered but not implemented in Group 1.",
            failed_stage="availability",
            retryable=1,
            resume_safe=1,
            evidence_refs="",
        )
    )
    tool.atomic_write_json(
        run_dir / "invariants.json",
        {"schema_version": 1, "run_id": run_id, "required_failures": [], "checks": {}, "sanitized": True},
    )
    tool.atomic_write_json(
        run_dir / "sanitization.json",
        {"schema_version": 1, "run_id": run_id, "sanitized": True, "findings": []},
    )
    output = run_dir / "summary.json"
    assert tool.aggregate(argparse.Namespace(run_dir=str(run_dir), run_id=run_id, output=str(output))) == 2
    summary = json.loads(output.read_text())
    assert summary["status"] == "not_ready"
    assert summary["gates_unavailable"] == 1
    assert summary["real_phase5_gates_executed"] == 1
    assert "not implemented" in summary["failure_reason"].lower()
