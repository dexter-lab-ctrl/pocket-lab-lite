from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/docs/intelligence/generate_documentation_intelligence.py"
OUT = ROOT / "contracts/generated/documentation-intelligence"
INDEX = OUT / "index.json"
EXPERIENCE = ROOT / "contracts/metadata/documentation-experience.json"
EXPERIENCE_SCHEMA = ROOT / "schemas/documentation/documentation-experience.schema.json"
INTELLIGENCE_SCHEMA = ROOT / "schemas/documentation/documentation-intelligence.schema.json"
OP_HEALTH = ROOT / "contracts/generated/runtime/domain-operational-health.json"
RUNTIME = ROOT / "contracts/parity/runtime-verification-baseline.json"
MKDOCS = ROOT / "mkdocs.yml"
DOCS_TASKS = ROOT / "tasks/Taskfile.docs.yml"
HOME = ROOT / "docs/index.md"
HOME_FRAGMENT = ROOT / "docs/generated/home-dashboard.md"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def intelligence():
    return load(INDEX)["items"]


def test_ux_contract_and_intelligence_schema_are_valid():
    jsonschema.Draft202012Validator(load(EXPERIENCE_SCHEMA)).validate(load(EXPERIENCE))
    jsonschema.Draft202012Validator(load(INTELLIGENCE_SCHEMA)).validate(intelligence())


def test_intelligence_release_binding_matches_promoted_health_and_runtime():
    data = intelligence()
    runtime = load(RUNTIME)
    health = load(OP_HEALTH)
    for field in ("release_tag", "source_commit", "promoted_at"):
        assert data["release"][field] == runtime[field] == health[field]


def test_dependency_health_never_inherits_domain_health_without_dependency_evidence():
    rows = {x["domain"]: x for x in intelligence()["dependency_health"]}
    assert rows["apps"]["operational_health"] == "healthy"
    assert next(x for x in rows["apps"]["dependencies"] if x["name"] == "PhotoPrism runtime")["state"] == "healthy"
    assert next(x for x in rows["security"]["dependencies"] if x["name"] == "Lynis")["state"] == "unvalidated"
    assert next(x for x in rows["recovery"]["dependencies"] if x["name"] == "restic")["state"] == "unvalidated"


def test_release_impact_is_future_ready_but_does_not_fabricate_history():
    impact = intelligence()["release_impact"]
    runtime = load(RUNTIME)

    if impact["current_release"]:
        assert impact["to_release"] == impact["current_release"]["tag"]
        assert impact["source_commit"] == impact["current_release"]["commit"]
    else:
        assert impact["to_release"] == runtime["release_tag"]
        assert impact["source_commit"] == runtime["source_commit"]

    assert impact["status"] == "release-impact-ready"
    assert impact["comparison_state"] in {
        "no-canonical-release",
        "baseline-only",
        "comparable",
        "comparison-evidence-unavailable",
    }
    assert len(impact["dimensions"]) == 22
    assert impact["material_findings"]
    assert {"operational_health", "semantic_parity", "platform_capabilities"} <= set(impact["current_snapshot"])
    if impact["comparison_state"] != "comparable":
        assert impact["from_release"] is None
        assert impact["unchanged"] == []
        assert all(row["classification"] == "not-comparable" for row in impact["technical_delta"]["dimensions"])
        assert "HEAD" not in impact["comparison_label"]


def test_home_dashboard_prefers_current_canonical_promoted_release():
    data = intelligence()
    dashboard = data["dashboard"]
    impact = data["release_impact"]
    runtime = load(RUNTIME)

    current = impact.get("current_release") or {}

    if current:
        assert dashboard["release_tag"] == current["tag"]
        assert dashboard["source_commit"] == current["commit"]

        expected_promoted_at = (
            current.get("observed_at")
            or current.get("published_at")
            or runtime["promoted_at"]
        )
        assert dashboard["promoted_at"] == expected_promoted_at
    else:
        assert dashboard["release_tag"] == runtime["release_tag"]
        assert dashboard["source_commit"] == runtime["source_commit"]
        assert dashboard["promoted_at"] == runtime["promoted_at"]

    # Runtime/operational-health identity remains independently runtime-bound.
    assert data["release"]["release_tag"] == runtime["release_tag"]
    assert data["release"]["source_commit"] == runtime["source_commit"]


def test_runtime_drift_keeps_configuration_and_semantic_drift_independent():
    drift = intelligence()["runtime_drift"]
    assert drift["configuration_runtime"]
    assert drift["semantic_drift_independent"]
    assert drift["configuration_summary"]["aligned"] >= 1
    assert all("runtime_parity" in x for x in drift["semantic_drift_independent"])
    assert "independently" in drift["semantic_note"]


def test_recovery_readiness_preserves_stale_guard_and_write_safety():
    recovery = intelligence()["recovery_readiness"]
    assert recovery["overall"] == "degraded"
    assert recovery["reason"] == "projection_too_old"
    assert recovery["freshness_age_seconds"] > recovery["freshness_threshold_seconds"]
    checks = {x["name"]: x for x in recovery["checks"]}
    assert checks["Restore currently allowed"]["value"] is False
    assert checks["Fresh restore preview required"]["value"] is True


def test_fleet_readiness_separates_record_counts_from_protected_host_health():
    fleet = intelligence()["fleet_readiness"]
    assert fleet["known_device_records"] >= fleet["online_device_records"]
    assert fleet["overall"] == "healthy"
    assert fleet["remote_access_ready"] is True
    assert "do not by themselves degrade" in fleet["interpretation"]


