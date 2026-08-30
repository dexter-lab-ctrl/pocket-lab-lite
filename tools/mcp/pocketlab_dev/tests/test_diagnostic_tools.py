from __future__ import annotations

import json

import pytest

from pocketlab_dev_mcp.policy import UnknownDiagnosticTarget, get_diagnostic_target
from pocketlab_dev_mcp.runner import ProcessResult
from pocketlab_dev_mcp.tools.diagnostics import DiagnosticTools


class FakeRunner:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.calls: list[tuple[tuple[str, ...], float]] = []

    def run(self, argv, *, timeout_seconds):
        self.calls.append((tuple(argv), timeout_seconds))
        return self.result


def test_diagnostic_targets_are_exact_and_ordered(repository_root):
    listed = DiagnosticTools(repository_root).diagnostic_targets()["targets"]
    assert [target["id"] for target in listed] == ["docs_health", "generated_drift", "runtime_capture", "pm2_status", "nats_health", "openapi_routes", "security_summary", "pm2_summary", "security_run_summary"]
    assert all(target["mutation_capability"] is False for target in listed)


@pytest.mark.parametrize("candidate", ["openapi_routes; rm -rf /", "../../etc/passwd", "$(whoami)", "pm2_status --json", "nats_health && env", "pm2_summary; reboot", "security_run_summary $(whoami)", "ssh pocketlab-termux"])
def test_unknown_diagnostics_fail_before_execution(candidate):
    with pytest.raises(UnknownDiagnosticTarget):
        get_diagnostic_target(candidate)


def test_openapi_summary_is_compact(repository_root):
    path = repository_root / "contracts/generated"
    path.mkdir(parents=True)
    (path / "lite-openapi.json").write_text(json.dumps({
        "openapi": "3.1.0",
        "paths": {"/api/lite/example": {"get": {}}, "/outside": {"post": {}}},
        "components": {"schemas": {"Example": {}}},
    }), encoding="utf-8")
    result = DiagnosticTools(repository_root).diagnostic_summary("openapi_routes")
    assert result["status"] == "ok"
    assert result["complete"] is True
    assert result["sources"] == ["contracts/generated/lite-openapi.json"]
    assert any(fact["name"] == "route_count" for fact in result["facts"])


def test_openapi_missing_or_malformed_is_truthfully_unavailable(tmp_path, repository_root):
    tools = DiagnosticTools(repository_root)
    tools.repository_root = tmp_path
    assert tools.diagnostic_summary("openapi_routes")["status"] == "unavailable"
    path = tmp_path / "contracts/generated"
    path.mkdir(parents=True)
    (path / "lite-openapi.json").write_text("not-json", encoding="utf-8")
    assert tools.diagnostic_summary("openapi_routes")["status"] == "unavailable"


