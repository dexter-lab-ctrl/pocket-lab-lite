from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/docs/enterprise/documentation_ia.py"


def load_module():
    spec = importlib.util.spec_from_file_location("documentation_ia", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ia = load_module()
EXPECTED_TOP_LEVEL = [
    "start-here",
    "use",
    "operate",
    "understand",
    "build-test",
    "security-assurance",
    "release-change",
    "reference",
    "documentation-platform",
]


def test_documentation_ia_contract_is_complete_and_question_oriented():
    contract = json.loads(
        (ROOT / "contracts/generated/documentation-enterprise/information-architecture.json").read_text()
    )
    assert contract["top_level"] == EXPECTED_TOP_LEVEL
    assert contract["page_count"] >= 400
    assert {row["slug"] for row in contract["feature_journeys"]} == {
        "devices",
        "apps",
        "security",
        "recovery",
        "remote-access",
        "identity",
        "release",
    }
    # No canonical Rules journey exists in the source Knowledge Graph today;
    # the IA must not fabricate one just to make the catalog look symmetric.
    assert "rules" not in {row["slug"] for row in contract["feature_journeys"]}
    assert contract["audiences"] == list(ia.AUDIENCES)
    assert contract["intents"] == list(ia.INTENTS)
    assert contract["page_types"] == list(ia.PAGE_TYPES)
    assert contract["authorities"] == list(ia.AUTHORITIES)


def test_feature_journeys_are_bounded_source_derived_and_cycle_safe():
    contract = json.loads(
        (ROOT / "contracts/generated/documentation-enterprise/information-architecture.json").read_text()
    )
    canonical = json.loads((ROOT / "contracts/generated/knowledge/journeys.json").read_text())
    canonical_ids = {row["id"] for row in canonical["items"]}
    for row in contract["feature_journeys"]:
        assert set(row["source_journeys"]) <= canonical_ids
        assert row["confidence"] == "source-derived"
        assert row["expansion"] == {
            "algorithm": "deterministic-bfs",
            "cycle_detection": True,
            "max_depth": 2,
            "max_results": 80,
        }
        assert len(row["expanded_relations"]) <= 80
        assert all(edge["depth"] in {1, 2} for edge in row["expanded_relations"])


def test_every_nav_destination_has_one_primary_owner_and_stable_specialist_urls():
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assignments = ia._nav_primary_assignments(mkdocs)
    assert assignments
    assert all(len(owners) == 1 for owners in assignments.values())

    contract = json.loads(
        (ROOT / "contracts/generated/documentation-enterprise/information-architecture.json").read_text()
    )
    by_path = {row["path"]: row for row in contract["pages"]}
    for path, owners in assignments.items():
        assert path in by_path
        assert by_path[path]["primary_navigation_owner"] == owners[0]

    # Specialist systems keep their canonical URLs even though the global nav is task-oriented.
    for path in (
        "generated/enterprise/knowledgebase/knowledge-graph.md",
        "generated/enterprise/threat-model/index.md",
        "generated/enterprise/threat-model/catalog.md",
        "generated/production/architecture/component-catalog.md",
        "generated/enterprise/reference/api-ui-trace.md",
    ):
        assert (ROOT / "docs" / path).exists()
        assert path in by_path


def test_navigation_has_exact_new_top_level_and_preserves_specialist_threat_model_subnav():
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    nav_text = mkdocs.split("\nnav:\n", 1)[1]
    actual = [line.strip()[2:-1] for line in nav_text.splitlines() if line.startswith("  - ") and line.endswith(":")]
    assert actual == [
        "Start Here",
        "Use",
        "Operate",
        "Understand",
        "Build & Test",
        "Security & Assurance",
        "Release & Change",
        "Reference",
        "Documentation Platform",
    ]
    top_level_lines = {line for line in nav_text.splitlines() if line.startswith("  - ") and line.endswith(":")}
    for legacy in ("Home", "Knowledgebase", "Architecture", "Threat Model", "Evidence", "Develop", "Release", "Enterprise Reference"):
        assert f"  - {legacy}:" not in top_level_lines
    for specialist in (
        "generated/enterprise/threat-model/architecture.md",
        "generated/enterprise/threat-model/stride.md",
        "generated/enterprise/threat-model/attack-paths.md",
        "generated/enterprise/threat-model/controls.md",
        "generated/enterprise/threat-model/evidence.md",
        "generated/enterprise/threat-model/catalog.md",
    ):
        assert specialist in nav_text
    assert mkdocs.count("BEGIN GENERATED KNOWLEDGE RELEASE NAV: production") == 1
    assert mkdocs.count("BEGIN GENERATED KNOWLEDGE RELEASE NAV: development") == 1


def test_start_here_is_a_universal_static_front_door():
    start = (ROOT / "docs/generated/enterprise/hubs/start-here.md").read_text()
    for marker in (
        "## New to Pocket Lab?",
        "## Looking for something exact?",
        "Android / Termux quick start",
        "system architecture",
        "vocabulary",
        "glossary",
        "Knowledge Graph",
        "Reference hub",
    ):
        assert marker in start
    ia_pages = list((ROOT / "docs/generated/enterprise/hubs").glob("*.md")) + list((ROOT / "docs/generated/enterprise/journeys").glob("*.md"))
    assert all('href="/' not in page.read_text() for page in ia_pages)


def test_cross_link_and_search_contracts_are_static_deterministic_and_safe():
    cross = json.loads(
        (ROOT / "contracts/generated/documentation-enterprise/documentation-cross-links.json").read_text()
    )
    search = json.loads(
        (ROOT / "contracts/generated/documentation-enterprise/documentation-search.json").read_text()
    )
    relation_ids = [row["id"] for row in cross["relations"]]
    assert relation_ids == sorted(relation_ids)
    assert len(relation_ids) == len(set(relation_ids))
    assert search["implementation"] == "static-local-search-metadata"
    assert search["runtime_indexing"] is False
    assert search["ranking_model"]["algorithm"] == "weighted-lexical-static"
    aliases = {row["canonical"] for row in search["entries"]}
    assert {
        "device offline",
        "add device",
        "remote access not ready",
        "backup restore",
        "app install",
        "security scan",
        "release changed",
        "api frontend",
        "event nats",
        "why do we believe this",
        "documentation generator",
    } <= aliases


def test_documentation_platform_is_self_documenting_and_security_bounded():
    base = ROOT / "docs/generated/enterprise/documentation-platform"
    required = {
        "index.md",
        "how-to-use.md",
        "architecture.md",
        "information-architecture.md",
        "audience-intent.md",
        "sources-of-truth.md",
        "content-model.md",
        "page-types.md",
        "generation-pipeline.md",
        "evidence-model.md",
        "cross-link-model.md",
        "search-model.md",
        "design-system.md",
        "validation-testing.md",
        "contribution.md",
        "operations-troubleshooting.md",
        "security-boundaries.md",
        "known-limitations.md",
    }
    assert required <= {path.name for path in base.glob("*.md")}
    combined = "\n".join((base / name).read_text() for name in sorted(required))
    for statement in (
        "does not capture runtime",
        "poll NATS",
        "run scanners",
        "access backend secrets",
    ):
        assert statement in combined
    assert not ia.PRIVATE.search(combined)
    assert not ia.SECRET.search(combined)


def test_documentation_ia_build_is_deterministic_without_runtime_access():
    outputs_a, contract_a, cross_a, search_a = ia.build(ROOT)
    outputs_b, contract_b, cross_b, search_b = ia.build(ROOT)
    assert outputs_a == outputs_b
    assert contract_a == contract_b
    assert cross_a == cross_b
    assert search_a == search_b
    source = MODULE_PATH.read_text()
    for forbidden in (
        "requests.get(",
        "requests.post(",
        "httpx.get(",
        "httpx.post(",
        "EventSource(",
        "WebSocket(",
        "capture_termux_runtime",
        "promote_termux_runtime.py",
    ):
        assert forbidden not in source

def test_generated_ia_links_use_correct_markdown_and_browser_bases():
    start_here = (
        ROOT / "docs/generated/enterprise/hubs/start-here.md"
    ).read_text(encoding="utf-8")

    devices = (
        ROOT / "docs/generated/enterprise/journeys/devices.md"
    ).read_text(encoding="utf-8")

    # Markdown links retain source .md filenames for MkDocs.
    assert "../../../getting-started/android-termux.md" in start_here
    assert "../../production/architecture/complete-system.md" in start_here
    assert "../../production/knowledge/vocabulary.md" in start_here
    assert "../../production/knowledge/glossary.md" in start_here
    assert "[Reference hub](reference.md)" in start_here
    assert "../knowledgebase/knowledge-graph.md" in start_here

    assert "../../production/devices.md" in devices
    assert "../../production/architecture/device-onboarding.md" in devices

    # Old pretty-route Markdown forms must not return.
    assert "../../../getting-started/android-termux/" not in start_here
    assert "../../production/architecture/complete-system/" not in start_here
    assert "../../production/devices/" not in devices

    # Raw HTML cards remain browser-route-relative.
    assert 'href="../use/"' in start_here
    assert 'href="../operate/"' in start_here
    assert 'href="../build-test/"' in start_here
    assert 'href="../understand/"' in start_here
    assert 'href="../reference/"' in start_here

    assert 'href="use/"' not in start_here
    assert 'href="operate/"' not in start_here

