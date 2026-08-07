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
GENERATOR = ROOT / "scripts/docs/knowledge/generate_knowledge.py"
RUNTIME_BASELINE = ROOT / "contracts/parity/runtime-verification-baseline.json"
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
    assert {x["status"] for x in matrix} <= {"implemented", "observed", "unvalidated"}


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
    recovery = health["recovery"]
    assert recovery["runtime_parity"] == "verified-with-mapped-presentation"
    assert recovery["operational_health"] == "degraded"
    assert recovery["degraded_reason"] == "projection_too_old"


def test_freshness_dashboard_is_pre_generated_and_release_bound():
    freshness = load("freshness.json")
    runtime = json.loads(RUNTIME_BASELINE.read_text(encoding="utf-8"))
    assert freshness["promoted_release"] == runtime["release_tag"]
    assert freshness["promoted_source_commit"] == runtime["source_commit"]
    assert freshness["runtime_evidence_sanitized"] is True
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
