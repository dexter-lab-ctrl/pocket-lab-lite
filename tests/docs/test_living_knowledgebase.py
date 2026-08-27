from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "contracts/generated/knowledge"
SCHEMAS = ROOT / "schemas/knowledge"
DEV = ROOT / "docs/generated/development/knowledge"
PROD = ROOT / "docs/generated/production/knowledge"
ENTERPRISE_KB = ROOT / "docs/generated/enterprise/knowledgebase"
KNOWLEDGE_ASSETS = ROOT / "docs/generated/assets/knowledge"
GENERATOR = ROOT / "scripts/docs/knowledge/generate_knowledge.py"
RUNTIME_BASELINE = ROOT / "contracts/parity/runtime-verification-baseline.json"
PROMOTED_RELEASE_EVIDENCE = (
    ROOT / "contracts/generated/releases/promoted-release-evidence.json"
)
SOURCE_RELEASE_BADGE = (
    ROOT / "docs/overrides/partials/release-badge.html"
)
MKDOCS = ROOT / "mkdocs.yml"


def load(name: str):
    payload = json.loads((KNOWLEDGE / name).read_text(encoding="utf-8"))
    return payload["items"] if "items" in payload else payload


@pytest.fixture(scope="module")
def graph():
    return json.loads((KNOWLEDGE / "index.json").read_text(encoding="utf-8"))


def test_schema_validity_and_status_dimensions(graph):
    entity_schema = json.loads((SCHEMAS / "entity.schema.json").read_text())
    status_schema = json.loads((SCHEMAS / "status-dimensions.schema.json").read_text())
    entity_schema["properties"]["status_dimensions"] = status_schema
    relation_schema = json.loads((SCHEMAS / "relation.schema.json").read_text())
    for entity in graph["entities"]:
        jsonschema.Draft202012Validator(entity_schema).validate(entity)
    for relation in graph["relations"]:
        jsonschema.Draft202012Validator(relation_schema).validate(relation)


def test_stable_unique_entity_and_relation_ids(graph):
    entity_ids = [x["id"] for x in graph["entities"]]
    relation_ids = [x["id"] for x in graph["relations"]]
    assert entity_ids == sorted(entity_ids)
    assert relation_ids == sorted(relation_ids)
    assert len(entity_ids) == len(set(entity_ids))
    assert len(relation_ids) == len(set(relation_ids))
    for rel in graph["relations"][:25]:
        expected = "rel:" + hashlib.sha256(f"{rel['type']}\0{rel['source']}\0{rel['target']}".encode()).hexdigest()[:16]
        assert rel["id"] == expected


def test_no_dangling_graph_references_and_backlinks(graph):
    ids = {x["id"] for x in graph["entities"]}
    for rel in graph["relations"]:
        assert rel["source"] in ids
        assert rel["target"] in ids
    outgoing = graph["indexes"]["outgoing"]
    incoming = graph["indexes"]["incoming"]
    for rel in graph["relations"]:
        assert {"type": rel["type"], "target": rel["target"]} in outgoing[rel["source"]]
        assert {"type": rel["type"], "source": rel["source"]} in incoming[rel["target"]]


def test_api_ui_reverse_indexes_are_symmetric(graph):
    idx = load("api-ui-index.json")
    for api, consumers in idx["api_to_ui"].items():
        for ui in consumers:
            assert api in idx["ui_to_api"][ui]
    assert any(consumers for consumers in idx["api_to_ui"].values())


def test_field_and_route_lineage_are_contract_grounded():
    route_lineage = load("data-lineage.json")
    field_lineage = load("field-lineage.json")
    assert route_lineage
    assert field_lineage
    assert all(x["confidence"] in {"contract-derived", "unvalidated"} for x in route_lineage)
    assert all(x["confidence"] == "contract-derived" for x in field_lineage)
    assert any(x["target_field"] == "last_backup.verification_status" for x in field_lineage)


def test_sqlite_semantic_ownership_and_schemaspy_linkage():
    tables = load("tables.json")
    assert tables
    assert all(x.get("owner") or x.get("writer") for x in tables)
    text = (DEV / "sqlite.md").read_text()
    assert "SchemaSpy remains the structural authority" in text
    assert "security_database_restores" in text


def test_nats_subjects_have_domains_and_never_credentials():
    subjects = load("subjects.json")
    assert subjects
    assert all(x.get("domain") for x in subjects)
    raw = json.dumps(subjects)
    assert not re.search(r"nats://[^\s/@]+:[^\s/@]+@", raw, re.I)


