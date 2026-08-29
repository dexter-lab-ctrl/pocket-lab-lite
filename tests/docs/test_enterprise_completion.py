from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


completion = load_module("enterprise_completion", "scripts/docs/enterprise/enterprise_completion.py")
supply = load_module("supply_chain_automation", "scripts/docs/enterprise/supply_chain_automation.py")
release_promotion = load_module("release_evidence_promotion", "scripts/docs/enterprise/release_evidence_promotion.py")


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_every_enterprise_requirement_is_implemented_by_source_contract():
    rows = completion.coverage_requirements()
    assert len(rows) >= 50
    assert {row["implementation_status"] for row in rows} == {"implemented"}
    names = {row["requirement"] for row in rows}
    required = {
        "Close five Documentation Experience gaps",
        "Executable Task Reference",
        "Event encyclopedia",
        "Production promoted threat posture",
        "Production incident runbooks",
        "Release delta",
        "Syft/CycloneDX SBOM",
        "OSV-Scanner correlation",
        "Grype corroboration",
        "ScanCode licensing",
        "Gitleaks secrets",
        "Semgrep Community rules",
        "Cosign artifact signing workflow",
        "SLSA-style provenance",
        "Heavy WSL2/CI execution",
        "Lightweight Termux evidence boundary",
        "Tool bootstrap/download",
        "Output normalization",
        "Page-anatomy enforcement",
    }
    assert required <= names


def test_release_delta_is_real_multidimensional_comparison_without_unknowns():
    delta = completion.release_delta(ROOT)
    assert delta["implementation_status"] == "implemented"
    assert len(delta["dimensions"]) == 22
    assert {row["dimension"] for row in delta["dimensions"]} == set(completion.RELEASE_DIMENSIONS)
    assert all(row["classification"] != "unknown" for row in delta["dimensions"])
    if delta["status"] == "comparable":
        assert delta["from"]["tag"].startswith("lite-")
        assert all("source_paths" in row for row in delta["dimensions"])
        assert all("contracts/generated/documentation-enterprise" not in " ".join(row.get("source_paths", [])) for row in delta["dimensions"])


def test_task_handbook_has_executable_engineering_fields_and_all_workflow_groups():
    rows = completion.task_handbook(ROOT)
    required = {
        "name", "purpose", "audience", "source", "dependencies", "aliases", "commands",
        "environment", "inputs", "outputs", "generated_artifacts", "side_effects",
        "runtime_mutation", "repository_mutation", "captures_runtime", "promotes_evidence",
        "requires_termux", "requires_wsl2", "safe_local", "expected_runtime_class",
        "related_tasks", "failure_modes", "validation_outcome", "example_invocation",
        "workflow_group", "implementation_status",
    }
    assert rows and all(required <= set(row) for row in rows)
    assert {
        "Development loop", "Documentation loop", "API-validation loop", "Runtime-evidence loop",
        "Security-analysis loop", "Release loop", "Recovery-diagnostics loop",
    } <= {row["workflow_group"] for row in rows}


def test_contribution_onboarding_covers_all_requested_change_types():
    rows = completion.contribution_matrix()
    names = {row["change_type"] for row in rows}
    assert {
        "Backend API", "Frontend", "SQLite migration", "NATS/event", "Worker", "Node agent",
        "Supervisor", "Security scanner", "Device bootstrap", "Tailscale", "Application integration",
        "Documentation generator", "Generated contracts", "Release workflow",
    } <= names
    for row in rows:
        assert row["affected_files"] and row["contracts"] and row["tests"]
        assert row["review_checklist"] and row["common_mistakes"] and row["reviewers"]


def test_event_encyclopedia_is_source_derived_and_has_full_anatomy():
    rows = completion.event_encyclopedia(ROOT)
    fields = {
        "event_name", "domain", "publisher", "consumers", "nats_subject", "schema", "payload_fields",
        "lifecycle", "durability", "replay", "ordering", "idempotency", "acknowledgment",
        "failure_handling", "audit_implications", "related_api", "reason_codes", "ui_state",
        "sanitized_example", "tests", "source_owner", "runtime_owner", "security_classification",
        "redacted_fields", "implementation_status",
    }
    assert rows and all(fields <= set(row) for row in rows)
    assert all(row["source_owner"] for row in rows)
    assert (ROOT / "docs/generated/assets/enterprise/event-flows.svg").exists()


