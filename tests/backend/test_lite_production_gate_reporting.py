from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / 'scripts/dev/check-lite-production-gate-server-phone.sh'

def test_gate_reports_latency_policy_failure_explicitly():
    text = GATE.read_text()
    assert 'Progress latency gate failed:' in text
    assert 'set +e' in text and 'rc=$?' in text

def test_gate_wraps_database_commands_with_explicit_failures():
    text = GATE.read_text()
    assert 'SQLite database check failed' in text
    assert 'JSON/SQLite comparison command failed' in text

def test_gate_is_valid_bash():
    result = subprocess.run(['bash','-n',str(GATE)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_gate_preserves_runtime_diagnostics_capture_failure_evidence():
    text = GATE.read_text()
    assert '"capture_ok": False' in text
    assert '"error_class": error_class' in text
    assert '"timeout_seconds": 3' in text
    assert 'error_class = "timeout" if rc == 28 else "capture_failed"' in text

def test_gate_declares_all_required_functions_before_main_execution():
    text = GATE.read_text()
    for name in (
        'latency_gate', 'submission_latency_gate', 'capture_runtime_diagnostics',
        'write_final_report', 'run_scan_gate', 'sample_progress',
    ):
        assert f'{name}()' in text
    assert 'required_gate_functions' in text
    assert 'declare -F "$name"' in text
