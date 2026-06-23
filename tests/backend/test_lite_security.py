from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_lite_security_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_SCAN_ROOT", str(Path.cwd()))
    yield


def test_lite_security_default_state_is_stable():
    from api_fastapi.services import lite_security

    payload = lite_security.current_state()
    assert payload["status"] == "healthy"
    assert payload["summary"] == "No urgent safety issues found."
    assert payload["score"] == 100
    assert payload["last_run"] is None
    assert payload["checks_reviewed"] == 0
    assert payload["critical_issues"] == []
    assert len(payload["guidance"]) == 3


def test_lite_security_check_queues_worker_command(monkeypatch):
    from api_fastapi.services import lite_security
    from api_fastapi.services.nats_bus import BUS

    published: list[tuple[str, str, dict]] = []
    BUS.connected = True
    BUS.js = object()

    async def fake_publish(subject, event_type, data=None, *, trace_id=None):
        published.append((subject, event_type, data or {}))

    monkeypatch.setattr(BUS, "publish_json", fake_publish)

    response = client().post("/api/lite/security/check", json={"reason": "unit-test"})
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["accepted"] is True
    assert payload["command_subject"] == "pocketlab.commands.lite.security.scan"
    assert payload["execution_mode"] == "worker"
    assert payload["run_id"].startswith("security-")
    assert any(item[0] == "pocketlab.commands.lite.security.scan" for item in published)
    assert lite_security.read_run(payload["run_id"])["status"] == "queued"


def test_lite_security_check_fails_closed_when_bus_unavailable(monkeypatch):
    from api_fastapi.services import lite_security
    from api_fastapi.services.nats_bus import BUS

    BUS.connected = False
    BUS.nc = None
    BUS.js = None

    async def fail_start():
        raise RuntimeError("unit-test NATS unavailable")

    monkeypatch.setattr(BUS, "start", fail_start)

    response = client().post("/api/lite/security/check", json={"reason": "bus-down"})
    assert response.status_code == 503
    assert lite_security.current_state()["last_run"] is None


def test_missing_lynis_and_trivy_produce_safe_normalized_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    (tmp_path / "empty-bin").mkdir()

    from api_fastapi.services import lite_security

    result = lite_security.run_security_scan({"command_id": "security-missing-tools", "run_id": "security-missing-tools"})
    state = result["state"]
    assert state["last_run"]["status"] == "succeeded"
    assert state["score"] == 90
    assert state["status"] in {"review", "degraded"}
    assert state["items_to_review"] == 2
    categories = {item["category"] for item in result["findings"]}
    assert categories == {"missing_tool"}

    evidence_payload = lite_security.read_evidence("security-missing-tools")
    assert evidence_payload is not None
    text = json.dumps(evidence_payload).lower()
    assert "password=" not in text
    assert "authorization:" not in text
    assert "***redacted***" not in text or "secret-like" in text