def test_reason_code_registry_contains_only_canonical_codes():
    generated = {x["name"] for x in load("reason-codes.json")}
    canonical_payload = json.loads((ROOT / "contracts/generated/reason-codes.json").read_text())["reason_codes"]
    canonical = canonical_payload.get("reason_codes", canonical_payload)
    assert generated == {x["code"] for x in canonical}
    assert "projection_too_old" in generated


def test_adrs_are_source_grounded_and_relationship_backed(graph):
    adrs = load("adrs.json")
    assert adrs
    assert all(x["source_refs"] for x in adrs)
    targets = {r["target"] for r in graph["relations"] if r["type"] == "affected_by"}
    assert any(x["id"] in targets for x in adrs)


def test_release_knowledge_is_truthful_without_fabricated_history():
    releases = load("releases.json")
    changes = load("release-changes.json")
    runtime = json.loads(RUNTIME_BASELINE.read_text(encoding="utf-8"))
    promoted = next(x for x in releases if x["name"] == runtime["release_tag"])
    assert promoted["source_commit"] == runtime["source_commit"]
    assert promoted["release_manifest_status"] in {"verified", "unvalidated"}
    assert all(x.get("added") == [] and x.get("removed") == [] and x.get("changed") == [] for x in changes)
    assert {x["status"] for x in changes} <= {
        "no-comparable-verified-prior-release",
        "semantic-comparison-available",
    }


def test_all_explicitly_promoted_releases_are_projected_into_knowledge():
    promoted_payload = json.loads(
        PROMOTED_RELEASE_EVIDENCE.read_text(encoding="utf-8")
    )
    promoted = [
        item
        for item in promoted_payload.get("releases", [])
        if item.get("verification_status") == "promoted"
    ]

    assert promoted

    releases = {
        item["name"]: item
        for item in load("releases.json")
    }

    production_overview = (
        PROD / "releases.md"
    ).read_text(encoding="utf-8")

    for record in promoted:
        tag = record["release_tag"]

        assert tag in releases
        assert releases[tag]["source_commit"] == record["source_commit"]
        assert releases[tag]["confidence"] == "release-promoted"
        assert releases[tag]["sanitized"] is True

        release_slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            tag.lower(),
        ).strip("-")

        assert (
            DEV / "releases" / f"{release_slug}.md"
        ).exists()
        assert (
            PROD / "releases" / f"{release_slug}.md"
        ).exists()
        assert tag in production_overview


def test_source_release_badge_uses_latest_explicitly_promoted_release():
    promoted_payload = json.loads(
        PROMOTED_RELEASE_EVIDENCE.read_text(encoding="utf-8")
    )
    promoted = [
        item
        for item in promoted_payload.get("releases", [])
        if item.get("verification_status") == "promoted"
    ]

    assert promoted

    latest = max(
        promoted,
        key=lambda item: (
            str(
                item.get("observed_at")
                or item.get("published_at")
                or ""
            ),
            str(item.get("release_tag") or ""),
        ),
    )

    badge = SOURCE_RELEASE_BADGE.read_text(encoding="utf-8")
    assert latest["release_tag"] in badge


def test_limitations_lifecycle_and_partial_domains_remain_truthful():
    limitations = load("limitations.json")
    assert limitations
    assert {x["status"] for x in limitations} <= {"open", "accepted"}
    domains = {x["id"]: x for x in load("domains.json")}
    for domain in ("domain:identity", "domain:rules"):
        assert domains[domain]["status_dimensions"]["implementation_status"] == "partial"
        assert domains[domain]["status_dimensions"]["runtime_parity"] == "partial"


def test_incident_model_exists_but_history_is_not_fabricated():
    assert load("incidents.json") == []
    template = load("incident-template.json")
    assert "required_fields" in template
    for field in ("id", "affected_release", "root_cause", "regression_tests"):
        assert field in template["required_fields"]


def test_troubleshooting_covers_major_operational_failure_modes():
    titles = {x["id"] for x in load("troubleshooting.json")}
    expected = {
        "troubleshooting:ui-unavailable", "troubleshooting:caddy-unavailable", "troubleshooting:api-unavailable",
        "troubleshooting:nats-unavailable", "troubleshooting:worker-stopped", "troubleshooting:supervisor-stopped",
        "troubleshooting:device-offline", "troubleshooting:tailscale-unavailable", "troubleshooting:photoprism-unavailable",
        "troubleshooting:security-scan-failure", "troubleshooting:backup-failure", "troubleshooting:restore-blocked",
        "troubleshooting:recovery-projection-stale", "troubleshooting:documentation-drift", "troubleshooting:runtime-evidence-mismatch",
    }
    assert expected <= titles


