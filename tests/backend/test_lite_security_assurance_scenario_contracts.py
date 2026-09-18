from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "security" / "assurance" / "scenarios.yaml"
SUITES = ROOT / "security" / "assurance" / "suites.yaml"
TOOLS = ROOT / "security" / "assurance" / "tools.yaml"
THREAT = ROOT / "security" / "threat-model-scenarios.json"
ROUTER = ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "routers" / "security_assurance.py"

STRIDE = {"Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"}
OWASP = {f"A{i:02d}" for i in range(1, 11)}
SAFETY = {"PASSIVE", "SAFE_ACTIVE", "CONTROLLED_MUTATION", "DESTRUCTIVE_QUALIFICATION"}
EXECUTIONS = {
    "configuration_posture",
    "authenticated_admission_posture",
    "fixed_caddy_probe",
    "fixed_local_health_probe",
    "worker_execution_receipt",
    "redaction_contract",
    "existing_security_projection",
    "existing_opa_status",
    "bounded_source_assertions",
    "fixed_negative_auth_probes",
    "canonical_threat_model_check",
    "attack_path_inventory",
    "dev_pc_live_runtime_evidence",
}
LIFECYCLE = {
    "precondition", "action", "expected_invariant", "pass_condition", "fail_condition",
    "blocked_condition", "cleanup", "normalized_evidence",
}


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _threat():
    import json
    return json.loads(THREAT.read_text(encoding="utf-8"))


def test_registry_scenarios_have_unique_fixed_lifecycle_contracts():
    payload = _yaml(SCENARIOS)
    scenarios = payload["scenarios"]
    ids = [item["id"] for item in scenarios]
    assert len(ids) == len(set(ids))
    suites = set(_yaml(SUITES)["profiles"])
    threat = _threat()
    ap_ids = {item["id"] for item in threat["attack_paths"]}
    controls = {item["id"] for item in threat["controls"]}
    for path in threat["attack_paths"]:
        controls.update(
            str(value).strip()
            for value in path.get("controls", [])
            if str(value).strip()
        )
    case_ids: set[str] = set()
    for scenario in scenarios:
        assert scenario["execution"] in EXECUTIONS
        assert scenario["safety_class"] in SAFETY
        assert str(scenario["required_capability"]).startswith("security.assurance.")
        assert set(scenario["suites"]).issubset(suites)
        assert set(scenario["stride"]).issubset(STRIDE)
        assert set(scenario["owasp"]).issubset(OWASP)
        assert set(scenario["attack_paths"]).issubset(ap_ids)
        assert set(scenario["controls"]).issubset(controls)
        assert LIFECYCLE.issubset(scenario)
        assert all(str(scenario[key]).strip() for key in LIFECYCLE)
        for case in scenario.get("coverage_cases", []):
            case_id = str(case["id"])
            assert re.fullmatch(r"[a-z][a-z0-9._-]{2,79}", case_id)
            assert case_id not in case_ids
            case_ids.add(case_id)
            assert str(case["threat"]).strip()
            assert str(case["expected_invariant"]).strip()
    assert len(case_ids) >= 35


def test_all_suite_scenario_references_exist_and_safety_classes_are_allowed():
    scenario_map = {item["id"]: item for item in _yaml(SCENARIOS)["scenarios"]}
    for suite_id, suite in _yaml(SUITES)["profiles"].items():
        allowed = set(suite["allowed_safety_classes"])
        phone = set(suite["scenarios"])
        dev_pc = set(suite.get("dev_pc_scenarios", []))
        assert phone.isdisjoint(dev_pc)
        for scenario_id in phone:
            assert scenario_id in scenario_map, (suite_id, scenario_id)
            assert scenario_map[scenario_id]["safety_class"] in allowed
        for scenario_id in dev_pc:
            assert scenario_id in scenario_map, (suite_id, scenario_id)
            assert scenario_map[scenario_id]["safety_class"] in allowed
            assert scenario_map[scenario_id]["execution"] == "dev_pc_live_runtime_evidence"
            assert suite_id in scenario_map[scenario_id]["suites"]