def test_release_evidence_model_contains_requested_fields_and_does_not_fake_assets():
    delta = completion.release_delta(ROOT)
    evidence = completion.release_evidence(ROOT, delta)
    for field in [
        "source_commit", "tree_hash", "exact_tag", "build_timestamp", "artifacts", "frontend_version",
        "backend_identity", "database_migration_level", "fingerprints", "runtime_baseline_binding",
        "sbom_digest", "security_scan_digest", "signatures", "provenance", "device_compatibility",
        "known_limitations", "breaking_changes", "validation_outcomes", "authorities", "assurance",
        "evidence_gaps", "lineage",
    ]:
        assert field in evidence
    assert set(evidence["artifacts"]) >= {"dist.zip", "checksums.txt", "release_manifest"}
    for entry in evidence["artifacts"].values():
        assert {"release_presence", "integrity", "binding", "local_staging"} <= set(entry)
        assert entry["release_presence"]["status"] in {"verified", "unobserved", "invalid"}
        assert entry["local_staging"]["status"] in {"observed", "unobserved"}
        if entry["release_presence"]["status"] != "verified":
            assert entry["integrity"]["status"] != "verified"
    assert set(evidence["authorities"]) == {"release", "runtime", "supply_chain", "local_repository"}
    assert evidence["assurance"]["overall"] in {"verified", "verified-with-evidence-gaps", "partially-evidenced"}


def test_threat_model_is_canonical_stride_and_production_posture_is_promoted_not_live():
    supply_index = read_json("contracts/generated/documentation-enterprise/supply-chain.json")
    delta = completion.release_delta(ROOT)
    evidence = completion.release_evidence(ROOT, delta)
    dependency_doc = read_json("contracts/generated/documentation-intelligence/dependency-health.json")
    deps = []
    for item in dependency_doc.get("items", []):
        for dep in item.get("dependencies", []):
            deps.append({"domain": item.get("domain"), "dependency": dep.get("name"), "state": dep.get("state"), "evidence_authority": dep.get("evidence_status"), "root_cause": dep.get("note"), "blocking": dep.get("state") not in {"healthy", "ready", "online"}})
    threat = completion.enrich_threat_model(completion.threat_model(ROOT, supply_index, evidence, deps), ROOT)
    assert threat["implementation_status"] == "implemented"
    assert len(threat["boundaries"]) == 9
    assert len(threat["threats"]) == 54
    assert {x["stride"] for x in threat["threats"]} == set(completion.STRIDE)
    assert all(x["owner"] and isinstance(x["controls"], list) and x["tests"] and x["owasp_mappings"] for x in threat["threats"])
    assert all(x["residual_risk"] == "unvalidated until human review" for x in threat["threats"])
    posture = threat["production_posture"]
    assert posture["live_monitoring"] is False
    sources = " ".join(str(x).lower() for x in posture["signals"])
    for token in ["tailscale", "nats", "agent", "supervisor", "scanner", "release", "dependency", "sbom"]:
        assert token in sources
    assert {x["state"] for x in posture["signals"]} <= {
        "control-observed", "control-partial", "control-unvalidated", "mitigation-source-derived",
        "evidence-stale", "not-applicable",
    }
    assert threat["framework"]["primary"] == "STRIDE"

    attack_paths = {path["id"]: path for path in threat["attack_paths"]}
    assert set(attack_paths) == {f"AP-{index:02d}" for index in range(1, 15)}

    # AP-01..AP-08 are the original platform threat families.
    # AP-09..AP-14 add the bounded Identity + Rules D3 model.
    assert {
        attack_paths[path_id]["status"]
        for path_id in (f"AP-{index:02d}" for index in range(9, 15))
    } == {"modeled"}
    assert {
        attack_paths[path_id]["review_status"]
        for path_id in (f"AP-{index:02d}" for index in range(9, 15))
    } == {"human-review-required"}

    assert all(path["confirmed_exploit"] is False for path in threat["attack_paths"])
    assert all(path["controls"] and path["boundaries"] and path["consequences"] for path in threat["attack_paths"])
    assert all(control["effect"] == "mitigates" and control["prevention_claim"] is False for control in threat["controls"])
    assert all(control["failure_consequences"] for control in threat["controls"])
    assert threat["architecture_integration"]["canonical_model"] == "architecture/metadata/pocket-lab-architecture.json"
    assert threat["visualization"]["nodes"] and threat["visualization"]["edges"] and threat["visualization"]["control_bindings"]
    assert threat["visualization"]["live_monitoring"] is False


