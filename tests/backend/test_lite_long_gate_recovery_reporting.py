from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
JSON_TOOL = ROOT / "scripts/dev/lib/long_gate_json.py"
GROUP3 = ROOT / "scripts/dev/lib/long_gate_group3.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_summary_includes_group3_and_group4_implementation(tmp_path: Path):
    tool = load(JSON_TOOL, "long_gate_json_group3_reporting")
    run_id = "pocketlab-long-gates-group3-summary"
    run_dir = tmp_path / run_id
    tool.init_run(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "repo_root": str(ROOT), "gates": "nats-restart", "mode": "gates", "resume": False})())
    for phase in ("before", "after"):
        tool.atomic_write_json(run_dir / "baseline" / f"{phase}.json", {"status": "captured", "pocket_lab": {"database_health": {"quick_check": "ok"}, "json_sqlite_parity": {"matched": True}}, "process_state": {"processes": []}})
    tool.atomic_write_json(run_dir / "gates/nats-restart/result.json", {"gate_id": "nats-restart", "status": "passed", "phase5_gate": True, "framework_validation": False, "failure_reason": "", "sanitized": True})
    tool.atomic_write_json(run_dir / "invariants.json", {"required_failures": [], "checks": {}})
    tool.atomic_write_json(run_dir / "sanitization.json", {"sanitized": True, "findings": []})
    output = run_dir / "summary.json"
    assert tool.aggregate(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "output": str(output)})()) == 0
    summary = json.loads(output.read_text())
    for gate in ("submission-recovery", "nats-restart", "worker-restart"):
        assert gate in summary["implemented_gates"]
    for gate in ("wal-pressure", "low-storage", "android-resume"):
        assert gate in summary["implemented_gates"]
    assert summary["unavailable_future_gates"] == []
    assert summary["phase5_scope_complete"] is False


def test_group3_result_schema_and_evidence_refs(tmp_path: Path):
    module = load(GROUP3, "long_gate_group3_result_schema")
    path = tmp_path / "result.json"
    module.g2.write_result(path, {
        "status": "failed",
        "failure_reason": "A concise sanitized failure.",
        "gate": "worker-restart",
        "scenario": "after-claim",
        "sanitized": True,
    })
    payload = json.loads(path.read_text())
    assert payload["status"] == "failed"
    assert payload["failure_reason"]
    assert payload["sanitized"] is True
    try:
        module.g2.write_result(path, {"status": "failed", "failure_reason": ""})
    except RuntimeError:
        pass
    else:
        raise AssertionError("failed result without a reason was accepted")


def test_source_safety_no_public_ui_or_secret_evidence():
    sources = [
        GROUP3,
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_gate_faults.py",
        ROOT / "scripts/dev/check-lite-long-duration-gates-server-phone.sh",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert '"/tmp"' not in combined
    assert "pm2 kill" not in combined
    assert "restart all" not in combined
    assert "Authorization" not in (ROOT / "scripts/dev/lib/long_gate_group3.py").read_text()
    assert "token_sha256" in combined
    assert "token\": token" not in combined
    frontend = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "src").rglob("*") if path.is_file())
    assert "submission-response-delay" not in frontend
    assert "pocket-nats" not in frontend
    assert "pocket-worker" not in frontend


def test_active_nats_resume_reconciles_before_preflight_parity_and_never_restarts_twice():
    source = GROUP3.read_text(encoding="utf-8")
    loop = source.split('for scenario in _scenario_list(args.scenario, ("idle", "active")):', 1)[1]
    assert loop.index("reconcile_active_nats_resume") < loop.index("_preflight_disruption")
    helper = source.split("def reconcile_active_nats_resume", 1)[1].split("def run_nats_restart", 1)[0]
    assert "wait_for_nats" in helper
    assert "wait_terminal" in helper
    assert "wait_for_reconciled_health" in helper
    assert "run_pm2_action" not in helper
    assert "refusing to restart twice" in helper


def test_active_nats_resume_safety_order_is_explicit():
    source = GROUP3.read_text(encoding="utf-8")
    health = source.split("def wait_for_reconciled_health", 1)[1].split("def reconcile_active_nats_resume", 1)[0]
    assert health.index('health.get("quick_check")') < health.index('health.get("matched")')
    assert "resume_sqlite_quick_check" in health
    assert "resume_final_parity" in health
    resume = source.split("def reconcile_active_nats_resume", 1)[1].split("def run_nats_restart", 1)[0]
    assert resume.index("resume_identity") < resume.index("wait_for_nats")
    assert resume.index("wait_for_nats") < resume.index("wait_terminal")
    assert resume.index("wait_terminal") < resume.index("wait_for_reconciled_health")