def test_pm2_projects_only_safe_fields(repository_root):
    payload = [{"name": "safe", "pid": 7, "pm2_env": {"status": "online", "restart_time": 2, "pm_uptime": 3, "token": "never-return"}, "pm_exec_path": "secret command"}]
    runner = FakeRunner(ProcessResult(0, 1, json.dumps(payload), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_status")
    assert result["status"] == "ok"
    assert "never-return" not in repr(result)
    assert "secret command" not in repr(result)
    assert runner.calls == [(("pm2", "jlist"), 15)]


def test_pm2_unavailable_never_mutates(repository_root):
    runner = FakeRunner(ProcessResult(127, 1, "", "missing", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_status")
    assert result["status"] == "unavailable"
    assert runner.calls == [(("pm2", "jlist"), 15)]


def test_pm2_output_is_bounded_and_reports_truncation(repository_root):
    payload = [{"name": f"process-{index}", "pid": index, "pm2_env": {"status": "online"}} for index in range(20)]
    runner = FakeRunner(ProcessResult(0, 1, json.dumps(payload), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_status")
    assert result["truncated"] is True
    assert result["complete"] is False
    assert len(result["facts"]) == 12


def test_remote_pm2_summary_uses_only_fixed_managed_alias_and_safe_projection(repository_root):
    payload = [
        {"name": "pocket-api", "pid": 7, "pm2_env": {"status": "online", "restart_time": 2, "pm_uptime": 3, "token": "never-return"}, "pm_exec_path": "secret command"},
        {"name": "unrelated", "pid": 8, "pm2_env": {"status": "online"}},
    ]
    runner = FakeRunner(ProcessResult(0, 1, json.dumps(payload), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_summary")
    assert result["status"] == "ok"
    assert result["sources"] == ["server_phone:pm2"]
    assert "never-return" not in repr(result)
    assert "secret command" not in repr(result)
    assert "unrelated" not in repr(result)
    assert runner.calls[0][0][:8] == ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ConnectionAttempts=1", "pocketlab-termux")
    assert runner.calls[0][0][8].startswith("python3 -c ")
    assert "pm2'\"'\"','\"'\"'jlist" in runner.calls[0][0][8]


def test_remote_pm2_failure_is_transport_unavailable(repository_root):
    runner = FakeRunner(ProcessResult(255, 1, "", "identityfile=/private/path", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_summary")
    assert result["status"] == "unavailable"
    assert "private/path" not in repr(result)
    assert runner.calls[0][0][8].startswith("python3 -c ")


def test_nats_uses_fixed_pm2_projection_and_keeps_promoted_evidence_distinct(repository_root):
    runtime = repository_root / "contracts/generated/runtime"
    runtime.mkdir(parents=True)
    (runtime / "domain-operational-health.json").write_text(json.dumps({"domains": {"nats": {}}, "sanitized": True}), encoding="utf-8")
    runner = FakeRunner(ProcessResult(0, 1, json.dumps([{"name": "pocket-nats", "pm2_env": {"status": "online", "password": "never-return"}}]), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("nats_health")
    assert result["status"] == "ok"
    assert result["sources"] == ["server_phone:pm2", "contracts/generated/runtime/domain-operational-health.json"]
    assert "never-return" not in repr(result)
    assert runner.calls[0][0][8].startswith("python3 -c ")


def test_nats_attempts_live_pm2_when_promoted_nats_evidence_is_missing(repository_root):
    runtime = repository_root / "contracts/generated/runtime"
    runtime.mkdir(parents=True)
    (runtime / "domain-operational-health.json").write_text(json.dumps({"domains": {}, "sanitized": True}), encoding="utf-8")
    runner = FakeRunner(ProcessResult(0, 1, json.dumps([{"name": "pocket-nats", "pm2_env": {"status": "online"}}]), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("nats_health")
    assert result["status"] == "ok"
    assert any(fact == {"name": "promoted_evidence_state", "value": "unavailable"} for fact in result["facts"])
    assert runner.calls[0][0][8].startswith("python3 -c ")


def test_remote_security_summary_never_runs_a_scanner_and_projects_only_safe_fields(repository_root):
    payload = {"status": "verified", "updated_at": "2026-08-30T00:00:00Z", "latest_run": {"status": "verified", "completed_at": "2026-08-30T00:00:00Z", "token": "never-return"}, "evidence_refs": ["safe"]}
    runner = FakeRunner(ProcessResult(0, 1, json.dumps(payload), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("security_run_summary")
    assert result["status"] == "ok"
    assert "never-return" not in repr(result)
    call = runner.calls[0][0]
    assert call[:7] == ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ConnectionAttempts=1")
    assert "pocketlab-termux" in call
    assert not {"trivy", "syft", "semgrep"}.intersection(call)


def test_remote_diagnostics_report_explicit_bounds(repository_root):
    payload = [{"name": f"pocketlab-agent-{index}", "pid": index, "pm2_env": {"status": "online"}} for index in range(20)]
    runner = FakeRunner(ProcessResult(0, 1, json.dumps(payload), "", False, False))
    result = DiagnosticTools(repository_root, runner=runner).diagnostic_summary("pm2_summary")
    assert result["truncated"] is True
    assert result["complete"] is False


def test_runtime_and_security_missing_evidence_are_unavailable(repository_root):
    tools = DiagnosticTools(repository_root)
    assert tools.diagnostic_summary("runtime_capture")["status"] == "unavailable"
    assert tools.diagnostic_summary("security_summary")["status"] == "unavailable"
