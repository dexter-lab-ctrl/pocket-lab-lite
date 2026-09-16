from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lite" / "security_assurance_report.py"


def _module():
    spec = importlib.util.spec_from_file_location("security_assurance_report", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(*, terminal: bool = True, unsafe_summary: bool = False):
    run_id = "assurance-" + "a" * 32
    sha = "b" * 40
    run = {
        "run_id": run_id,
        "suite_id": "standard",
        "status": "PASS" if terminal else "RUNNING",
        "revision_sha": sha,
        "completed_at": "2026-09-16T00:00:00Z",
    }
    finding = {
        "finding_id": f"{run_id}-finding-1",
        "stable_key": "assurance:fixture",
        "run_id": run_id,
        "suite": "standard",
        "scenario_id": "evidence-redaction",
        "tool": "trivy",
        "category": "security_finding",
        "severity": "medium",
        "title": "Fixture finding",
        "safe_summary": "Authorization: Bearer SHOULD_BE_BLOCKED_123" if unsafe_summary else "Sanitized fixture finding.",
        "component": "Pocket Lab Lite",
        "asset": "registered component",
        "stride": ["Information Disclosure"],
        "owasp": ["A02"],
        "attack_paths": ["AP-06"],
        "controls": ["CTRL-EVIDENCE-SANITIZE"],
        "cwe": [],
        "cve": [],
        "baseline_state": "NEW",
        "status": "open",
        "remediation": "Review the normalized finding.",
        "evidence_refs": ["security/evidence/fixture.json"],
    }
    files = {
        "manifest.json": {
            "schema_version": "1.0.0", "run_id": run_id, "suite": "standard",
            "profile": "security-assurance-runner", "target_scope": "local_server_host_only",
            "revision_sha": sha, "status": "PASS", "sanitized": True,
            "registry": {"registry_hashes": {"tools": "sha256:fixture-tools", "suites": "sha256:fixture-suites", "scenarios": "sha256:fixture-scenarios", "threat_model": "sha256:fixture-threat"}},
        },
        "environment.json": {"qualification_environment": True, "sanitized": True},
        "toolchain.json": {"tools": [{"tool_id": "trivy", "status": "PASS", "version": "fixture", "execution_lane": "server_phone_worker", "finding_count": 1, "duration_ms": 10}], "sanitized": True},
        "findings.json": {"findings": [finding], "sanitized": True},
        "threat-coverage.json": {
            "framework": "STRIDE", "scenario_count": 1,
            "by_category": {"Information Disclosure": {"PASS": 1, "FAIL": 0, "PARTIAL": 0, "BLOCKED": 0}},
            "scenarios": [{"scenario_id": "evidence-redaction", "status": "PASS", "stride": ["Information Disclosure"], "owasp": ["A02"], "attack_paths": ["AP-06"], "controls": ["CTRL-EVIDENCE-SANITIZE"]}],
            "sanitized": True,
        },
        "owasp-coverage.json": {"version": "2021", "categories": [{"id": "A02", "name": "Cryptographic Failures", "scenario_count": 1, "passing_scenarios": 1}], "sanitized": True},
        "attack-path-results.json": {"status": "PASS", "paths": [{"attack_path_id": "AP-06", "name": "Evidence poisoning", "classification": "EXECUTABLE_NOW", "status": "PASS", "reason": "fixture", "human_review_required": False, "stride": ["Information Disclosure"], "owasp": ["A02"], "controls": ["CTRL-EVIDENCE-SANITIZE"]}], "sanitized": True},
        "controls.json": {"controls": [{"control_id": "CTRL-EVIDENCE-SANITIZE", "scenario_ids": ["evidence-redaction"], "attack_paths": ["AP-06"], "status": "PASS"}], "sanitized": True},
        "delta.json": {"baseline_available": False, "counts": {"NEW": 1}, "new_finding_count": 1, "sanitized": True},
        "performance.json": {"started_at": "2026-09-15T23:59:59Z", "completed_at": "2026-09-16T00:00:00Z", "duration_ms": 1000, "resource_start": {}, "resource_finish": {}, "sanitized": True},
        "sanitization.json": {
            "sanitized": True, "raw_scanner_output_persisted": False,
            "raw_credentials_persisted": False, "session_tokens_persisted": False,
            "key_material_persisted": False, "authorization_headers_persisted": False,
            "user_media_scanned": False, "backup_payloads_scanned": False,
            "evidence_policy": "normalized_and_redacted",
        },
        "checksums.json": {"schema_version": "1.0.0", "files": {}, "algorithm": "sha256", "sanitized": True},
        "summary.md": "# Sanitized fixture summary\n",
    }
    return run, {"available": True, "run_id": run_id, "files": files, "sanitized": True}


def test_report_model_has_deterministic_identity_and_all_findings():
    module = _module()
    run, report = _fixture()
    model = module.build_model(run, report)
    assert model["report_id"] == f"security-assurance-20260916T000000Z-{'b' * 10}-{run['run_id']}"
    assert model["qualification_id"] == run["run_id"]
    assert len(model["findings"]) == 1
    assert model["severity_counts"]["medium"] == 1
    assert model["baseline_counts"]["NEW"] == 1
    assert model["overall_status"] == "PASS"


def test_non_terminal_and_invalid_qualification_are_rejected():
    module = _module()
    run, report = _fixture(terminal=False)
    with pytest.raises(module.ReportError, match="not terminal"):
        module.build_model(run, report)
    with pytest.raises(module.ReportError, match="invalid qualification"):
        module._safe_id("../../etc/passwd")


def test_missing_or_unsafe_sanitization_blocks_publication_source():
    module = _module()
    run, report = _fixture()
    del report["files"]["findings.json"]
    with pytest.raises(module.ReportError, match="incomplete"):
        module.build_model(run, report)
    run, report = _fixture()
    report["files"]["sanitization.json"]["raw_scanner_output_persisted"] = True
    with pytest.raises(module.ReportError, match="sanitization marker"):
        module.build_model(run, report)


def test_publish_is_atomic_indexed_and_idempotent(tmp_path: Path):
    module = _module()
    run, report = _fixture()
    model = module.build_model(run, report)
    first = module.publish_model(model, tmp_path)
    assert first["status"] == "published"
    report_id = model["report_id"]
    assert (tmp_path / f"{report_id}.md").is_file()
    assert (tmp_path / f"{report_id}.json").is_file()
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert f"({report_id}.md)" in index
    second = module.publish_model(model, tmp_path)
    assert second["status"] == "idempotent"
    assert module.check_published(run["run_id"], tmp_path)["status"] == "PASS"


def test_redaction_failure_blocks_report_publish(tmp_path: Path):
    module = _module()
    run, report = _fixture(unsafe_summary=True)
    model = module.build_model(run, report)
    with pytest.raises(module.ReportError, match="redaction validation blocked"):
        module.publish_model(model, tmp_path)
    assert not list(tmp_path.glob("security-assurance-*.md"))
    assert not list(tmp_path.glob("security-assurance-*.json"))


def test_index_is_deterministic(tmp_path: Path):
    module = _module()
    run, report = _fixture()
    model = module.build_model(run, report)
    module.publish_model(model, tmp_path)
    before = (tmp_path / "index.md").read_text(encoding="utf-8")
    module.rebuild_index(tmp_path)
    after = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert before == after


def test_markdown_contains_required_sections_and_reconciled_counts():
    module = _module()
    run, report = _fixture()
    model = module.build_model(run, report)
    text = module.render_markdown(model)
    for heading in (
        "## 1. Executive Security Summary", "## 2. Qualification Identity",
        "## 3. Overall Assurance Verdict", "## 4. Security Confidence / Assurance Metrics",
        "## 5. Finding Counts", "## 6. Severity Chart", "## 7. Findings by Tool",
        "## 8. Findings by Suite", "## 9. Complete Finding Register", "## 10. STRIDE Matrix",
        "## 11. OWASP Top 10 Matrix", "## 12. Attack-Path Matrix", "## 13. Toolchain Matrix",
        "## 14. Runtime / Resource Metrics", "## 15. Security Architecture", "## 16. Trust Boundaries",
        "## 17. Controls Validated", "## 18. Human Review Required", "## 19. Out of Scope",
        "## 20. Remediation Priorities", "## 21. Retest Plan", "## 22. Sanitization Statement",
    ):
        assert heading in text
    assert "Fixture finding" in text
    assert "Medium | 1" in text
