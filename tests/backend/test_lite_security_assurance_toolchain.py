from __future__ import annotations

import json
import sys
from pathlib import Path

from pocket_lab_test_utils import ensure_runtime_path


def _module():
    ensure_runtime_path()
    import scripts.dev.lite.security_assurance_toolchain as toolchain

    return toolchain


def test_tool_registry_promotes_all_required_tools_to_fixed_harness_contracts():
    toolchain = _module()
    registry = toolchain._registry()
    assert len(registry["toolchain"]) == 31
    assert all(item.get("harness_status") == "ACTIVE" for item in registry["toolchain"].values())
    assert all(item.get("execution_lane") in {"server_phone_worker", "dev_pc_static", "dev_pc_live_runtime"} for item in registry["toolchain"].values())
    assert all(item.get("command_id") and item.get("fixed_target") for item in registry["toolchain"].values())
    assert not any("deferred" in json.dumps(item).casefold() or "inventory_only" in json.dumps(item).casefold() for item in registry["toolchain"].values())
    assert toolchain.TOOL_EXECUTION_ORDER.index("syft") < toolchain.TOOL_EXECUTION_ORDER.index("grype")


def test_check_status_uses_only_terminal_toolchain_vocabulary():
    toolchain = _module()
    result = toolchain.check_toolchain()
    assert result["required_status_vocabulary"] == ["READY", "NOT_APPLICABLE", "FAILED"]
    assert len(result["tools"]) == 31
    assert {item["status"] for item in result["tools"]} <= {"READY", "NOT_APPLICABLE", "FAILED"}
    assert all("binary_path" not in item or not str(item["binary_path"]).startswith("/home/") for item in result["tools"])


def test_fixed_runtime_commands_have_no_caller_target_or_argv_inputs(tmp_path: Path, monkeypatch):
    toolchain = _module()
    toolchain.MANAGED_ROOT = tmp_path / "managed"
    toolchain.MANAGED_ROOT.mkdir()
    sni_file = tmp_path / "caddy-sni"
    sni_file.write_text("qualification.example.test\n", encoding="ascii")
    monkeypatch.setattr(toolchain, "TLS_SNI_FILE", sni_file)
    binary = Path(sys.executable)
    command, _ = toolchain._run_command_for_tool("nmap", "deep", binary, tmp_path, toolchain._fixed_env())
    assert command[-1] == toolchain.APPROVED_NMAP_TARGET
    assert command[command.index("-p") + 1] == toolchain.APPROVED_PORTS
    assert toolchain.APPROVED_PORT_FORWARD_MAP == {
        14222: "server_phone_nats_4222",
        18080: "server_phone_api_8080",
        18181: "server_phone_opa_8181",
        18222: "server_phone_nats_monitor_8222",
        18443: "server_phone_caddy_tls_443",
    }
    assert "http://attacker.invalid" not in command
    command, _ = toolchain._run_command_for_tool("testssl.sh", "standard", binary, tmp_path, toolchain._fixed_env())
    assert command[-1] == "qualification.example.test:18443"
    assert command[command.index("--ip") + 1] == "127.0.0.1"
    assert command[-1] == "qualification.example.test:18443"
    displayed = toolchain._display_argv(command)
    assert "qualification.example.test:18443" not in displayed
    assert displayed[-1] == "FIXED_CADDY_TLS_IDENTITY:FIXED_CADDY_TLS_PORT"


    runtime_command, _ = toolchain._run_command_for_tool(
        "pocketlab-runtime-360",
        "adversarial",
        Path(sys.executable),
        tmp_path,
        toolchain._fixed_env(tool_id="pocketlab-runtime-360"),
    )
    assert runtime_command == [
        str(Path(sys.executable)),
        str(toolchain.LIVE_360_SCRIPT),
        "adversarial",
    ]
    assert "attacker.invalid" not in " ".join(runtime_command)

    browser_command, _ = toolchain._run_command_for_tool(
        "playwright-runtime",
        "standard",
        Path("/usr/bin/node"),
        tmp_path,
        toolchain._fixed_env(tool_id="playwright-runtime"),
    )
    assert browser_command == [
        "/usr/bin/node",
        str(toolchain.BROWSER_360_SCRIPT),
        "standard",
    ]