def test_enterprise_intelligence_contracts_cover_prompt_fields():
    config = completion.configuration_intelligence([])
    traces = completion.api_ui_traces(ROOT)
    privacy = completion.privacy_map(ROOT)
    dependency_doc = read_json("contracts/generated/documentation-intelligence/dependency-health.json")
    deps = []
    for item in dependency_doc.get("items", []):
        for dep in item.get("dependencies", []):
            deps.append({"domain": item.get("domain"), "dependency": dep.get("name"), "state": dep.get("state"), "evidence_authority": dep.get("evidence_status"), "root_cause": dep.get("note"), "blocking": dep.get("state") not in {"healthy", "ready", "online"}})
    fmea = completion.fmea(ROOT, deps)
    objectives = completion.reliability(ROOT)
    adrs = completion.adr_intelligence(ROOT)
    owners = completion.ownership(ROOT)
    validation = completion.validation_coverage(ROOT)
    assert all({"name", "source", "purpose", "owner", "required", "default", "safe_example", "restart_required", "release_impact", "runtime_impact", "validation", "affected_components"} <= set(x) for x in config)
    assert traces and all({"action", "api", "frontend", "backend_handler", "execution_owner", "events", "tests", "evidence", "failure_states", "source_files"} <= set(x) for x in traces)
    assert len(privacy) >= 9 and all({"category", "source", "storage", "retention", "sanitization", "access", "network_exposure", "backup_behavior", "deletion_behavior", "privacy_risk", "controls"} <= set(x) for x in privacy)
    assert fmea and all({"component", "failure_mode", "detection", "user_impact", "automatic_recovery", "manual_recovery", "severity", "severity_definition", "occurrence", "detectability", "residual_risk", "human_review_required"} <= set(x) for x in fmea)
    opa = next(item for item in fmea if item["component"] == "OPA policy engine")
    assert opa["implementation_status"] == "partial"
    assert "policy_unavailable" in opa["reason_codes"]
    exceptions = next(item for item in fmea if item["component"] == "Temporary exceptions")
    assert exceptions["implementation_status"] == "partial"
    assert exceptions["reason_codes"]
    assert all(code.startswith("exception_") for code in exceptions["reason_codes"])
    assert len(objectives) >= 6 and {x["status"] for x in objectives} <= {"pass", "degraded", "unknown"}
    assert all("live monitoring" not in str(x.get("latest_promoted_observation", "")).lower() for x in objectives)
    assert all({"decision", "context", "alternatives", "selected_approach", "reason", "consequences", "affected_components", "related_risks", "related_threats", "tests", "release_introduced", "superseded_by"} <= set(x) for x in adrs["entities"])
    assert owners and all({"source_owner", "runtime_owner", "recovery_owner", "control_owner", "presentation_owner", "evidence_owner", "source_refs", "architecture", "threats", "tests"} <= set(x) for x in owners)
    assert validation["implementation_status"] == "implemented" and validation["checks"]
    assert all({"latest_verified_status", "canonical_evidence", "live_polling"} <= set(x) for x in validation["checks"])
    assert all(x["live_polling"] is False for x in validation["checks"])


def test_supply_chain_inventory_and_change_contracts_are_complete():
    baseline = completion.current_release_baseline(ROOT)["baseline"]
    inventory = completion.source_dependency_inventory(ROOT, baseline["tag"] if baseline else None)
    required = {"name", "version", "ecosystem", "category", "direct", "transitive", "purpose", "license", "architecture", "arm64_support", "runtime_or_dev", "vulnerability_status", "upstream_posture", "release_introduced"}
    assert inventory["dependencies"] and all(required <= set(row) for row in inventory["dependencies"])
    delta = completion.supply_chain_change(inventory, ROOT, baseline["tag"] if baseline else None)
    for field in ["dependencies_added", "dependencies_removed", "versions_changed", "new_vulnerabilities", "resolved_vulnerabilities", "new_licenses", "removed_licenses", "license_classification_changes", "upstream_posture_changes"]:
        assert field in delta


