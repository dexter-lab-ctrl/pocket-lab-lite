from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
JSON_TOOL = ROOT / "scripts/dev/lib/long_gate_json.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_json_checkpoint", JSON_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def init_run(tool, run_dir: Path, run_id: str, *, resume: bool = False):
    return tool.init_run(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            repo_root=str(ROOT),
            gates="framework-self-test",
            mode="framework_self_test",
            resume=resume,
        )
    )


def transition(tool, run_dir: Path, run_id: str, stage: str, status: str, reason: str = ""):
    return tool.checkpoint_transition(
        argparse.Namespace(
            run_dir=str(run_dir),
            run_id=run_id,
            gate_id="framework-self-test",
            stage_id=stage,
            status=status,
            failure_reason=reason,
            evidence_refs="",
            resume_safe=1,
            retryable=1,
        )
    )


def test_manifest_layout_and_atomic_checkpoint_transitions(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-checkpoint-test"
    run_dir = tmp_path / run_id
    init_run(tool, run_dir, run_id)
    for name in ("checkpoints", "baseline", "gates", "samples", "logs", "tmp"):
        assert (run_dir / name).is_dir()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["sanitized"] is True
    assert manifest["selected_gates"] == ["framework-self-test"]

    transition(tool, run_dir, run_id, "layout", "running")
    transition(tool, run_dir, run_id, "layout", "passed")
    checkpoint = json.loads((run_dir / "checkpoints/framework-self-test.json").read_text())
    assert checkpoint["status"] == "passed"
    assert checkpoint["last_successful_stage"] == "layout"
    assert checkpoint["attempt"] == 1
    assert not list((run_dir / "checkpoints").glob(".*.tmp"))


def test_resume_marks_running_stage_interrupted_and_preserves_history(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-resume-test"
    run_dir = tmp_path / run_id
    init_run(tool, run_dir, run_id)
    transition(tool, run_dir, run_id, "resume-boundary", "running")
    tool.mark_interrupted(argparse.Namespace(run_dir=str(run_dir), run_id=run_id))
    checkpoint = json.loads((run_dir / "checkpoints/framework-self-test.json").read_text())
    assert checkpoint["status"] == "interrupted"
    assert checkpoint["resume_safe"] is True
    assert checkpoint["failure_reason"]

    init_run(tool, run_dir, run_id, resume=True)
    transition(tool, run_dir, run_id, "resume-boundary", "running")
    transition(tool, run_dir, run_id, "resume-boundary", "passed")
    checkpoint = json.loads((run_dir / "checkpoints/framework-self-test.json").read_text())
    assert checkpoint["attempt"] == 2
    statuses = [entry["status"] for entry in checkpoint["history"]]
    assert "interrupted" in statuses
    assert statuses[-1] == "passed"
    state = json.loads((run_dir / "state.json").read_text())
    assert state["resume_count"] == 1


def test_completed_stage_is_not_rerun_by_framework_self_test(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-selftest-resume"
    run_dir = tmp_path / run_id
    init_run(tool, run_dir, run_id)
    os.environ["POCKETLAB_LONG_GATE_SELF_TEST_INTERRUPT_AT_STAGE"] = "atomic-evidence"
    try:
        assert tool.framework_self_test(
            argparse.Namespace(run_dir=str(run_dir), run_id=run_id, gate_id="framework-self-test")
        ) == 75
    finally:
        os.environ.pop("POCKETLAB_LONG_GATE_SELF_TEST_INTERRUPT_AT_STAGE", None)
    checkpoint = json.loads((run_dir / "checkpoints/framework-self-test.json").read_text())
    assert checkpoint["stage_id"] == "atomic-evidence"
    assert checkpoint["status"] == "running"
    layout_pass_count = sum(
        1
        for entry in checkpoint["history"]
        if entry.get("stage_id") == "layout" and entry.get("status") == "passed"
    )
    tool.mark_interrupted(argparse.Namespace(run_dir=str(run_dir), run_id=run_id))
    assert tool.framework_self_test(
        argparse.Namespace(run_dir=str(run_dir), run_id=run_id, gate_id="framework-self-test")
    ) == 0
    resumed = json.loads((run_dir / "checkpoints/framework-self-test.json").read_text())
    assert sum(
        1
        for entry in resumed["history"]
        if entry.get("stage_id") == "layout" and entry.get("status") == "passed"
    ) == layout_pass_count
    assert resumed["status"] == "passed"


def test_corrupt_checkpoint_and_manifest_fail_closed(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-corrupt-test"
    run_dir = tmp_path / run_id
    init_run(tool, run_dir, run_id)
    checkpoint = run_dir / "checkpoints/framework-self-test.json"
    checkpoint.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        tool.mark_interrupted(argparse.Namespace(run_dir=str(run_dir), run_id=run_id))

    (run_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 999, "run_id": run_id, "sanitized": True}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema version"):
        init_run(tool, run_dir, run_id, resume=True)


def test_stale_lock_requires_inactive_pid_and_minimum_age(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-stale-lock"
    owner = tmp_path / "owner.json"
    tool.lock_metadata(
        argparse.Namespace(output=str(owner), run_id=run_id, pid=str(os.getpid()))
    )
    active_rc = tool.inspect_lock(
        argparse.Namespace(path=str(owner), run_id=run_id, minimum_age="0")
    )
    assert active_rc == 3

    payload = json.loads(owner.read_text())
    payload["pid"] = 99999999
    payload["started_epoch"] = 0
    tool.atomic_write_json(owner, payload)
    assert tool.inspect_lock(
        argparse.Namespace(path=str(owner), run_id=run_id, minimum_age="60")
    ) == 0