def test_osv_and_zap_use_bounded_structured_artifacts(tmp_path: Path):
    toolchain = _module()
    binary = Path(sys.executable)
    osv_command, osv_artifact = toolchain._run_command_for_tool("osv-scanner", "standard", binary, tmp_path, toolchain._fixed_env())
    assert osv_artifact is not None and osv_artifact.name == "osv.json"
    assert "--output-file" in osv_command
    assert str(osv_artifact) in osv_command
    zap_command, zap_artifact = toolchain._run_command_for_tool("owasp-zap", "deep", binary, tmp_path, toolchain._fixed_env())
    assert zap_artifact is not None and zap_artifact.name == "zap-report.json"
    assert "-quickout" in zap_command
    assert str(zap_artifact) in zap_command
    assert "-silent" in zap_command


def test_structured_zap_alerts_are_normalized_without_raw_details(tmp_path: Path):
    toolchain = _module()
    payload = {
        "site": [{"alerts": [{"alert": "Example alert", "riskcode": "2", "pluginid": "10001", "url": "http://secret.invalid/path"}]}]
    }
    findings = toolchain._parse_findings("owasp-zap", "deep", "", "", tmp_path, artifact_payload=payload)
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "secret.invalid" not in json.dumps(findings[0])
    assert findings[0]["runtime_target"] == "local_server_host_only"


def test_nmap_result_keeps_only_fixed_listener_provenance(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "_live_target_probe", lambda _tool_id: {"available": True, "sanitized": True})
    monkeypatch.setattr(toolchain, "_probe_version", lambda _tool_id, _binary: {"status": "READY", "version": "7.98", "version_status": "verified"})
    monkeypatch.setattr(toolchain, "_run_command_for_tool", lambda *_args: ([sys.executable, "-c", ""], None))
    monkeypatch.setattr(toolchain, "_bounded_run", lambda *_args, **_kwargs: {"status": "PASS", "exit_code": 0, "duration_ms": 1, "stdout": "", "stderr": ""})
    result = toolchain._tool_result(
        "nmap",
        "deep",
        Path(sys.executable),
        tmp_path,
        toolchain._fixed_env(tool_id="nmap"),
    )
    assert result["port_forward_map"] == toolchain.APPROVED_PORT_FORWARD_MAP


def test_gitleaks_uses_a_fixed_excluded_tracked_file_view(tmp_path: Path, monkeypatch):
    toolchain = _module()
    fixed_source = tmp_path / "tracked-only"
    fixed_source.mkdir()
    monkeypatch.setattr(toolchain, "_gitleaks_source", lambda _workspace: fixed_source)
    command, _ = toolchain._run_command_for_tool("gitleaks", "smoke", Path(sys.executable), tmp_path, toolchain._fixed_env())
    assert command[command.index("--source") + 1] == str(fixed_source)
    assert Path(command[command.index("--source") + 1]).resolve() != toolchain.ROOT.resolve()
    assert "--no-git" in command


def test_bounded_runner_terminates_timeout_and_does_not_use_shell(tmp_path: Path, monkeypatch):
    toolchain = _module()
    toolchain.MANAGED_ROOT = tmp_path / "managed"
    calls = []
    real_popen = toolchain.subprocess.Popen

    def capture(*args, **kwargs):
        calls.append(kwargs.get("shell"))
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(toolchain.subprocess, "Popen", capture)
    result = toolchain._bounded_run(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_seconds=1,
        max_output_bytes=4096,
        env=toolchain._fixed_env(),
        cwd=tmp_path,
    )
    assert result["status"] == "PARTIAL"
    assert result["failure_code"] == "timed_out"
    assert calls == [False]


def test_secret_summaries_are_redacted_before_evidence():
    toolchain = _module()
    value = "Authorization: Bearer abc123 password=supersecret -----BEGIN PRIVATE KEY-----bytes-----END PRIVATE KEY-----"
    sanitized = toolchain._sanitize_text(value)
    assert "abc123" not in sanitized
    assert "supersecret" not in sanitized
    assert "BEGIN PRIVATE KEY" not in sanitized
    assert "REDACTED BY SECURITY ASSURANCE POLICY" in sanitized


def test_dependency_findings_corroborate_without_duplicate_identity():
    toolchain = _module()
    first = toolchain._base_finding(
        tool_id="osv-scanner",
        suite_id="deep",
        identity="CVE-2099-0001|demo",
        title="advisory",
        severity="medium",
        summary="bounded advisory",
        component="demo",
    )
    second = dict(first)
    second["tool"] = "grype"
    second["finding_id"] = toolchain._finding_key("grype", "CVE-2099-0001|demo")
    first["advisory_key"] = second["advisory_key"] = "CVE-2099-0001|demo"
    result = toolchain._correlate_findings([first, second])
    assert len(result) == 1
    assert result[0]["corroborating_tools"] == ["grype", "osv-scanner"]
    assert result[0]["confidence"] == "high"


