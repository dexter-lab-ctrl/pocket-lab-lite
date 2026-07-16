from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "scripts/dev/check-lite-long-duration-gates-server-phone.sh"
PRODUCTION_GATE = ROOT / "scripts/dev/check-lite-production-gate-server-phone.sh"
JSON_TOOL = ROOT / "scripts/dev/lib/long_gate_json.py"
LIB_DIR = ROOT / "scripts/dev/lib"
SELF_TEST = ROOT / "scripts/dev/long-gates/framework-self-test.sh"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_json_framework", JSON_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase5_group1_shell_files_are_valid_and_modular():
    files = [ORCHESTRATOR, SELF_TEST, *sorted(LIB_DIR.glob("long_gate_*.sh"))]
    assert len(files) >= 8
    for path in files:
        result = subprocess.run(
            ["bash", "-n", str(path)], cwd=ROOT, capture_output=True, text=True
        )
        assert result.returncode == 0, f"{path}: {result.stderr}"
    assert len(ORCHESTRATOR.read_text(encoding="utf-8").splitlines()) < 560
    assert "scripts/dev/lib/long_gate_" in ORCHESTRATOR.read_text(encoding="utf-8")


def test_cli_help_registry_and_dry_run_are_truthful(tmp_path: Path):
    help_result = subprocess.run(
        ["bash", str(ORCHESTRATOR), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    for option in (
        "--gate <name>",
        "--all",
        "--resume",
        "--report-dir <path>",
        "--run-id <id>",
        "--list-gates",
        "--dry-run",
    ):
        assert option in help_result.stdout

    registry = subprocess.run(
        ["bash", str(ORCHESTRATOR), "--list-gates"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert registry.returncode == 0
    assert "framework-self-test" in registry.stdout
    assert "implemented" in registry.stdout
    for gate in (
        "idle",
        "repeated-scans",
        "progress-soak",
        "submission-recovery",
        "nats-restart",
        "worker-restart",
        "wal-checkpoint-pressure",
        "low-storage",
        "android-background-resume",
    ):
        assert gate in registry.stdout
    assert registry.stdout.count("unavailable") >= 3
    assert registry.stdout.count("implemented") >= 7

    report_root = tmp_path / "reports"
    dry_run = subprocess.run(
        [
            "bash",
            str(ORCHESTRATOR),
            "--dry-run",
            "--framework-self-test",
            "--report-dir",
            str(report_root),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "mode=framework_self_test" in dry_run.stdout
    assert "status=implemented" in dry_run.stdout
    assert not any(report_root.glob("*/manifest.json"))


def test_unavailable_gate_and_all_paths_cannot_claim_ready():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "LONG_GATE_EXIT_GATE_UNAVAILABLE=24" in (LIB_DIR / "long_gate_common.sh").read_text()
    assert "registered but not implemented in the current group" in text
    assert "unavailable_selected=1" in text
    assert 'exit "$LONG_GATE_EXIT_GATE_UNAVAILABLE"' in text
    all_dry = subprocess.run(["bash", str(ORCHESTRATOR), "--dry-run", "--all"], cwd=ROOT, capture_output=True, text=True)
    assert all_dry.returncode == 0
    assert "selected_gates=idle,repeated-scans,progress-soak" in all_dry.stdout
    assert "submission-recovery" not in all_dry.stdout
    assert "framework-self-test" not in list(
        line.strip() for line in text.split("real_gate_names()", 1)[-1].split("}", 1)[0].splitlines()
        if line.strip().startswith("printf")
    )


def test_run_id_generation_and_termux_safe_paths(monkeypatch: pytest.MonkeyPatch):
    tool = load_tool()
    first = subprocess.run(
        [sys.executable, str(JSON_TOOL), "generate-run-id", "--timestamp", "20260715-120000"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert first.startswith("pocketlab-long-gates-20260715-120000-")
    assert len(first.rsplit("-", 1)[-1]) == 8

    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setenv("TERMUX_VERSION", "0.119")
    assert tool.runtime_identity()["runtime_type"] == "termux"
    all_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [ORCHESTRATOR, JSON_TOOL, *sorted(LIB_DIR.glob("long_gate_*.sh"))]
    )
    assert '"/tmp"' not in all_source
    assert "mktemp" not in ORCHESTRATOR.read_text(encoding="utf-8")


def test_atomic_mkdir_lock_conflict_is_refused_before_resume(tmp_path: Path):
    tool = load_tool()
    run_id = "pocketlab-long-gates-lock-test"
    report_root = tmp_path / "reports"
    run_dir = report_root / run_id
    (run_dir / ".lock").mkdir(parents=True)
    tool.lock_metadata(
        type(
            "Args",
            (),
            {
                "output": str(run_dir / ".lock" / "owner.json"),
                "run_id": run_id,
                "pid": str(os.getpid()),
            },
        )()
    )
    result = subprocess.run(
        [
            "bash",
            str(ORCHESTRATOR),
            "--resume",
            "--run-id",
            run_id,
            "--framework-self-test",
            "--report-dir",
            str(report_root),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 23
    assert "already locked" in result.stderr.lower()


def test_existing_production_gate_remains_valid_bash():
    result = subprocess.run(
        ["bash", "-n", str(PRODUCTION_GATE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "pocketlab-lite-production-gate" in PRODUCTION_GATE.read_text(encoding="utf-8")
