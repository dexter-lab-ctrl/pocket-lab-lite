from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_security_poster_is_static_architecture_bound_and_score_free():
    model = read_json("contracts/security/threat-model.json")
    poster = read_json("contracts/generated/documentation-enterprise/security-poster.json")

    assert poster["source_model"] == "contracts/security/threat-model.json"
    assert poster["architecture_model"] == model["architecture_integration"]["canonical_model"]
    assert poster["live_monitoring"] is False
    assert poster["generated_intelligence"] == "deterministic-presentation-projection-only"
    assert poster["presentation_modes"] == ["understand", "threats", "controls"]
    assert poster["stride_lens"] == [
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege",
    ]

    raw = json.dumps(poster, sort_keys=True).lower()
    for forbidden in ["risk_score", "security_score", "last_seen", "live_feed", "active_attack"]:
        assert f'"{forbidden}"' not in raw

    node_ids = {row["id"] for row in poster["nodes"]}
    assert len(node_ids) == len(poster["nodes"]) == len(model["visualization"]["nodes"])
    assert {row["architecture_component"] for row in poster["nodes"]} == {
        row["architecture_component"] for row in model["visualization"]["nodes"]
    }
    assert all(row["from"] in node_ids and row["to"] in node_ids for row in poster["flows"])
    assert all(set(row["path_nodes"]).issubset(node_ids) for row in poster["attack_paths"])
    assert all("assets" in row for row in poster["nodes"])
    assert poster["guardrails"]["sanitized_input_required"] is True


def test_security_poster_forbidden_paths_are_exact_canonical_statements():
    model = read_json("contracts/security/threat-model.json")
    poster = read_json("contracts/generated/documentation-enterprise/security-poster.json")
    canonical = {
        statement
        for boundary in model["boundaries"]
        for statement in boundary.get("forbidden_flows", [])
    }
    assert poster["forbidden_flows"]
    assert all(row["statement"] in canonical for row in poster["forbidden_flows"])


def test_security_poster_svg_has_bounded_motion_and_no_remote_or_script_content():
    svg = (ROOT / "docs/generated/assets/enterprise/threat-model.svg").read_text(encoding="utf-8")
    detail = (ROOT / "docs/generated/assets/enterprise/threat-model-detail.svg").read_text(encoding="utf-8")

    assert "Pocket Lab Lite Security Architecture Poster" in svg
    assert "NOT LIVE MONITORING" in svg
    assert 'data-poster-mode="understand"' in svg
    assert 'data-core="true"' in svg
    assert 'class="forbidden"' in svg
    assert 'class="control"' in svg
    assert "@keyframes canonical-flow" in svg
    assert "@keyframes attack-trace" in svg
    assert "@keyframes control-halo" in svg
    assert "data-assets=" in svg
    assert "prefers-reduced-motion" in svg
    assert "<script" not in svg.lower()
    assert not re.search(r'(?:href|xlink:href)=["\'](?:https?:)?//', svg, re.I)
    assert "Pocket Lab Lite threat model architecture overlay" in detail


def test_threat_model_is_split_into_cross_linked_pages_and_catalog_is_preserved():
    pages = {
        "index.md",
        "architecture.md",
        "stride.md",
        "attack-paths.md",
        "controls.md",
        "assets-guardrails.md",
        "evidence.md",
        "catalog.md",
    }
    base = ROOT / "docs/generated/enterprise/threat-model"
    assert pages.issubset({path.name for path in base.glob("*.md")})

    overview = (base / "index.md").read_text(encoding="utf-8")
    catalog = (base / "catalog.md").read_text(encoding="utf-8")
    assert "How Pocket Lab protects control" in overview
    assert 'data-threat-poster-mode="understand"' in overview
    assert 'data-stride-lens="Tampering"' in overview
    assert 'data-threat-guardrails="toggle"' in overview
    assert "Security Atlas Catalog" in catalog
    assert "Threat Atlas" in catalog and "Evidence Atlas" in catalog

    for name in pages - {"catalog.md"}:
        text = (base / name).read_text(encoding="utf-8")
        normalized = text.replace("&amp;", "&")
        assert "Security Atlas catalog" in normalized
        assert "Architecture & trust zones" in normalized
        assert "Evidence & provenance" in normalized



def test_threat_model_architecture_boundary_links_resolve_to_sibling_pages():
    base = (
        ROOT
        / "docs/generated/enterprise/threat-model"
    )
    architecture = (
        base / "architecture.md"
    ).read_text(encoding="utf-8")

    expected = [
        "application-container",
        "browser",
        "control-api",
        "durable-state",
        "external-release",
        "managed-device",
        "messaging-execution",
        "server-host",
        "private-network",
    ]

    for boundary in expected:
        sibling = f"{boundary}.md"

        assert f"]({sibling})" in architecture
        assert f"](../{sibling})" not in architecture
        assert (base / sibling).exists()


def test_poster_browser_layer_has_no_network_polling_or_timers():
    javascript = (ROOT / "docs/javascripts/threat-model-poster.js").read_text(encoding="utf-8")
    for forbidden in ["fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "setInterval(", "setTimeout(", "requestAnimationFrame"]:
        assert forbidden not in javascript
    assert "data-threat-poster-mode" in javascript
    assert "data-stride-lens" in javascript
    assert "show-guardrails" in javascript
    assert "CATALOG_ONLY" in javascript
    assert "window.location.replace(url)" in javascript
    assert "new URL('catalog/', window.location.href)" in javascript