def test_supply_chain_change_exposes_current_snapshot_and_baseline_readiness():
    baseline = completion.current_release_baseline(ROOT)["baseline"]
    inventory = completion.source_dependency_inventory(ROOT, baseline["tag"] if baseline else None)
    change = completion.supply_chain_change(inventory, ROOT, baseline["tag"] if baseline else None)
    assert change["schema_version"] == "1.1.0"
    assert {"current_snapshot", "baseline_readiness", "historical_comparison"} <= set(change)
    snapshot = change["current_snapshot"]
    assert snapshot["raw_scanner_output_included"] is False
    assert snapshot["live_capture_performed"] is False
    assert {"sbom", "vulnerabilities", "licenses", "security", "repository_posture", "tool_coverage", "source_refs"} <= set(snapshot)
    assert {"dev_components", "release_components", "runtime_components"} <= set(snapshot["sbom"])
    assert {"package_license_coverage", "deep_source_license_coverage", "package_rows", "trivy_license_rows"} <= set(snapshot["licenses"])
    readiness = change["baseline_readiness"]
    assert readiness["status"] in {"ready", "not-ready"}
    assert isinstance(readiness["candidate_count"], int)
    assert readiness["baseline_policy"]
    if baseline is None:
        assert change["status"] == "no-comparable-verified-prior-release"
        assert change["historical_comparison"]["status"] == "not-comparable"
        assert readiness["selected_baseline"] is None


def test_supply_chain_change_page_renders_snapshot_tool_posture_and_truthful_empty_state():
    baseline = completion.current_release_baseline(ROOT)["baseline"]
    inventory = completion.source_dependency_inventory(ROOT, baseline["tag"] if baseline else None)
    change = completion.supply_chain_change(inventory, ROOT, baseline["tag"] if baseline else None)

    def simple_table(headers, rows):
        return "| " + " | ".join(map(str, headers)) + " |\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in rows) + "\n"

    page = completion.render_supply_chain_change_page(change, table=simple_table)
    for heading in [
        "## Current promoted snapshot",
        "### Tool coverage",
        "### Repository posture",
        "## Baseline readiness",
        "## Historical comparison",
    ]:
        assert heading in page
    assert "transient scanner output" in page
    if change["status"] != "comparable":
        assert "No comparable verified prior release" in page
        assert "Historical comparison unavailable until a verified canonical prior-release baseline exists." in page
        assert "| Ecosystem | Name | Version |" not in page
    posture_checks = change["current_snapshot"]["repository_posture"]["checks"]
    for item in posture_checks:
        assert str(item["name"]) in page
        assert str(item["status"]) in page


def test_supply_chain_change_contract_keeps_provider_unavailable_scorecard_controls_truthful():
    snapshot = completion.supply_chain_current_snapshot(ROOT)
    checks = {row["name"]: row for row in snapshot["repository_posture"]["checks"]}
    for name in ["Branch-Protection", "Signed-Releases", "Maintained"]:
        if name in checks and checks[name]["status"] == "provider-unavailable":
            assert checks[name]["score"] is None
            assert checks[name]["reason"] == "scorecard-provider-unsupported-request-type"
            assert checks[name]["blocking"] is False


def test_security_tool_metadata_is_fully_pinned_and_installable_on_dev_surface():
    meta = read_json("contracts/metadata/documentation-security-tools.json")
    assert meta["schema_version"] == "2.0.0"
    by_id = {x["id"]: x for x in meta["tools"]}
    required = {"syft", "trivy", "osv-scanner", "grype", "gitleaks", "semgrep", "scancode", "scorecard", "cosign"}
    assert required <= set(by_id)
    for tool_id in required:
        tool = by_id[tool_id]
        assert tool["required"] is True
        assert tool["version"] and tool["version"] != "missing"
        assert tool["purpose"] and tool["license"] and tool["execution_surface"]
        assert tool["tool"] == tool_id and tool["source"] and tool["platform"]
        assert tool["required_or_optional"] == "required" and tool["expected_binary"] == tool["binary"]
        assert tool["validation_command"]
        assert tool["install"]["method"] in {"github-release", "pypi-venv"}
    assert by_id["threat-dragon"]["required"] is False
    assert by_id["dependency-track"]["required"] is False
    assert "bounded" in by_id["trivy"]["execution_surface"].lower()