def test_caller_request_model_has_no_arbitrary_execution_inputs():
    text = ROUTER.read_text(encoding="utf-8")
    request_block = text.split("class AssuranceRunRequest", 1)[1].split("class FaultControlRequest", 1)[0]
    assert 'ConfigDict(extra="forbid")' in request_block
    assert "suite_id:" in request_block
    assert "scenario_id:" in request_block
    assert "baseline_run_id:" in request_block
    for forbidden in ("url:", "method:", "target:", "port:", "argv:", "subject:", "template:", "rule:", "path:", "host:"):
        assert forbidden not in request_block


def test_tool_backed_scenarios_remain_fixed_and_bounded():
    tools = {item["id"]: item for item in _yaml(TOOLS)["toolchain"]}
    nuclei = tools["nuclei"]
    assert nuclei["execution_lane"] == "dev_pc_live_runtime"
    assert nuclei["fixed_target"] == "approved_server_phone_api_tunnel"
    assert nuclei["template_allowlist"] == "security/assurance/nuclei-safe-templates"
    assert nuclei["ruleset"] == "security/assurance/nuclei-safe-templates"
    assert "-templates" in nuclei["fixed_argv"]
    nmap = tools["nmap"]
    assert nmap["fixed_target"] == "approved_loopback_listener_set"
    joined_nmap = " ".join(nmap["fixed_argv"])
    assert "127.0.0.1" in joined_nmap
    assert "-p-" not in joined_nmap
    zap = tools["owasp-zap"]
    assert zap["execution_lane"] == "dev_pc_live_runtime"
    assert zap["suite_membership"] == ["deep"]
    assert zap["ruleset"] == "fixed_api_baseline_profile"
    assert zap["template_allowlist"] == "fixed_safe_api_routes"
    schemathesis = tools["schemathesis"]
    assert "get_only" in schemathesis["fixed_argv"]
    assert schemathesis["template_allowlist"] == "safe_get_routes_only"
    testssl = tools["testssl.sh"]
    assert testssl["fixed_target"] == "approved_server_phone_caddy_tls_tunnel"
    assert "--fast" in testssl["fixed_argv"]


def test_scenario_evidence_tool_references_are_registered():
    tools = {item["id"] for item in _yaml(TOOLS)["toolchain"]}
    for scenario in _yaml(SCENARIOS)["scenarios"]:
        assert set(scenario.get("evidence_tools", [])).issubset(tools)


def test_360_runtime_expansion_is_fixed_and_dev_pc_owned():
    tools = {item["id"]: item for item in _yaml(TOOLS)["toolchain"]}
    expected = {
        "playwright", "mitmdump", "hurl", "k6", "websocat", "katana",
        "httpx", "tlsx", "tshark", "ffuf", "nats-cli",
    }
    assert len(tools) == 29
    assert expected.issubset(tools)
    for tool_id in expected:
        item = tools[tool_id]
        assert item["execution_lane"] == "dev_pc_live_runtime"
        assert item["harness_status"] == "ACTIVE"
        assert item["allowed_mode"] == "fixed_registered_command"
        assert item["fixed_target"] in {
            "approved_server_phone_api_tunnel",
            "approved_server_phone_caddy_tls_tunnel",
            "approved_loopback_listener_set",
        }
        rendered = " ".join(item["fixed_argv"]).casefold()
        for forbidden in ("caller_url", "caller_host", "caller_port", "caller_argv", "caller_subject"):
            assert forbidden not in rendered

    profiles = _yaml(SUITES)["profiles"]
    assert len(profiles["standard"]["dev_pc_scenarios"]) == 18
    assert len(profiles["deep"]["dev_pc_scenarios"]) == 32
    assert len(profiles["adversarial"]["dev_pc_scenarios"]) == 27
    assert profiles["smoke"]["dev_pc_scenarios"] == []


def test_runtime_probe_cli_has_no_arbitrary_target_options():
    probe = (ROOT / "scripts/dev/lite/security_assurance_runtime_probe.py").read_text(encoding="utf-8")
    assert 'choices=("websocket","mitmproxy","tshark","nats","tailnet")' in probe
    for forbidden in ('add_argument("--url"', 'add_argument("--host"', 'add_argument("--port"', 'add_argument("--argv"', 'add_argument("--subject"'):
        assert forbidden not in probe

    config = (ROOT / "playwright.security.config.ts").read_text(encoding="utf-8")
    assert "LITE_BASE_URL" not in config
    assert "caddy-sni" in config
    assert "--host-resolver-rules=MAP" in config
