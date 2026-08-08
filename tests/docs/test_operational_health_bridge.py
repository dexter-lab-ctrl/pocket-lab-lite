from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "scripts/docs/runtime/generate_domain_operational_health.py"
ARTIFACT = ROOT / "contracts/generated/runtime/domain-operational-health.json"
SCHEMA = ROOT / "schemas/runtime/domain-operational-health.schema.json"
BASELINE = ROOT / "contracts/parity/runtime-verification-baseline.json"
PARITY_MODEL = ROOT / "contracts/parity/parity-model.json"
METADATA = ROOT / "contracts/metadata/documentation-platform.json"
REASON_CODES = ROOT / "contracts/generated/reason-codes.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_generator():
    spec = importlib.util.spec_from_file_location("domain_operational_health_generator", GENERATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_reasons() -> set[str]:
    payload = load(REASON_CODES)["reason_codes"]
    return {row["code"] for row in payload["reason_codes"]}


def test_artifact_schema_release_binding_and_sanitization():
    artifact = load(ARTIFACT)
    baseline = load(BASELINE)
    jsonschema.Draft202012Validator(load(SCHEMA)).validate(artifact)
    assert artifact["sanitized"] is True
    for field in ("release_tag", "source_commit", "promoted_at"):
        assert artifact[field] == baseline[field]
    assert artifact["observed_at"] == baseline["generated_at"]


def test_current_promoted_domain_health_is_evidence_backed_and_independent():
    domains = load(ARTIFACT)["domains"]
    expected = {
        "home": ("implemented", "observed", "degraded", "service_unavailable"),
        "apps": ("implemented", "observed", "healthy", None),
        "devices": ("implemented", "observed", "healthy", None),
        "security": ("implemented", "observed", "healthy", None),
        "recovery": ("implemented", "observed", "degraded", "projection_too_old"),
        "identity": ("partial", "observed", "unvalidated", None),
        "rules": ("partial", "observed", "unvalidated", None),
    }
    for domain_id, values in expected.items():
        row = domains[domain_id]
        assert (
            row["implementation_status"],
            row["runtime_status"],
            row["operational_health"],
            row["reason"],
        ) == values

    assert domains["home"]["semantic_parity"] == "verified-with-mapped-presentation"
    assert domains["home"]["operational_health"] == "degraded"
    assert domains["recovery"]["semantic_parity"] == "verified-with-mapped-presentation"
    assert domains["recovery"]["operational_health"] == "degraded"
    assert domains["recovery"]["freshness"] == "stale"
    assert domains["recovery"]["freshness_age_seconds"] > domains["recovery"]["freshness_threshold_seconds"]


@pytest.mark.parametrize(
    ("domain_id", "observations", "expected_health", "expected_reason"),
    [
        (
            "home",
            {"home-termux-overall_status": "degraded", "home-termux-read_degraded": False},
            "degraded",
            "service_unavailable",
        ),
        (
            "apps",
            {
                "apps-termux-runtime_status": "ready",
                "apps-termux-installed": True,
                "apps-termux-route_ready": True,
                "apps-termux-open_enabled": True,
            },
            "healthy",
            None,
        ),
        (
            "devices",
            {
                "devices-termux-server_status": "Protected server host",
                "devices-termux-server_identity_expected": True,
                "devices-termux-remote_access_ready": True,
            },
            "healthy",
            None,
        ),
        (
            "security",
            {"security-termux-status": "healthy"},
            "healthy",
            None,
        ),
        (
            "recovery",
            {
                "recovery-termux-status": "degraded",
                "recovery-termux-degraded_reason": "projection_too_old",
                "recovery-termux-read_degraded": True,
                "recovery-termux-projection_age_ms": 141714,
            },
            "degraded",
            "projection_too_old",
        ),
    ],
)
def test_table_driven_domain_policy_permutations(domain_id, observations, expected_health, expected_reason):
    generator = load_generator()
    metadata = load(METADATA)
    parity_domains = {row["id"]: row for row in load(PARITY_MODEL)["domains"]}
    baseline_domain = {
        "id": domain_id,
        "implementation_status": "implemented",
        "live_api_coverage": "observed",
        "live_termux_coverage": "observed",
        "live_ui_coverage": "observed",
        "runtime_parity": "verified-with-mapped-presentation",
        "comparisons": [
            {"id": comparison_id, "backend_value": value, "result": "match"}
            for comparison_id, value in observations.items()
        ],
    }
    health, reason, _age, _evidence = generator.evaluate_domain_health(
        domain_id,
        baseline_domain,
        parity_domains[domain_id],
        metadata["operational_health"]["domains"][domain_id],
        canonical_reasons(),
    )
    assert (health, reason) == (expected_health, expected_reason)


def test_implemented_observed_promoted_domain_cannot_silently_become_unvalidated():
    generator = load_generator()
    artifact = load(ARTIFACT)
    broken = copy.deepcopy(artifact)
    broken["domains"]["home"]["operational_health"] = "unvalidated"
    broken["domains"]["home"]["severity"] = "unknown"
    broken["domains"]["home"]["reason"] = None
    with pytest.raises(ValueError, match="must not silently become unvalidated"):
        generator.validate_projection(broken)


def test_nonhealthy_state_requires_canonical_reason():
    generator = load_generator()
    artifact = load(ARTIFACT)
    broken = copy.deepcopy(artifact)
    broken["domains"]["home"]["reason"] = None
    with pytest.raises(ValueError, match="requires a reason"):
        generator.validate_projection(broken)


def test_platform_capability_matrix_is_complete_role_aware_and_evidence_backed():
    artifact = load(ARTIFACT)
    metadata = load(METADATA)
    rows = artifact["platform_capabilities"]
    assert len(rows) == len(metadata["capabilities"]) * len(metadata["platforms"])
    assert len({(row["capability"], row["platform"]) for row in rows}) == len(rows)

    statuses = {row["status"] for row in rows}
    assert {"verified", "implemented", "not-applicable", "unvalidated"} <= statuses
    assert statuses <= {"verified", "observed", "implemented", "unsupported", "not-applicable", "unvalidated"}

    for row in rows:
        if row["status"] == "verified":
            assert row["evidence_status"] == "release-promoted"
            assert row["evidence_comparisons"]
            assert row["source_domain"] in {"apps", "devices", "security", "recovery"}
        if row["role"] in {"control-client", "development"}:
            assert row["status"] == "not-applicable"
            assert row["evidence_status"] == "not-applicable"


def test_generator_is_two_pass_idempotent_and_does_not_mutate_promoted_baseline():
    baseline_before = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    generated_hashes = []
    for mode in ("generate", "generate", "check"):
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), mode],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        generated_hashes.append(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest())
    assert generated_hashes[0] == generated_hashes[1] == generated_hashes[2]
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == baseline_before


