from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_security_atlas_is_a_deterministic_projection_of_the_canonical_model():
    model = read_json("contracts/security/threat-model.json")
    atlas = read_json("contracts/generated/documentation-enterprise/security-atlas.json")

    assert "security_atlas" not in model
    assert atlas["source_model"] == "contracts/security/threat-model.json"
    assert atlas["live_monitoring"] is False
    assert atlas["generated_intelligence"] == "deterministic-projection-only"
    assert [row["label"] for row in atlas["views"]] == [
        "Threat Atlas",
        "System Atlas",
        "Attack Surface Atlas",
        "Control Atlas",
        "Evidence Atlas",
    ]

    keys = [(row["kind"], row["catalog_id"]) for row in atlas["catalog"]]
    targets = [(row["kind"], row["target_id"]) for row in atlas["catalog"]]
    assert len(keys) == len(set(keys))
    assert len(targets) == len(set(targets))
    assert keys == sorted(keys, key=lambda item: (next(
        row["view"] for row in atlas["catalog"] if (row["kind"], row["catalog_id"]) == item
    ), item[0], item[1]))


def test_security_atlas_covers_threats_system_attack_surface_controls_and_evidence():
    model = read_json("contracts/security/threat-model.json")
    atlas = read_json("contracts/generated/documentation-enterprise/security-atlas.json")
    by_view = {row["id"]: row["entry_count"] for row in atlas["views"]}

    assert by_view["threats"] == len(model["threats"])
    assert by_view["system"] == len(model["visualization"]["nodes"])
    assert by_view["attack-surface"] == len(model["boundaries"]) + len(model["attack_paths"])
    assert by_view["controls"] == len(model["controls"])
    assert by_view["evidence"] >= len(model["visualization"]["evidence_lineage"])

    ap04 = next(row for row in atlas["catalog"] if row["kind"] == "attack-path" and row["target_id"] == "AP-04")
    assert ap04["title"] == "Attack path AP-04"
    assert "CTRL-API-CONTROL" in ap04["meta"]

    controls = [row for row in atlas["catalog"] if row["kind"] == "control"]
    assert controls and all("If it fails:" in row["meta"] for row in controls)


def test_generated_security_atlas_page_and_poster_are_accessible_and_source_bound():
    page = (ROOT / "docs/generated/enterprise/threat-model/catalog.md").read_text(encoding="utf-8")
    poster = (ROOT / "docs/generated/assets/enterprise/security-atlas.svg").read_text(encoding="utf-8")

    for text in [
        "## Security Atlas",
        "Threat Atlas",
        "System Atlas",
        "Attack Surface Atlas",
        "Control Atlas",
        "Evidence Atlas",
        'data-catalog-id="AP-04"',
        'data-catalog-kind="attack-path"',
        "Select a catalog entry",
        "Threats, controls, boundaries, assets and paths remain evidence-bound and source-derived.",
    ]:
        assert text in page

    assert 'data-layout-engine="canonical-security-layout-v2"' in poster
    assert 'data-variant="catalog"' in poster
    assert '<title id="poster-title">Pocket Lab Lite · Security Atlas Architecture Overlay</title>' in poster
    assert '<desc id="poster-desc">' in poster
    assert 'data-threat-legend="svg"' in poster
    assert 'role="img"' in poster
    assert not re.search(r'(?:href|xlink:href)=["\'](?:https?:)?//', poster, re.I)


def test_security_atlas_browser_projection_has_no_runtime_polling_or_network_capture():
    javascript = (ROOT / "docs/javascripts/threat-model.js").read_text(encoding="utf-8")
    assert "setTimeout(" not in javascript
    assert "window.requestAnimationFrame" not in javascript
    assert "semanticSelection" not in javascript
    assert "handleHashChange" not in javascript
    assert "replaceSemanticUrl" in javascript
    assert "url.searchParams.set(`atlas-${kind}`, target)" in javascript
    assert "url.hash = '#security-atlas'" in javascript
    forbidden = ["fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "setInterval(", "requests.get(", "httpx.get("]
    assert not any(token in javascript for token in forbidden)
    assert "URLSearchParams" in javascript
    assert "applyDeepLink" in javascript
    assert "activateAttackPath" in javascript
    assert "object.addEventListener('load', bindSvg" in javascript
    assert "Detail projection is intentionally independent of SVG readiness" in javascript
