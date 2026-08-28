from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE = ROOT / "scripts/docs/enterprise"
if str(ENTERPRISE) not in sys.path:
    sys.path.insert(0, str(ENTERPRISE))

from threat_model_experience import build_security_atlas, enrich
from threat_model_poster import build_security_poster, render_threat_model_overview


def _projection() -> tuple[dict, dict]:
    threat = enrich(
        json.loads((ROOT / "contracts/security/threat-model.json").read_text(encoding="utf-8")),
        ROOT,
    )
    return threat, build_security_poster(threat, build_security_atlas(threat))


def test_enterprise_console_projection_is_deterministic_referenced_and_truth_bound():
    threat, poster = _projection()
    enterprise = threat["visualization"]["enterprise"]
    assert enterprise["schema_version"] == "2.0.0"
    assert enterprise["canonical_topology"] is True
    assert enterprise["live_monitoring"] is False
    assert poster["enterprise"] == enterprise
    nodes = {row["id"] for row in threat["visualization"]["nodes"]}
    controls = {row["id"] for row in threat["controls"]}
    paths = {row["id"] for row in threat["attack_paths"]}
    assert set(enterprise["lenses"]) == {
        "architecture", "trust-boundaries", "attack-paths", "stride", "controls", "evidence", "consequences"
    }
    subjects = {row["subject"] for row in enterprise["blast_radius"]}
    assert {f"system:{node}" for node in nodes}.issubset(subjects)
    assert {f"control:{control}" for control in controls}.issubset(subjects)
    assert {f"boundary:{row['id']}" for row in threat["boundaries"]}.issubset(subjects)
    assert {f"path:{path}" for path in paths}.issubset(subjects)
    for story in enterprise["story_paths"]:
        assert story["id"] in paths
        assert story["confirmed_exploit"] is False
        for stage in story["stages"]:
            assert stage["source"] in nodes and stage["destination"] in nodes
            assert set(stage["controls"]).issubset(controls)
            assert "does not claim exploitation" in stage["truth"]
    for interception in enterprise["control_interceptions"]:
        assert interception["control"] in controls
        assert interception["attack_path"] in paths
        assert interception["prevention_claim"] is False
    assert "not a runtime simulator" in enterprise["scenario_comparison"]["truth"]
    assert "do not represent live compromise" in enterprise["truth"].lower()
    assert enterprise["control_coverage"] and enterprise["evidence_gaps"]
    assert all("counts" in row and "markers" in row for row in enterprise["control_coverage"])


def test_enterprise_console_page_has_semantic_lenses_story_and_local_review_workspace():
    threat, poster = _projection()
    page = render_threat_model_overview(threat, poster)
    for token in (
        'data-pl-security-console="true"', 'role="tablist"', 'data-pl-security-lens="architecture"',
        'data-pl-security-lens="consequences"', 'data-pl-enterprise-stride="Tampering"',
        'Attack Path Story Mode', 'data-pl-story="next"', 'Show blast radius', 'Isolate boundary',
        'data-pl-security-action="blast" aria-pressed="false"',
        'data-pl-security-action="isolate" aria-pressed="false"',
        'data-pl-security-action="workspace" aria-expanded="false"',
        'Show evidence gaps', 'Compare modeled posture', 'Security Review Workspace',
        'Executive view', 'Engineer view', 'Evidence <textarea data-pl-review="evidence"', 'type="application/json"',
    ):
        assert token in page
    javascript = (ROOT / "docs/javascripts/threat-model-poster.js").read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "setInterval(", "setTimeout("):
        assert forbidden not in javascript
    svg = (ROOT / "docs/generated/assets/enterprise/threat-model.svg").read_text(encoding="utf-8")
    assert 'class="attack attack-segment"' in svg
    assert 'data-stage="1"' in svg
    assert 'tabindex="0" role="button"' in svg
