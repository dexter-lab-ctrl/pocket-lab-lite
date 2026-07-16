from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "scripts/dev/check-lite-long-duration-gates-server-phone.sh"
JSON_TOOL = ROOT / "scripts/dev/lib/long_gate_json.py"
GROUP2_TOOL = ROOT / "scripts/dev/lib/long_gate_group2.py"


def load_json_tool():
    spec = importlib.util.spec_from_file_location("long_gate_json_group2_reporting", JSON_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_registry_cli_and_all_selection():
    registry = subprocess.run(["bash", str(ORCHESTRATOR), "--list-gates"], cwd=ROOT, capture_output=True, text=True, check=True)
    for gate in ("idle", "repeated-scans", "progress-soak"):
        line = next(line for line in registry.stdout.splitlines() if line.startswith(gate))
        assert "implemented" in line
    dry = subprocess.run(["bash", str(ORCHESTRATOR), "--dry-run", "--all"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "selected_gates=idle,repeated-scans,progress-soak,wal-pressure,low-storage" in dry.stdout


def test_summary_distinguishes_implemented_selected_and_future(tmp_path: Path):
    tool = load_json_tool()
    run_id = "pocketlab-long-gates-group2-summary"
    run_dir = tmp_path / run_id
    tool.init_run(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "repo_root": str(ROOT), "gates": "idle", "mode": "gates", "resume": False})())
    for phase in ("before", "after"):
        tool.atomic_write_json(run_dir / "baseline" / f"{phase}.json", {"status": "captured", "pocket_lab": {"database_health": {"quick_check": "ok"}, "json_sqlite_parity": {"matched": True}}, "process_state": {"processes": []}})
    tool.atomic_write_json(run_dir / "gates/idle/result.json", {"gate_id": "idle", "status": "passed", "phase5_gate": True, "framework_validation": False, "failure_reason": "", "sanitized": True})
    tool.atomic_write_json(run_dir / "invariants.json", {"required_failures": [], "checks": {}})
    tool.atomic_write_json(run_dir / "sanitization.json", {"sanitized": True, "findings": []})
    output = run_dir / "summary.json"
    assert tool.aggregate(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "output": str(output)})()) == 0
    summary = json.loads(output.read_text())
    assert summary["implemented_gates"] == ["android-resume", "idle", "low-storage", "nats-restart", "progress-soak", "repeated-scans", "submission-recovery", "wal-pressure", "worker-restart"]
    assert summary["selected_gates"] == ["idle"]
    assert summary["passed_gates"] == ["idle"]
    assert summary["unavailable_future_gates"] == []
    assert summary["phase5_scope_complete"] is False


def test_source_safety_and_no_product_frontend_changes():
    source_paths = [ORCHESTRATOR, GROUP2_TOOL, *sorted((ROOT / "scripts/dev/long-gates").glob("*.sh"))]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    assert '"/tmp"' not in combined
    assert "pm2 restart" not in combined
    assert "systemctl restart" not in combined
    assert "nats-server --signal" not in combined
    assert "Authorization: Bearer ${POCKETLAB_API_TOKEN}" not in combined
    assert "while true" not in combined
    frontend = (ROOT / "src/hooks/useLiteSecurityEvents.js").read_text(encoding="utf-8")
    assert "EventSource" in frontend
    assert "nats://" not in frontend
    assert "child_process" not in frontend


def test_result_schema_rejects_contradictory_status(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("long_gate_group2_result", GROUP2_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    path = tmp_path / "result.json"
    try:
        module.write_result(path, {"status": "passed", "failure_reason": "should not exist"})
    except RuntimeError:
        pass
    else:
        raise AssertionError("contradictory passing result was accepted")
