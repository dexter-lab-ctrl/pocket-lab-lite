from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "scripts/dev/check-lite-long-duration-gates-server-phone.sh"
GROUP4 = ROOT / "scripts/dev/lib/long_gate_group4.py"
FRONTEND_HOOK = ROOT / "src/hooks/useLiteSecurityEvents.js"


def run(*args: str):
    return subprocess.run(["bash", str(ORCHESTRATOR), *args], cwd=ROOT, capture_output=True, text=True)


def test_group4_registry_and_all_selection_are_truthful(tmp_path: Path):
    registry = run("--list-gates")
    assert registry.returncode == 0
    for gate in ("wal-pressure", "low-storage", "android-resume"):
        assert gate in registry.stdout
        line = next(item for item in registry.stdout.splitlines() if item.startswith(gate))
        assert "implemented" in line
    assert "android-resume" in registry.stdout and "yes" not in next(item for item in registry.stdout.splitlines() if item.startswith("android-resume")).split()[4:5]

    all_dry = run("--all", "--dry-run", "--report-dir", str(tmp_path))
    assert all_dry.returncode == 0
    assert "wal-pressure" in all_dry.stdout
    assert "low-storage" in all_dry.stdout
    assert "android-resume" not in all_dry.stdout
    assert "nats-restart" not in all_dry.stdout


def test_live_storage_requires_both_optins_and_explicit_cap(tmp_path: Path):
    base = ("--gate", "low-storage", "--scenario", "live", "--dry-run", "--report-dir", str(tmp_path))
    denied = run(*base)
    assert denied.returncode == 22
    assert "allow-storage-pressure" in denied.stderr
    one_optin = run(*base, "--allow-disruptive")
    assert one_optin.returncode == 22
    allowed = run(*base, "--allow-disruptive", "--allow-storage-pressure", "--max-allocation-bytes", "1048576")
    assert allowed.returncode == 0, allowed.stderr
    assert "capped run-owned allocation" in allowed.stdout


def test_group4_source_safety_contracts():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [ORCHESTRATOR, GROUP4, *sorted((ROOT / "scripts/dev/long-gates").glob("*.sh"))]
    )
    assert '"/tmp"' not in sources
    assert "VACUUM" not in GROUP4.read_text(encoding="utf-8").upper()
    assert "pm2 kill" not in sources
    assert "pm2 restart all" not in sources
    assert "pkill -9" not in sources
    frontend = FRONTEND_HOOK.read_text(encoding="utf-8")
    assert "EventSource" in frontend
    assert "visibilitychange" in frontend
    assert "sourceActiveRef.current" in frontend
    assert "fallbackActive" in frontend
    assert "nats://" not in frontend
    assert "child_process" not in frontend


def test_wal_and_android_dry_runs_show_safe_plan(tmp_path: Path):
    wal = run("--gate", "wal-pressure", "--scenario", "isolated", "--duration-seconds", "5", "--dry-run", "--report-dir", str(tmp_path))
    assert wal.returncode == 0, wal.stderr
    assert "passive checkpoints only" in wal.stdout
    android = run("--gate", "android-resume", "--scenario", "background-active", "--dry-run", "--report-dir", str(tmp_path))
    assert android.returncode == 0, android.stderr
    assert "operator-assisted" in android.stdout


def test_full_phase5_ready_requires_all_nine_gates(tmp_path: Path):
    import importlib.util
    import json
    import sys

    json_tool = ROOT / "scripts/dev/lib/long_gate_json.py"
    spec = importlib.util.spec_from_file_location("long_gate_json_group4_full", json_tool)
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool
    spec.loader.exec_module(tool)
    gates = sorted(tool.REAL_PHASE5_GATES)
    run_id = "pocketlab-long-gates-group4-full-summary"
    run_dir = tmp_path / run_id
    tool.init_run(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "repo_root": str(ROOT), "gates": ",".join(gates), "mode": "gates", "resume": False})())
    for phase in ("before", "after"):
        tool.atomic_write_json(run_dir / "baseline" / f"{phase}.json", {"status": "captured", "pocket_lab": {"database_health": {"quick_check": "ok"}, "json_sqlite_parity": {"matched": True}}, "process_state": {"processes": []}})
    for gate in gates:
        tool.atomic_write_json(run_dir / "gates" / gate / "result.json", {"gate_id": gate, "status": "passed", "phase5_gate": True, "framework_validation": False, "failure_reason": "", "sanitized": True})
    tool.atomic_write_json(run_dir / "invariants.json", {"required_failures": [], "checks": {}})
    tool.atomic_write_json(run_dir / "sanitization.json", {"sanitized": True, "findings": []})
    output = run_dir / "summary.json"
    assert tool.aggregate(type("Args", (), {"run_dir": str(run_dir), "run_id": run_id, "output": str(output)})()) == 0
    summary = json.loads(output.read_text())
    assert summary["full_phase5_ready"] is True
    assert summary["phase5_scope_complete"] is True
    assert summary["unavailable_future_gates"] == []