def _write_fake_tool(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    path.chmod(0o755)


def test_trivy_secret_findings_are_redacted_and_critical(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_tool(
        bin_dir / "lynis",
        """
import sys
print('Lynis quick scan completed')
raise SystemExit(0)
""",
    )
    _write_fake_tool(
        bin_dir / "trivy",
        """
import json
import pathlib
import sys
args = sys.argv[1:]
if '--format' in args and args[args.index('--format') + 1] == 'cyclonedx':
    out = pathlib.Path(args[args.index('--output') + 1])
    out.write_text(json.dumps({'bomFormat': 'CycloneDX', 'components': []}), encoding='utf-8')
    raise SystemExit(0)
if '--scanners' in args and args[args.index('--scanners') + 1] == 'secret':
    print(json.dumps({'Results': [{'Target': 'state/example.env', 'Secrets': [{'RuleID': 'generic-api-key', 'Severity': 'CRITICAL', 'Match': 'password=super-secret-value'}]}]}))
    raise SystemExit(0)
print(json.dumps({'Results': [{'Target': 'package-lock.json', 'Vulnerabilities': [{'VulnerabilityID': 'CVE-TEST-1', 'PkgName': 'example-package', 'Severity': 'HIGH', 'FixedVersion': '1.2.3'}]}]}))
raise SystemExit(0)
""",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from api_fastapi.services import lite_security

    result = lite_security.run_security_scan({"command_id": "security-critical", "run_id": "security-critical"})
    state = result["state"]
    assert state["status"] == "danger"
    assert state["last_run"]["critical_count"] == 1
    assert state["last_run"]["high_count"] == 1
    assert state["score"] == 55
    assert state["critical_issues"][0]["category"] == "secret_exposure"

    evidence_payload = lite_security.read_evidence("security-critical")
    dumped = json.dumps(evidence_payload).lower()
    assert "super-secret-value" not in dumped
    assert "potential secret-like value found" in dumped


def test_score_calculation_and_critical_status():
    from api_fastapi.services import lite_security

    run = {"run_id": "score-test", "status": "succeeded", "tools": ["lynis", "trivy"]}
    findings = [
        lite_security.normalize_finding({"id": "a", "source": "trivy", "category": "secret_exposure", "severity": "critical"}),
        lite_security.normalize_finding({"id": "b", "source": "trivy", "category": "dependency_vulnerability", "severity": "high"}),
        lite_security.normalize_finding({"id": "c", "source": "lynis", "category": "host_hardening", "severity": "medium"}),
    ]
    state = lite_security.build_state(run, findings, [])
    assert state["score"] == 50
    assert state["status"] == "danger"
    assert state["last_run"]["critical_count"] == 1
    assert len(state["critical_issues"]) == 1


def test_lynis_normalizer_filters_termux_proc_net_dev_warning():
    from api_fastapi.services import lite_security

    result = {
        "returncode": 0,
        "stdout": "Warning: cannot open /proc/net/dev (Permission denied). Limited output.",
        "stderr": "",
        "timed_out": False,
    }

    findings = lite_security.normalize_lynis_output(result, "security-termux-net-dev")
    assert findings == []


def test_lynis_normalizer_strips_noise_and_dedupes():
    from api_fastapi.services import lite_security

    result = {
        "returncode": 0,
        "stdout": "\n".join(
            [
                "\x1b[2C-e   [WARNING]: Test KRNL-6000 had a long execution: 13.0 seconds",
                "Warning: PID file exists, probably another Lynis process is running.",
                "-e \x1b[4C- OpenSSH option: MaxAuthTries\x1b[27C [ SUGGESTION ]",
                "* Consider hardening SSH configuration [SSH-7408]",
                "* Consider hardening SSH configuration [SSH-7408]",
                "* Article: OpenSSH security and hardening: https://example.invalid/ssh",
                "Suggestions (31):",
            ]
        ),
        "stderr": "",
        "timed_out": False,
    }

    findings = lite_security.normalize_lynis_output(result, "security-clean")
    recommendations = [item["recommendation"] for item in findings]
    assert len([item for item in recommendations if "Consider hardening SSH" in item]) == 1
    assert all("\x1b" not in item for item in recommendations)
    assert all(not item.startswith("-e") for item in recommendations)
    assert all("long execution" not in item.lower() for item in recommendations)
    assert all("pid file exists" not in item.lower() for item in recommendations)
    assert all("article:" not in item.lower() for item in recommendations)


def test_protected_runtime_secret_is_downgraded_when_locked_down(tmp_path):
    from api_fastapi.services import lite_security

    conf_dir = tmp_path / "gitea" / "conf"
    conf_dir.mkdir(parents=True)
    runtime = conf_dir / "app.runtime.ini"
    runtime.write_text("[security]\nJWT_SECRET=super-secret-value\n", encoding="utf-8")
    conf_dir.chmod(0o700)
    runtime.chmod(0o600)

    payload = {
        "Results": [
            {
                "Target": "gitea/conf/app.runtime.ini",
                "Secrets": [{"RuleID": "jwt-token", "Severity": "CRITICAL", "Match": "JWT_SECRET=super-secret-value"}],
            }
        ]
    }
    findings = lite_security.normalize_trivy_json(payload, "security-protected", secret_mode=True, root=tmp_path)
    assert len(findings) == 1
    assert findings[0]["category"] == "protected_runtime_secret"
    assert findings[0]["severity"] == "low"
    assert findings[0]["summary"] == "Protected backend runtime secret found."
    assert "super-secret-value" not in str(findings[0])


def test_security_scan_progress_estimates_remaining_time(monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_security

    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ESTIMATED_SECONDS", "240")
    monkeypatch.setattr(deps, "now_utc_iso", lambda: "2026-01-01T00:01:00Z")

    run = {
        "run_id": "security-progress",
        "status": "running",
        "tools": ["lynis", "trivy"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": None,
        "partial_results": False,
    }

    state = lite_security.build_state(run, [], [], status_override="running")
    progress = state["scan_progress"]
    assert progress["status"] == "running"
    assert progress["stage"] == "Running Lynis and Trivy"
    assert progress["elapsed_seconds"] == 60
    assert progress["estimated_total_seconds"] == 240
    assert progress["estimated_remaining_seconds"] == 180
    assert progress["estimated_remaining_label"] == "about 3 min"
    assert progress["percent"] == 25


def test_security_scan_progress_marks_completed(monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_security

    monkeypatch.setattr(deps, "now_utc_iso", lambda: "2026-01-01T00:04:00Z")
    run = {
        "run_id": "security-progress-complete",
        "status": "succeeded",
        "tools": ["lynis", "trivy"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:03:00Z",
        "partial_results": False,
    }

    state = lite_security.build_state(run, [], [])
    assert state["scan_progress"]["percent"] == 100
    assert state["scan_progress"]["estimated_remaining_seconds"] == 0
    assert state["scan_progress"]["stage"] == "Safety check complete"