def test_ownership_reverse_index_has_system_roles_only():
    ownership = load("ownership.json")
    assert ownership
    assert all(":" in role for role in ownership)
    assert all(resources for resources in ownership.values())


def test_threat_models_reference_real_boundaries(graph):
    models = load("threat-models.json")
    boundaries = {x["name"] for x in graph["entities"] if x["type"] == "threat-boundary"}
    assert models
    assert all(x["name"] in boundaries for x in models)
    assert all(x["confidence"] == "inferred" for x in models)


def test_platform_capabilities_use_nuanced_statuses():
    matrix = load("platform-capabilities.json")
    assert matrix
    assert {x["platform"] for x in matrix} == {
        "Android/Termux ARM64", "ARM64 Ubuntu/proot", "Ubuntu/WSL2 Dev", "desktop browser", "mobile browser", "server phone", "secondary device"
    }
    assert {x["status"] for x in matrix} <= {
        "verified", "observed", "implemented", "unsupported", "not-applicable", "unvalidated"
    }
    assert any(x["status"] == "verified" for x in matrix)
    assert all(
        x["status"] == "not-applicable"
        for x in matrix
        if x.get("role") in {"control-client", "development"}
    )


def test_traceability_does_not_equate_test_link_with_runtime_verification():
    trace = load("traceability.json")
    assert trace
    assert {x["verification_status"] for x in trace} <= {"test-linked", "unvalidated"}
    assert all("does not by itself prove runtime verification" in x["note"] for x in trace)


def test_vocabulary_unique_and_semantically_independent():
    vocabulary = load("vocabulary.json")
    names = [x["name"] for x in vocabulary]
    assert len(names) == len(set(names))
    by_name = {x["name"]: x for x in vocabulary}
    assert "operationally healthy" in by_name["verified"]["does_not_prove"]
    assert "Semantic mismatch" in by_name["degraded"]["does_not_prove"]
    assert by_name["verified-with-mapped-presentation"]["description"]


def test_operational_health_is_independent_from_semantic_parity():
    health = {x["domain"]: x for x in load("operational-health.json")}
    canonical_health = json.loads(
        (
            ROOT
            / "contracts/generated/runtime/domain-operational-health.json"
        ).read_text(encoding="utf-8")
    )["domains"]

    assert health["home"]["runtime_parity"] == (
        canonical_health["home"]["semantic_parity"]
    )
    assert health["home"]["operational_health"] == (
        canonical_health["home"]["operational_health"]
    )
    assert health["home"]["degraded_reason"] == (
        canonical_health["home"]["reason"]
    )
    assert health["apps"]["operational_health"] == "healthy"
    assert health["devices"]["operational_health"] == "healthy"
    assert health["security"]["operational_health"] == "healthy"
    recovery = health["recovery"]

    assert recovery["runtime_parity"] == (
        canonical_health["recovery"]["semantic_parity"]
    )
    assert recovery["operational_health"] == (
        canonical_health["recovery"]["operational_health"]
    )
    assert recovery["degraded_reason"] == (
        canonical_health["recovery"]["reason"]
    )


def test_freshness_dashboard_is_pre_generated_and_release_bound():
    freshness = load("freshness.json")
    runtime = json.loads(RUNTIME_BASELINE.read_text(encoding="utf-8"))
    assert freshness["promoted_release"] == runtime["release_tag"]
    assert freshness["promoted_source_commit"] == runtime["source_commit"]
    assert freshness["runtime_evidence_sanitized"] is True
    assert freshness["operational_health_source_fingerprint"] == json.loads(
        (ROOT / "contracts/generated/runtime/domain-operational-health.json").read_text(encoding="utf-8")
    )["source_fingerprint"]
    assert set(freshness["operational_degradation"]) <= {
        x["domain"] for x in load("operational-health.json")
    }


def test_knowledge_export_sanitization_and_no_private_paths(graph):
    raw = json.dumps(graph, sort_keys=True)
    forbidden = [
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"Bearer\s+[A-Za-z0-9._~+/-]{12,}",
        r"/data/data/com\.termux/files/(?:home|usr)",
        r"/home/[^/\s]+",
        r"nats://[^\s/@]+:[^\s/@]+@",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, raw, re.I)