def test_baseline_delta_is_stable_and_only_contains_finding_ids(tmp_path: Path, monkeypatch):
    toolchain = _module()
    toolchain.EVIDENCE_ROOT = tmp_path / "evidence"
    finding = toolchain._base_finding(
        tool_id="bandit",
        suite_id="standard",
        identity="B602|runtime.py|12",
        title="bounded finding",
        severity="low",
        summary="safe summary",
        component="runtime.py",
    )
    first = toolchain._baseline_delta([finding])
    second = toolchain._baseline_delta([finding])
    assert first["new"] == [finding["finding_id"]]
    assert second["existing"] == [finding["finding_id"]]
    stored = json.loads((tmp_path / "evidence/baseline.json").read_text())
    assert set(stored) == {"finding_digest", "finding_ids", "sanitized", "updated_at"}


def test_external_scenario_aggregation_preserves_not_assessed_and_fail_truth():
    toolchain = _module()
    definitions = toolchain._external_scenario_definitions("standard")
    ids = {item["id"] for item in definitions}
    assert "browser-origin-control-plane-bypass" in ids
    assert "owner-session-lifecycle" in ids

    rows = toolchain._aggregate_external_scenarios(
        "standard",
        [
            {
                "tool_id": "playwright-runtime",
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "PASS",
                        "evidence": "fixed browser evidence",
                    },
                    "owner-session-lifecycle": {
                        "status": "NOT_ASSESSED",
                        "evidence": "disposable identity required",
                    },
                },
            },
            {
                "tool_id": "pocketlab-runtime-360",
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "FAIL",
                        "evidence": "fixed runtime evidence",
                    }
                },
            },
        ],
    )
    by_id = {item["scenario_id"]: item for item in rows}
    assert by_id["browser-origin-control-plane-bypass"]["status"] == "FAIL"
    assert by_id["owner-session-lifecycle"]["status"] == "NOT_ASSESSED"


def test_repository_owned_adapters_are_not_promoted_as_scanner_binaries(monkeypatch):
    toolchain = _module()
    checked = {
        "status": "READY",
        "version": "1.0.0",
        "version_status": "verified",
        "checksum_status": "not_managed",
        "signature_status": "not_applicable",
    }
    monkeypatch.setattr(toolchain, "_check_one", lambda tool_id, spec: {"tool_id": tool_id, **checked})
    monkeypatch.setattr(
        toolchain,
        "_candidate",
        lambda tool_id: Path(sys.executable) if tool_id in {"pocketlab-runtime-360", "playwright-runtime"} else None,
    )
    original_registry = toolchain._registry
    registry = original_registry()
    registry["toolchain"] = {
        key: value
        for key, value in registry["toolchain"].items()
        if key in {"pocketlab-runtime-360", "playwright-runtime"}
    }
    monkeypatch.setattr(toolchain, "_registry", lambda: registry)
    result = toolchain.install_toolchain()
    assert result["status"] == "PASS"
    assert {row["action"] for row in result["tools"]} == {"repository_owned_adapter"}


def test_consolidated_expansion_tools_are_registered():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]

    expected = {
        "playwright",
        "mitmdump",
        "hurl",
        "k6",
        "websocat",
        "katana",
        "httpx",
        "tlsx",
        "tshark",
        "ffuf",
        "nats-cli",
        "playwright-runtime",
        "pocketlab-runtime-360",
    }

    assert len(registry) == 31
    assert expected.issubset(registry)


def test_consolidated_high_live_finding_is_scenario_fail():
    toolchain = _module()

    rows = toolchain._aggregate_external_scenarios(
        "standard",
        [
            {
                "tool_id": "playwright",
                "status": "PASS",
                "findings": [
                    {
                        "finding_id": "x",
                        "severity": "high",
                    }
                ],
            },
            {
                "tool_id": "playwright-runtime",
                "status": "PASS",
                "findings": [],
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "PASS",
                        "evidence": "fixed browser observation",
                        "reason": None,
                    }
                },
            },
        ],
    )

    target = next(
        row
        for row in rows
        if row["scenario_id"]
        == "browser-origin-control-plane-bypass"
    )

    assert target["status"] == "FAIL"


def test_webauthn_human_review_never_auto_promotes_to_pass():
    toolchain = _module()

    rows = toolchain._aggregate_external_scenarios(
        "deep",
        [
            {
                "tool_id": "playwright",
                "status": "PASS",
                "findings": [],
            }
        ],
    )

    target = next(
        row
        for row in rows
        if row["scenario_id"]
        == "webauthn-origin-rpid-mismatch"
    )

    assert target["status"] == "PARTIAL"
    assert target["human_review_required"] is True
