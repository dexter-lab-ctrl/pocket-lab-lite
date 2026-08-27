from __future__ import annotations

import json
from pathlib import Path

from scripts.docs.enterprise import threat_model_experience

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "security/threat-model-scenarios.json"
GENERATED_THREAT = ROOT / "contracts/security/threat-model.json"

EXPECTED_PATHS = {
    "AP-09": ["Spoofing", "Tampering", "Elevation of Privilege"],
    "AP-10": ["Tampering", "Repudiation", "Elevation of Privilege"],
    "AP-11": ["Tampering", "Elevation of Privilege", "Denial of Service"],
    "AP-12": ["Tampering", "Repudiation", "Denial of Service"],
    "AP-13": ["Spoofing", "Tampering", "Repudiation", "Elevation of Privilege"],
    "AP-14": ["Tampering", "Elevation of Privilege"],
}

EXPECTED_CONTROLS = {
    "CTRL-WEBAUTHN-ASSURANCE",
    "CTRL-ENTERPRISE-ROLE-FINAL-OWNER",
    "CTRL-POLICY-REVISION-LIFECYCLE",
    "CTRL-INDEPENDENT-APPROVAL-CONTINUATION",
    "CTRL-TEMPORARY-EXCEPTION-SCOPE",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _projected_threat() -> dict:
    # Enrichment is intentionally idempotent so this focused test works both
    # before and after the generated threat contract has been refreshed.
    return threat_model_experience.enrich(_read(GENERATED_THREAT), ROOT)


def test_identity_rules_d3_canonical_scenarios_are_bounded_and_source_backed() -> None:
    scenarios = _read(SCENARIOS)
    paths = {row["id"]: row for row in scenarios["attack_paths"]}
    controls = {row["id"]: row for row in scenarios["controls"]}

    assert set(EXPECTED_PATHS).issubset(paths)
    assert set(controls) == EXPECTED_CONTROLS
    assert len([path_id for path_id in paths if path_id.startswith("AP-")]) == 14

    for path_id, stride in EXPECTED_PATHS.items():
        row = paths[path_id]
        assert row["stride"] == stride
        assert row["status"] == "modeled"
        assert row["review_status"] == "human-review-required"

    for row in controls.values():
        assert row["status"] == "mitigation-source-derived"
        assert row["freshness"] == "source-current"
        for relative in [*row["implementation"], *row["source_refs"], *row["tests"]]:
            assert (ROOT / relative).exists(), f"missing D3 source proof: {relative}"

    approval = controls["CTRL-INDEPENDENT-APPROVAL-CONTINUATION"]["description"]
    assert "approval does not execute the action" in approval
    assert "initiator retry" in approval
    exception = controls["CTRL-TEMPORARY-EXCEPTION-SCOPE"]["description"]
    assert "catalog.install" in exception
    assert "at most 60 minutes" in exception


def test_identity_rules_d3_generated_projection_remains_static_and_modeled() -> None:
    threat = _projected_threat()
    paths = {row["id"]: row for row in threat["attack_paths"]}
    controls = {row["id"]: row for row in threat["controls"]}
    boundary_ids = {row["id"] for row in threat["boundaries"]}

    for path_id, stride in EXPECTED_PATHS.items():
        row = paths[path_id]
        assert row["stride"] == stride
        assert row["status"] == "modeled"
        assert row["confirmed_exploit"] is False
        assert set(row["boundaries"]).issubset(boundary_ids)

    for control_id in EXPECTED_CONTROLS:
        row = controls[control_id]
        assert row["status"] == "mitigation-source-derived"
        assert row["mitigation_adequacy"] == "human-review-required"
        assert row["prevention_claim"] is False
        assert set(row["boundaries"]).issubset(boundary_ids)

    assert threat["visualization"]["live_monitoring"] is False
    assert threat["visualization"]["animation_semantics"].endswith("never live traffic or attacks")
    assert threat["production_posture"]["controls_source_derived"] >= len(EXPECTED_CONTROLS)


def test_identity_rules_d3_security_atlas_projects_new_paths_and_controls() -> None:
    threat = _projected_threat()
    atlas = threat_model_experience.build_security_atlas(threat)
    catalog = {(row["kind"], row["catalog_id"]): row for row in atlas["catalog"]}

    assert atlas["live_monitoring"] is False
    for path_id in EXPECTED_PATHS:
        assert ("attack-path", path_id) in catalog
    for control_id in EXPECTED_CONTROLS:
        assert ("control", control_id) in catalog
