from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lite" / "security_assurance_report.py"


def _module():
    spec = importlib.util.spec_from_file_location("security_assurance_report_readability", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_tools():
    return {
        "toolchain": [
            {"id": "bandit", "version_pin": "1.9.4", "version_source": "qualified_tool_receipt"},
            {"id": "trivy", "version_pin": "runtime-reported", "version_source": "registered_security_tool_result"},
            {"id": "opa", "version_pin": "runtime-reported", "version_source": "policy_status"},
        ]
    }


def test_fixed_pin_and_observed_version_are_separate_and_match():
    module = _module()
    tools = module._enrich_tools(
        [{"tool_id": "bandit", "version": "bandit 1.9.4", "status": "PASS"}],
        _canonical_tools(),
        registry_hash_matches=True,
    )
    tool = tools[0]
    assert tool["registered_version_policy"] == "1.9.4"
    assert tool["observed_version"] == "bandit 1.9.4"
    assert tool["registered_version_source"] == "qualified_tool_receipt"
    assert tool["version_state"] == "MATCH"


def test_fixed_pin_mismatch_is_visible():
    module = _module()
    tool = module._enrich_tools(
        [{"tool_id": "bandit", "version": "1.9.3", "status": "PASS"}],
        _canonical_tools(),
        registry_hash_matches=True,
    )[0]
    assert tool["registered_version_policy"] == "1.9.4"
    assert tool["observed_version"] == "1.9.3"
    assert tool["version_state"] == "MISMATCH"


def test_not_run_fixed_tool_keeps_registry_pin_without_faking_observed_version():
    module = _module()
    tool = module._enrich_tools(
        [{"tool_id": "bandit", "status": "NOT_RUN", "finding_count": 0}],
        _canonical_tools(),
        registry_hash_matches=True,
    )[0]
    assert tool["registered_version_policy"] == "1.9.4"
    assert tool["observed_version"] is None
    assert tool["version_state"] == "NOT_OBSERVED"
    assert module._observed_version_display(tool) == "NOT_RUN"


def test_runtime_reported_versions_never_become_fake_pins():
    module = _module()
    trivy, opa = module._enrich_tools(
        [
            {"tool_id": "trivy", "version": "0.68.2", "status": "PASS"},
            {"tool_id": "opa", "status": "PASS"},
        ],
        _canonical_tools(),
        registry_hash_matches=True,
    )
    assert trivy["registered_version_policy"] == "runtime-reported"
    assert trivy["observed_version"] == "0.68.2"
    assert trivy["version_state"] == "RUNTIME_REPORTED"
    assert opa["registered_version_policy"] == "runtime-reported"
    assert opa["observed_version"] is None
    assert opa["version_state"] == "RUNTIME_VERSION_NOT_CAPTURED"


def test_registry_metadata_is_not_mixed_when_hash_does_not_match():
    module = _module()
    tool = module._enrich_tools(
        [{"tool_id": "bandit", "version": "1.9.4", "status": "PASS"}],
        _canonical_tools(),
        registry_hash_matches=False,
    )[0]
    assert tool["registered_version_policy"] is None
    assert tool["registered_version_source"] is None
    assert tool["observed_version"] == "1.9.4"
    assert tool["version_state"] == "REGISTRY_METADATA_UNAVAILABLE"


def test_report_vocabulary_explains_ambiguous_terms():
    module = _module()
    vocabulary = {term: (meaning, does_not_mean) for term, meaning, does_not_mean in module.REPORT_VOCABULARY}
    for term in (
        "PASS", "PARTIAL", "FAIL", "BLOCKED", "CANCELLED", "NOT_RUN", "DEFERRED",
        "UNAVAILABLE", "NOT_APPLICABLE", "HUMAN_REVIEW_REQUIRED", "EVIDENCE_PRESENT",
        "NOT_ASSESSED", "NEW", "EXISTING", "REGRESSED", "RESOLVED", "UNCHANGED",
        "runtime-reported", "Registered version", "Observed version", "MATCH", "MISMATCH",
        "NOT_OBSERVED", "RUNTIME_VERSION_NOT_CAPTURED", "0 findings", "Finding", "Scenario",
        "Tool", "Scenario coverage", "Attack-path coverage", "Tool readiness", "Sanitized evidence",
        "Source SHA / Runtime SHA",
    ):
        assert term in vocabulary
        assert vocabulary[term][0]
        assert vocabulary[term][1]


def test_markdown_places_reader_guide_before_executive_summary_and_explains_tool_versions():
    module = _module()
    tools = module._enrich_tools(
        [
            {"tool_id": "bandit", "status": "NOT_RUN", "finding_count": 0},
            {"tool_id": "trivy", "version": "0.68.2", "status": "PASS", "finding_count": 0},
            {"tool_id": "opa", "status": "PASS", "finding_count": 0},
        ],
        _canonical_tools(),
        registry_hash_matches=True,
    )
    model = {
        "qualification_id": "assurance-" + "a" * 32,
        "report_id": "security-assurance-20260917T000000Z-" + "b" * 10 + "-assurance-" + "a" * 32,
        "generated_at": "2026-09-17T00:00:01Z",
        "source_sha": "b" * 40,
        "runtime_sha": "b" * 40,
        "environment": "qualification",
        "target_scope": "local_server_host_only",
        "profile": "security-assurance-runner",
        "suite": "deep",
        "overall_status": "PARTIAL",
        "registry_hashes": {},
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "baseline_counts": {"NEW": 0, "EXISTING": 0, "REGRESSED": 0, "RESOLVED": 0, "UNCHANGED": 0},
        "metrics": {
            "scenario_coverage_percent": 100.0,
            "scenario_pass_percent": 100.0,
            "attack_path_coverage_percent": 0.0,
            "control_coverage_percent": 0.0,
            "tool_readiness_percent": 66.7,
            "evidence_completeness_percent": 100.0,
            "formula": "fixture",
        },
        "suite_results": {"smoke": "NOT_RUN", "standard": "NOT_RUN", "adversarial": "NOT_RUN", "deep": "PARTIAL"},
        "scenarios": [],
        "tools": tools,
        "findings": [],
        "stride": {},
        "owasp": [],
        "attack_paths": [],
        "controls": [],
        "performance": {},
        "canonical_threat_model": None,
        "out_of_scope": [],
    }
    text = module.render_markdown(model)
    assert text.index("## How to Read This Report") < text.index("## 1. Executive Security Summary")
    assert "`NOT_RUN` means the registered suite or tool did not execute in this qualification" in text
    assert "`0` findings on a `NOT_RUN` tool does not mean the tool scanned and found nothing" in text
    assert "Registered version" in text
    assert "Observed version" in text
    assert "Version state" in text
    assert "bandit | 1.9.4 | NOT_RUN | NOT_OBSERVED" in text
    assert "trivy | runtime-reported | 0.68.2 | RUNTIME_REPORTED" in text
    assert "opa | runtime-reported | UNAVAILABLE | RUNTIME_VERSION_NOT_CAPTURED" in text