def test_component_encyclopedia_covers_canonical_architecture():
    arch = json.loads((ROOT / "architecture/metadata/pocket-lab-architecture.json").read_text())
    components = load("components.json")
    assert {x["id"].split(":", 1)[1] for x in components} == set(arch["components"])
    for component in components:
        page = DEV / "components" / f"{component['id'].split(':', 1)[1]}.md"
        text = page.read_text()
        assert "## Depends on / uses" in text
        assert "## Used by / backlinks" in text
        assert "## Canonical sources" in text


def test_identity_rules_relationships_are_source_backed_and_discoverable():
    arch = json.loads((ROOT / "architecture/metadata/pocket-lab-architecture.json").read_text())
    assert "identity-access-controls" in arch["components"]
    assert arch["components"]["identity-access-controls"]["security_boundary"] == "control-api"
    assert {"webauthn_credentials", "enterprise_memberships"} <= set(
        arch["components"]["identity-access-controls"]["durable_state_dependencies"]
    )
    assert {"policy_revisions", "policy_approvals", "policy_temporary_exceptions"} <= set(
        arch["components"]["opa-policy-engine"]["durable_state_dependencies"]
    )
    edges = {(row["source"], row["target"]) for row in arch["connections"]}
    assert ("identity-access-controls", "sqlite") in edges

    for domain, journey in (("identity", "identity"), ("rules", "rules")):
        page = ROOT / "docs/generated/enterprise/knowledgebase/domains" / f"{domain}.md"
        text = page.read_text(encoding="utf-8")
        assert f"../../journeys/{journey}.md" in text
        assert "../../reference/api-ui-trace.md" in text


def test_search_terms_are_discoverable_in_generated_pages():
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in list(DEV.rglob("*.md")) + list(PROD.rglob("*.md")))
    for term in ("projection_too_old", "Restart Agent", "NATS", "security_database_restores", "PhotoPrism", "Tailscale", "supervisor", "FastAPI"):
        assert term in corpus