def test_task_wiring_keeps_docs_sync_read_only_and_promotion_explicit():
    docs = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    parity = (ROOT / "tasks/Taskfile.parity.yml").read_text(encoding="utf-8")
    gate = (ROOT / "scripts/dev/lite/run-gate.sh").read_text(encoding="utf-8")

    assert "lite:docs:health:generate:" in docs
    assert "lite:docs:health:check:" in docs
    assert "- task: lite:docs:health:generate" in docs
    assert "- task: lite:docs:health:check" in docs
    assert "lite:evidence:runtime:promote:" in parity
    assert "- task: lite:docs:health:generate" in parity
    assert "record docs-strict task lite:docs:check" in gate

    sync = docs.split("  lite:docs:sync:", 1)[1].split("\n  lite:docs:check:", 1)[0]
    assert "lite:docs:generate" in sync and "lite:docs:check" in sync
    sync_cmds = sync.split("cmds:", 1)[1]
    assert "capture" not in sync_cmds.lower()
    assert "promote" not in sync_cmds.lower()


def test_platform_metadata_source_references_exist():
    metadata = load(METADATA)
    for row in metadata["platforms"]:
        assert (ROOT / row["source"]).is_file(), row
    assert metadata["operational_health"]["browser_authority"] == "presentation-semantics-only"
    assert metadata["operational_health"]["evidence_precedence"][0] == "promoted-sanitized-runtime-verification"