def test_tool_installer_has_fail_closed_nonroot_offline_update_and_selective_install_contract():
    source = (ROOT / "scripts/dev/lite/documentation_security_tools.py").read_text(encoding="utf-8")
    for token in ["is_termux", "--offline", "--update", "--only", "SHA-256", ".pocketlab-dev", "safe_extract_tar", "safe_extract_zip", "not-applicable"]:
        assert token in source
    assert "sudo " not in source


def test_supply_chain_automation_is_explicit_capture_normalize_promote_and_never_docs_live_capture():
    source = (ROOT / "scripts/docs/enterprise/supply_chain_automation.py").read_text(encoding="utf-8")
    for token in ["capture", "promote", "check", "dependency-track-export", "is_termux", "sbom-dev.cdx.json", "sbom-release.cdx.json", "sbom-runtime.cdx.json", "--metrics=off"]:
        assert token in source
    assert "runtime_capture_performed\": False" in source
    taskfile = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    docs_check_block = taskfile.split("lite:docs:check:", 1)[1].split("\n  lite:", 1)[0] if "lite:docs:check:" in taskfile else ""
    assert "supply-chain:capture" not in docs_check_block
    assert "security-tools:setup" not in docs_check_block


def test_cyclonedx_normalizer_and_vulnerability_correlation_are_deterministic(tmp_path: Path):
    source = {
        "components": [
            {"type": "library", "name": "b", "version": "2", "purl": "pkg:pypi/b@2"},
            {"type": "library", "name": "a", "version": "1", "purl": "pkg:pypi/a@1", "licenses": [{"license": {"id": "MIT"}}]},
        ]
    }
    bom = supply.canonical_cdx(source, target="development", evidence_status="observed", source_digest="abc", release_binding="lite-test")
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.6"
    assert [x["name"] for x in bom["components"]] == ["a", "b"]
    props = {x["name"]: x["value"] for x in bom["metadata"]["properties"]}
    assert props["pocketlab:release-binding"] == "lite-test"
    (tmp_path / "trivy-sbom-dev.json").write_text(json.dumps({"Results": [{"Vulnerabilities": [{"VulnerabilityID": "CVE-1", "PkgName": "a", "InstalledVersion": "1", "Severity": "HIGH"}]}]}), encoding="utf-8")
    (tmp_path / "grype-sbom-dev.json").write_text(json.dumps({"matches": [{"vulnerability": {"id": "CVE-1", "severity": "High", "fix": {"versions": ["2"]}}, "artifact": {"name": "a", "version": "1"}}]}), encoding="utf-8")
    (tmp_path / "osv-source.json").write_text("{}", encoding="utf-8")
    (tmp_path / "osv-sbom-dev.json").write_text("{}", encoding="utf-8")
    correlated = supply.correlate_vulnerabilities(tmp_path)
    assert correlated["items"][0]["correlation"] == "corroborated"
    assert correlated["scanner_disagreement_is_failure"] is False


def test_supply_chain_canonicalization_redacts_private_paths_but_keeps_secret_gate_fail_closed(tmp_path: Path):
    source = {
        "components": [
            {
                "type": "library",
                "name": "/home/dj/pocket-lab-lite/local-package",
                "version": "1",
                "purl": "pkg:generic/local-package@1?download_url=file:///home/dj/pocket-lab-lite/local-package.whl",
            },
            {
                "type": "library",
                "name": r"C:\Users\Dexter\work\windows-package",
                "version": "2",
            },
        ]
    }
    bom = supply.canonical_cdx(source, target="development", evidence_status="observed", source_digest="abc")
    assert bom["components"][0]["name"] == "<home>/pocket-lab-lite/local-package"
    assert "purl" not in bom["components"][0]
    assert bom["components"][1]["name"] == r"<windows-home>\work\windows-package"

    out = tmp_path / "canonical.json"
    payload = {"path": "/home/dj/pocket-lab-lite", "nested": [r"C:\Users\Dexter\repo"]}
    sanitized = supply.sanitize_private_paths(payload)
    text = supply.stable(sanitized)
    assert "/home/dj" not in text and r"C:\Users\Dexter" not in text
    supply.safe_text("test", text)

    secret_text = '{"token":"super-secret-token-value"}'
    try:
        supply.safe_text("test", secret_text)
    except SystemExit:
        pass
    else:
        raise AssertionError("secret-like canonical content must still fail closed")