def test_evidence_lineage_is_release_bound_and_sanitized():
    rows = intelligence()["evidence_lineage"]
    assert len(rows) == 7
    assert all(x["release_tag"] and x["source_commit"] and x["promoted_at"] for x in rows)
    assert all(x["projection"] == "contracts/generated/runtime/domain-operational-health.json" for x in rows)
    raw = json.dumps(rows)
    assert "/data/data/com.termux" not in raw
    assert "nats://" not in raw


def test_evidence_coverage_is_complete_cartesian_domain_dimension_matrix():
    coverage = intelligence()["evidence_coverage"]
    assert len(coverage["cells"]) == 7 * len(coverage["dimensions"])
    assert len({(x["domain"], x["dimension"]) for x in coverage["cells"]}) == len(coverage["cells"])
    assert coverage["by_domain"]["identity"]["confidence"] == "partial"
    assert coverage["by_domain"]["recovery"]["coverage_fraction"].endswith(f"/{len(coverage['dimensions'])}")


def test_limitations_reason_codes_and_scenarios_are_source_grounded():
    data = intelligence()
    categories = {x["category"] for x in data["limitations"]}
    assert {"accepted-limitation", "known-gap", "unsupported-operation"} <= categories
    active_reasons = {
        x["code"]
        for x in data["reason_codes"]
        if x["observed_in_current_health"]
    }

    operational_health = load(OP_HEALTH)
    expected_active_reasons = {
        row["reason"]
        for row in operational_health["domains"].values()
        if row.get("reason") is not None
    }

    assert active_reasons == expected_active_reasons
    assert any(x["id"] == "add-device" for x in data["scenarios"])
    assert all(x["guardrail"] for x in data["scenarios"])


def test_platform_matrix_is_complete_and_role_aware():
    matrix = intelligence()["platform_matrix"]
    health = load(OP_HEALTH)
    assert len(matrix) == len(health["platform_capabilities"])
    assert len({(x["capability"], x["platform"]) for x in matrix}) == len(matrix)
    assert all(x["status"] == "not-applicable" for x in matrix if x["role"] in {"control-client", "development"})


def test_home_dashboard_and_information_architecture_are_question_oriented():
    mkdocs = MKDOCS.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    fragment = HOME_FRAGMENT.read_text(encoding="utf-8")
    for entry in (
        "Start Here",
        "Use",
        "Operate",
        "Understand",
        "Build & Test",
        "Security & Assurance",
        "Release & Change",
        "Reference",
        "Documentation Platform",
    ):
        assert f"  - {entry}:" in mkdocs
    assert "navigation.instant" in mkdocs
    assert "navigation.instant.prefetch" in mkdocs
    assert "navigation.instant.progress" in mkdocs
    assert "stylesheets/intelligence.css" in mkdocs
    assert '--8<-- "generated/home-dashboard.md"' in home
    assert "Documentation Control Center" in fragment
    assert "I want to" in fragment
    assert "Current operational health" in fragment


def test_ux_contract_enforces_cognitive_accessibility_and_performance_guardrails():
    ux = load(EXPERIENCE)
    assert ux["progressive_disclosure"] == ["summary", "explanation", "technical-evidence"]
    assert ux["motion"]["continuous_animation_allowed"] is False
    assert ux["motion"]["reduced_motion_required"] is True
    assert "color-is-never-the-only-status-signal" in ux["guardrails"]
    assert "no-heavy-monitoring-stack-in-documentation" in ux["guardrails"]
    assert len(ux["task_entry_points"]) >= 6
    assert all(ux["role_shortcuts"].values())


def test_generator_is_two_pass_idempotent_and_read_only_to_promoted_runtime():
    runtime_before = hashlib.sha256(RUNTIME.read_bytes()).hexdigest()
    health_before = hashlib.sha256(OP_HEALTH.read_bytes()).hexdigest()
    hashes = []
    for mode in ("generate", "generate", "check"):
        result = subprocess.run([sys.executable, str(GENERATOR), mode], cwd=ROOT, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        hashes.append(hashlib.sha256(INDEX.read_bytes()).hexdigest())
    assert hashes[0] == hashes[1] == hashes[2]
    assert hashlib.sha256(RUNTIME.read_bytes()).hexdigest() == runtime_before
    assert hashlib.sha256(OP_HEALTH.read_bytes()).hexdigest() == health_before


def test_docs_sync_wiring_keeps_intelligence_static_and_never_captures_or_promotes():
    tasks = DOCS_TASKS.read_text(encoding="utf-8")
    generator = GENERATOR.read_text(encoding="utf-8")
    assert "lite:docs:intelligence:generate:" in tasks
    assert "lite:docs:intelligence:check:" in tasks
    assert "- task: lite:docs:intelligence:generate" in tasks
    assert "- task: lite:docs:intelligence:check" in tasks
    sync = tasks.split("  lite:docs:sync:", 1)[1].split("\n  lite:docs:check:", 1)[0]
    sync_cmds = sync.split("cmds:", 1)[1]
    assert "capture" not in sync_cmds.lower()
    assert "promote" not in sync_cmds.lower()
    assert "subprocess" not in generator
    assert "requests" not in generator
    assert "http://" not in generator and "https://" not in generator
