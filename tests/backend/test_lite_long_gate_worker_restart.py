from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
GROUP3 = ROOT / "scripts/dev/lib/long_gate_group3.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group3_worker_test", GROUP3)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lifecycle_monotonicity_and_terminal_active_key():
    module = load_tool()
    good = {
        "status": "succeeded",
        "active_key": None,
        "requested_at_epoch_ms": 1,
        "command_published_at_epoch_ms": 2,
        "accepted_at_epoch_ms": 3,
        "command_received_at_epoch_ms": 4,
        "execution_started_at_epoch_ms": 5,
        "last_progress_at_epoch_ms": 6,
        "completed_at_epoch_ms": 7,
        "updated_at_epoch_ms": 7,
    }
    assert module.lifecycle_order_issues(good) == []
    bad = {**good, "execution_started_at_epoch_ms": 2, "active_key": "quick:"}
    issues = module.lifecycle_order_issues(bad)
    assert any(item.startswith("timestamp_regression") for item in issues)
    assert "terminal_active_key_not_cleared" in issues


def test_recovery_outcome_classification_is_truthful():
    module = load_tool()
    assert module.recovery_outcome(None) == "unresolved"
    assert module.recovery_outcome({"status": "succeeded"}, restarted_after_claim=True) == "recovered_and_succeeded"
    assert module.recovery_outcome({"status": "failed", "failure_code": "stale_accepted_recovered"}) == "stale_recovered"
    assert module.recovery_outcome({"status": "failed"}, restarted_after_claim=True) == "recovered_and_failed_truthfully"
    assert module.recovery_outcome({"status": "running"}) == "unresolved"


def test_pm2_action_whitelist_rejects_unrelated_or_broad_actions(monkeypatch):
    module = load_tool()
    assert module.run_pm2_action("caddy-proxy", "restart")["error_type"] == "unapproved_process_name"
    assert module.run_pm2_action("pocket-worker", "kill")["error_type"] == "unapproved_action"


def test_worker_resume_state_records_nonrepeatable_disruption_and_scanner_evidence():
    source = GROUP3.read_text(encoding="utf-8")
    assert '"safe_to_repeat": False' in source
    assert "refusing to restart twice" in source
    assert 'run_pm2_action("pocket-worker", "stop"' in source
    assert 'run_pm2_action("pocket-worker", "start"' in source
    assert 'run_pm2_action("pocket-worker", "restart"' in source
    assert "scanner_inventory" in source
    assert "wait_for_scanner_cleanup" in source
    assert "pkill" not in source
    assert "killall" not in source