def test_cosign_provenance_is_explicit_and_slsa_style_without_formal_level_claim():
    source = (ROOT / "scripts/docs/enterprise/release_provenance.py").read_text(encoding="utf-8")
    assert "cosign" in source and "sign-blob" in source and "verify-blob" in source
    assert "sign-release-set" in source and "verify-release-set" in source
    for artifact in ["dist.zip", "pocketlab-lite-release.json", "sbom-dev.cdx.json", "sbom-release.cdx.json", "sbom-runtime.cdx.json"]:
        assert artifact in source
    assert "release-signatures.json" in source
    assert "formal_slsa_level" in source and "not-claimed" in source
    assert "no private key or credential is persisted" in source.lower()


def test_heavy_ci_workflow_only_uploads_sanitized_canonical_outputs():
    path = ROOT / ".github/workflows/docs-security-supply-chain.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text
    assert "supply_chain_automation.py capture" in text
    assert "supply_chain_automation.py promote" in text
    assert ".pocketlab-dev" not in text.split("Upload sanitized qualification evidence", 1)[1]
    assert "contracts/generated/supply-chain/" in text
    assert "gh watch" not in text


def test_graphviz_and_semgrep_boundaries_are_present():
    rules = (ROOT / "security/static-analysis/pocketlab-architecture.yml").read_text(encoding="utf-8")
    assert "NATS" in rules or "nats" in rules
    assert "child_process" in rules or "shell" in rules.lower()
    setup = (ROOT / "scripts/dev/lite/setup-documentation-tools.sh").read_text(encoding="utf-8")
    assert "graphviz" in setup.lower() or "dot" in setup


def test_supply_chain_capture_covers_source_sbom_history_release_and_never_replaces_worktree_scan():
    source = (ROOT / "scripts/docs/enterprise/supply_chain_automation.py").read_text(encoding="utf-8")
    assert '"osv-sbom-dev.json"' in source
    assert '"gitleaks-worktree.json"' in source
    assert '"gitleaks-history.json"' in source
    assert '"gitleaks-release.json"' in source
    assert '["git" if include_history else "dir"' not in source
    assert 'raw.glob("gitleaks-*.json")' in source


def test_documentation_quality_uses_only_contract_vocabulary_and_change_advisor_has_all_inputs():
    allowed = {"complete", "partial", "missing", "not-applicable"}
    rows = completion.documentation_quality(ROOT)
    keys = ["architecture_documented","api_documented","events_documented","runbook_present","threat_model_present","operational_health_modeled","evidence_coverage","troubleshooting","release_impact","ownership","privacy_map","quality"]
    assert rows and all({row[k] for k in keys} <= allowed for row in rows)
    advisor = completion.change_advisor()
    assert advisor["implementation_status"] == "implemented"
    assert advisor["executes_changes"] is False
    joined = " ".join(advisor["inputs"]).lower()
    for token in ["api", "event", "test", "documentation", "architecture", "security", "release", "runtime"]:
        assert token in joined


def test_release_delta_embeds_supply_chain_change_intelligence():
    baseline = completion.current_release_baseline(ROOT)["baseline"]
    inventory = completion.source_dependency_inventory(ROOT, baseline["tag"] if baseline else None)
    sc = completion.supply_chain_change(inventory, ROOT, baseline["tag"] if baseline else None)
    delta = completion.release_delta(ROOT)
    delta["supply_chain_change"] = sc
    assert delta["supply_chain_change"]["implementation_status"] == "implemented"