def test_generator_check_and_deterministic_second_build():
    before = hashlib.sha256((KNOWLEDGE / "index.json").read_bytes()).hexdigest()
    for _ in range(2):
        result = subprocess.run([sys.executable, str(GENERATOR), "check"], cwd=ROOT, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    after = hashlib.sha256((KNOWLEDGE / "index.json").read_bytes()).hexdigest()
    assert before == after

def test_mkdocs_release_nav_is_generator_owned_and_complete():
    text = MKDOCS.read_text(encoding="utf-8")
    for audience, root in (("development", DEV), ("production", PROD)):
        begin = f"# BEGIN GENERATED KNOWLEDGE RELEASE NAV: {audience}"
        end = f"# END GENERATED KNOWLEDGE RELEASE NAV: {audience}"
        assert text.count(begin) == 1
        assert text.count(end) == 1
        block = text.split(begin, 1)[1].split(end, 1)[0]
        expected = {
            p.relative_to(ROOT / "docs").as_posix()
            for p in (root / "releases").glob("*.md")
        }
        assert expected
        for path in expected:
            assert path in block
        stale = set(re.findall(r"generated/(?:development|production)/knowledge/releases/[^\s]+\.md", block))
        assert stale == expected


def test_knowledge_graph_is_enterprise_knowledgebase_surface(graph):
    page = ENTERPRISE_KB / "knowledge-graph.md"
    assert page.exists()
    assert not (DEV / "knowledge-graph.md").exists()
    text = page.read_text(encoding="utf-8")
    assert "# Knowledge Graph" in text
    assert 'class="pl-kpi-grid pl-kg-kpis"' in text
    assert "## Graph integrity" in text
    assert "## Entity taxonomy" in text
    assert "## Relation taxonomy" in text
    assert "## Domain connectivity" in text
    assert "## Explore an entity" in text
    assert "## Go deeper" in text
    assert "## AI-ready canonical graph" in text
    assert str(len(graph["entities"])) in text
    assert str(len(graph["relations"])) in text

    nav = MKDOCS.read_text(encoding="utf-8")
    assert "Knowledge Graph: generated/enterprise/knowledgebase/knowledge-graph.md" in nav
    assert "generated/development/knowledge/knowledge-graph.md" not in nav


def test_knowledge_graph_explorer_projection_is_bounded_and_provenance_preserving(graph):
    payload = json.loads((KNOWLEDGE_ASSETS / "knowledge-graph-explorer.json").read_text(encoding="utf-8"))
    assert payload["source"] == "contracts/generated/knowledge/index.json"
    assert payload["live_runtime"] is False
    assert payload["max_hops"] == 1
    assert len(payload["entities"]) == len(graph["entities"])
    assert len(payload["relations"]) == len(graph["relations"])
    entity_ids = {entity["id"] for entity in payload["entities"]}
    assert entity_ids == {entity["id"] for entity in graph["entities"]}
    assert all(relation["source"] in entity_ids and relation["target"] in entity_ids for relation in payload["relations"])
    canonical_relations = {relation["id"]: relation for relation in graph["relations"]}
    for relation in payload["relations"]:
        canonical = canonical_relations[relation["id"]]
        assert relation["type"] == canonical["type"]
        assert relation["evidence"] == canonical["evidence"]
        assert relation["derivation"]["method"] == "deterministic-canonical-correlation"
        assert relation["derivation"]["generator"] == "scripts/docs/knowledge/generate_knowledge.py"


def test_knowledge_graph_integrity_projection_matches_canonical_graph(graph):
    page = (ENTERPRISE_KB / "knowledge-graph.md").read_text(encoding="utf-8")
    entity_ids = {entity["id"] for entity in graph["entities"]}
    dangling = [
        relation for relation in graph["relations"]
        if relation["source"] not in entity_ids or relation["target"] not in entity_ids
    ]
    entities_with_sources = sum(bool(entity.get("source_refs")) for entity in graph["entities"])
    relations_with_evidence = sum(bool(relation.get("evidence")) for relation in graph["relations"])
    assert not dangling
    assert f"{entities_with_sources} / {len(graph['entities'])}" in page
    assert f"{relations_with_evidence} / {len(graph['relations'])}" in page
    assert "Dangling relations</span><strong>0</strong>" in page
    assert "Unsupported predicates</span><strong>0</strong>" in page


def test_knowledge_graph_ontology_svg_is_static_bounded_and_external_runtime_free():
    svg = (KNOWLEDGE_ASSETS / "knowledge-graph-ontology.svg").read_text(encoding="utf-8")
    assert "Pocket Lab Lite bounded knowledge graph ontology" in svg
    assert "Entity taxonomy" in svg
    assert "Relation taxonomy" in svg
    assert "Domain mapping" in svg
    assert "<script" not in svg.lower()
    assert "foreignObject" not in svg
    assert 'href="http' not in svg.lower()
    assert 'xlink:href="http' not in svg.lower()
    assert svg.count('<rect class="panel"') == 3


def test_knowledge_graph_accessibility_contract_is_deterministic():
    page = ROOT / "docs/generated/enterprise/knowledgebase/knowledge-graph.md"
    text = page.read_text(encoding="utf-8")
    assert 'width="1200" height="470" loading="eager" decoding="async"' in text
    assert 'loading="lazy"' not in text
    assert 'role="region" aria-label="Knowledge Graph domain connectivity table" tabindex="0"' in text

    css = (ROOT / "docs/stylesheets/intelligence.css").read_text(encoding="utf-8")
    assert ".pl-kg-domain-table .md-typeset__table { overflow: visible; }" in css
    assert ".pl-kg-taxonomy-card .pl-card-kicker" in css
    assert ".pl-kg-result small" in css


def test_knowledge_graph_explorer_javascript_is_static_one_hop_and_has_fail_closed_guards():
    script = (ROOT / "docs/javascripts/docs.js").read_text(encoding="utf-8")
    start = script.index("const enhanceKnowledgeGraph")
    end = script.index("const enhanceAudienceIdentity", start)
    block = script[start:end]
    assert "generated/assets/knowledge/knowledge-graph-explorer.json" in block
    assert "payload.max_hops !== 1" in block
    assert "payload.live_runtime !== false" in block
    assert "dangling browser projection relation" in block
    assert "entity count mismatch" in block
    assert "relation count mismatch" in block
    assert "credentials: 'same-origin'" in block
    assert "api.github.com" not in block
    assert "/api/lite/" not in block
    assert "nats://" not in block
    for forbidden in ("setInterval(", "setTimeout(", "requestAnimationFrame(", "WebSocket(", "EventSource("):
        assert forbidden not in block