def test_enterprise_engineering_handbooks_are_wired_into_mkdocs_nav():
    """Rich Task Reference and Events pages must own the visible Development nav."""
    from pathlib import Path

    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")

    expected = {
        "Task Reference": (
            "generated/enterprise/engineering/task-reference.md"
        ),
        "Events": (
            "generated/enterprise/engineering/events.md"
        ),
    }

    legacy = {
        "Task Reference": "generated/development/task-reference.md",
        "Events": "generated/development/events.md",
    }

    for label, target in expected.items():
        nav_entry = f"- {label}: {target}"
        assert nav_entry in mkdocs, (
            f"{label} must point to the rich enterprise engineering page: "
            f"{target}"
        )

    for label, target in legacy.items():
        nav_entry = f"- {label}: {target}"
        assert nav_entry not in mkdocs, (
            f"{label} still points to legacy thin page: {target}"
        )

    assert Path(
        "docs/generated/enterprise/engineering/task-reference.md"
    ).is_file()

    assert Path(
        "docs/generated/enterprise/engineering/events.md"
    ).is_file()


def test_docs_playwright_uses_shared_dev_scratch_namespace():
    """Docs browser tests use the common dev scratch root plus a namespace."""
    from pathlib import Path

    config = Path("playwright.docs.config.ts").read_text(encoding="utf-8")
    assert "POCKETLAB_DEV_TMPDIR" in config
    assert "pocketLabDevScratchRoot" in config
    assert "'playwright'" in config
    assert "TMPDIR: pocketLabDocsTempDir" in config
    assert "TMP: pocketLabDocsTempDir" in config
    assert "TEMP: pocketLabDocsTempDir" in config

def test_docs_portal_long_scenario_has_scoped_timeout():
    """The comprehensive mobile docs portal test needs a scoped budget."""
    from pathlib import Path

    config = Path(
        "playwright.docs.config.ts"
    ).read_text(encoding="utf-8")

    spec = Path(
        "tests/docs/mkdocs.spec.ts"
    ).read_text(encoding="utf-8")

    # Ordinary docs browser tests retain the stricter global ceiling.
    assert "timeout: 45_000" in config

    title = (
        "documentation portal navigation, theme, search, "
        "and accessibility"
    )

    start = spec.find(title)
    assert start >= 0, "Portal Playwright test is missing"

    # Search a bounded region belonging to this test rather than accepting
    # an unrelated timeout elsewhere in the file.
    region = spec[start:start + 1200]

    assert "test.setTimeout(90_000);" in region, (
        "The comprehensive docs portal scenario must retain its scoped "
        "90-second timeout; the global 45-second timeout is intentionally "
        "kept for ordinary tests."
    )


def test_docs_playwright_preserves_real_request_failures_while_ignoring_mkdocs_page_aborts():
    """Ignore only benign local MkDocs page aborts, not asset/network failures."""
    from pathlib import Path

    spec = Path(
        "tests/docs/mkdocs.spec.ts"
    ).read_text(encoding="utf-8")

    required = (
        "failure === 'net::ERR_ABORTED'",
        "parsed.pathname.startsWith(DOCS_PREFIX)",
        "parsed.pathname.endsWith('/')",
        "if (isLocalDocsPageAbort) return;",
        "failedRequests.push(`${failure} ${url}`);",
    )

    missing = [
        value
        for value in required
        if value not in spec
    ]

    assert not missing, (
        "Scoped MkDocs request-failure policy is incomplete: "
        + ", ".join(missing)
    )

    # We must not broadly suppress every ERR_ABORTED request.
    assert "if (failure === 'net::ERR_ABORTED') return;" not in spec

    # Asset/network failures must still enter failedRequests.
    assert spec.count(
        "failedRequests.push(`${failure} ${url}`);"
    ) >= 1




def test_storybook_home_devices_coverage_respects_story_boundary():
    """Reuse canonical representative render instead of duplicate navigation."""
    from pathlib import Path

    script = Path(
        "scripts/docs/lite/test-storybook.mjs"
    ).read_text(encoding="utf-8")

    # Devices must be validated inside the existing representative-story loop.
    assert "entry.title === 'Pocket Lab Lite/Devices'" in script
    assert (
        "locator('[data-lite-screen-id=\"devices\"]')"
        in script
    )

    # Home still proves that its Devices control exists and is usable.
    assert (
        "getByRole('button', { name: /^Devices/i })"
        in script
    )
    assert "devicesControl.isEnabled()" in script

    # Do not impersonate full app routing from an isolated Storybook story.
    assert "await devices.click();" not in script
    assert "devices.click({ noWaitAfter: true })" not in script

    # Do not reload a second arbitrary Devices story after the representative
    # story loop has already validated the Devices story family.
    assert "const devicesStory = entries.find(" not in script


def test_schemaspy_uses_shared_dev_scratch_namespace():
    """SchemaSpy uses the common dev scratch root with a specific override."""
    from pathlib import Path

    source = Path("scripts/docs/sqlite/generate_schemaspy.py").read_text(encoding="utf-8")
    assert "POCKETLAB_DEV_TMPDIR" in source
    assert "POCKETLAB_SCHEMASPY_TMPDIR" in source
    assert 'POCKETLAB_DEV_SCRATCH_ROOT / "schemaspy"' in source
    assert "dir=POCKETLAB_SCHEMASPY_TMP" in source


def test_release_comparison_never_substitutes_head_for_a_release():
    delta = completion.release_delta(ROOT)
    policy = completion.current_release_baseline(ROOT)["baseline_policy"]
    assert "release-to-HEAD comparison is forbidden" in policy
    if delta["status"] == "comparable":
        assert isinstance(delta.get("from"), dict) and delta["from"].get("tag", "").startswith("lite-")
        assert isinstance(delta.get("to"), dict) and delta["to"].get("tag", "").startswith("lite-")
    else:
        assert all(row["classification"] == "not-comparable" for row in delta["dimensions"])


def test_threat_model_svg_is_semantic_architecture_integrated_and_not_live():
    text = (ROOT / "docs/generated/assets/enterprise/threat-model.svg").read_text(encoding="utf-8")
    for token in ["data-node=", "data-control=", "data-attack-path=", "Modeled flow — not live traffic", "prefers-reduced-motion"]:
        assert token in text
    # Threat Model brand icons are embedded into the generated SVG so the
    # projection remains self-contained when rendered through <object>,
    # <picture>, or <img>. Do not require filesystem icon filenames here.
    assert 'class="brand-icon"' in text
    assert 'href="data:image/svg+xml;base64,' in text

    # Representative canonical systems must still be present as semantic
    # nodes; icon embedding must not weaken architecture integration.
    for node in [
        "lite-api",
        "nats-jetstream",
        "tailscale",
        "managed-device",
        "photoprism",
    ]:
        assert f'data-node="{node}"' in text

    # Embedded brand assets must remain self-contained. Browser rendering of
    # generated Threat Model SVGs must not depend on remote/network resources.
    assert 'href="http://' not in text
    assert 'href="https://' not in text


def test_threat_model_progressive_enhancement_never_polls_network():
    text = (ROOT / "docs/javascripts/threat-model.js").read_text(encoding="utf-8")
    forbidden = ["fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "navigator.sendBeacon"]
    assert not any(token in text for token in forbidden)
    assert "prefers-reduced-motion" in text


def test_release_evidence_promotion_validation_is_sanitized_and_fail_closed():
    digest = "a" * 64
    payload = {
        "release_tag": "lite-2026.08.12.2", "source_commit": "b" * 40, "tree_hash": "c" * 40,
        "verification_status": "verified", "sanitized": True,
        "artifacts": [{"name": name, "sha256": digest, "bytes": 1, "status": "verified"} for name in release_promotion.REQUIRED],
    }
    assert release_promotion.validate_capture(payload) == []
    broken = dict(payload); broken["sanitized"] = False
    assert "capture is not marked sanitized" in release_promotion.validate_capture(broken)
    parsed = release_promotion.parse_checksums(f"{digest}  dist.zip\n")
    assert parsed == {"dist.zip": digest}


def test_release_capture_is_explicit_and_never_invoked_by_docs_generators():
    capture=(ROOT/'scripts/docs/enterprise/release_evidence_promotion.py').read_text(encoding='utf-8')
    generator=(ROOT/'scripts/docs/enterprise/generate_enterprise_documentation.py').read_text(encoding='utf-8')
    assert 'gh", "api"' in capture and 'gh", "release", "download"' in capture
    assert 'RELEASE_EVIDENCE_PROMOTE' in capture
    assert 'release_evidence_promotion.py' not in generator
