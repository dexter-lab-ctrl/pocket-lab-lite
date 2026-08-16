from __future__ import annotations

import json
import subprocess
from itertools import product
from pathlib import Path, PurePosixPath

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "contracts/generated/knowledge/repository-codebase-map.json"
BROWSER_PATH = ROOT / "docs/generated/assets/knowledge/repository-codebase-map.json"
SCHEMA_PATH = ROOT / "schemas/knowledge/repository-codebase-map.schema.json"
PAGE_PATH = ROOT / "docs/generated/development/knowledge/codebase-map.md"
JS_PATH = ROOT / "docs/javascripts/codebase-map.js"
CSS_PATH = ROOT / "docs/stylesheets/codebase-map.css"
REPO_MAP_PAGE = ROOT / "docs/generated/development/knowledge/repository-map.md"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_files() -> set[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return {item.decode() for item in raw.split(b"\0") if item}


def test_codebase_map_schema_and_git_inventory_are_exact():
    model = load(MODEL_PATH)
    jsonschema.Draft202012Validator(load(SCHEMA_PATH)).validate(model)
    file_nodes = {node["path"] for node in model["nodes"] if node["kind"] == "file"}
    assert file_nodes == tracked_files()
    assert model["statistics"]["tracked_files"] == len(file_nodes)
    assert model["topology"]["repository_inventory"] == "git ls-files"
    assert model["capabilities"]["live_runtime"] is False


def test_codebase_map_paths_parents_and_relationship_endpoints_are_closed():
    model = load(MODEL_PATH)
    nodes = {node["id"]: node for node in model["nodes"]}
    external = set(model["topology"]["external_entities"])
    assert len(nodes) == len(model["nodes"])
    assert len(model["indexes"]["by_path"]) == len(model["nodes"])

    for node in model["nodes"]:
        if node["path"] != ".":
            assert not node["path"].startswith("/")
            assert "\\" not in node["path"]
            assert ".." not in PurePosixPath(node["path"]).parts
        if node["parent_id"]:
            assert node["parent_id"] in nodes

    for relation in model["relationships"]:
        assert relation["source"] in nodes or relation["source"] in external
        assert relation["target"] in nodes or relation["target"] in external


def test_directory_indexes_reconcile_with_node_parents():
    model = load(MODEL_PATH)
    nodes = {node["id"]: node for node in model["nodes"]}
    children = model["indexes"]["children_by_parent"]
    observed = {}
    for node in model["nodes"]:
        if node["parent_id"]:
            observed.setdefault(node["parent_id"], []).append(node["id"])
    assert {k: sorted(v) for k, v in observed.items()} == children
    for directory in (node for node in model["nodes"] if node["kind"] == "directory"):
        direct = children.get(directory["id"], [])
        assert directory["facts"]["child_count"] == len(direct)
        assert all(child in nodes for child in direct)


def test_facts_explanations_and_critical_coverage_are_explicit():
    model = load(MODEL_PATH)
    file_nodes = [node for node in model["nodes"] if node["kind"] == "file"]
    assert model["documentation_health"]["parser_failures"] == 0
    assert model["documentation_health"]["critical_explained"] == model["documentation_health"]["critical_paths"]
    for node in file_nodes:
        assert node["role"]
        assert node["execution_owner"]
        explanation = node["explanation"]
        assert explanation["purpose"]
        assert explanation["confidence"] in {
            "verified", "source-derived", "contract-derived", "path-derived", "generated", "stale", "unvalidated"
        }
        assert explanation["freshness_status"] in {"current", "stale", "unvalidated"}
        assert explanation["evidence_refs"]
        assert explanation["evidence_hash"].startswith("sha256:")


def test_relationship_reverse_indexes_match_forward_relations():
    model = load(MODEL_PATH)
    rels = {rel["id"]: rel for rel in model["relationships"]}
    forward = model["indexes"]["relationships_from"]
    reverse = model["indexes"]["relationships_to"]
    for rid, rel in rels.items():
        assert rid in forward.get(rel["source"], [])
        assert rid in reverse.get(rel["target"], [])
    assert any(rel["type"] == "IMPORTS" for rel in rels.values())
    assert any(rel["type"] == "TESTED_BY" for rel in rels.values())
    assert any(rel["type"] == "GENERATED_BY" for rel in rels.values())
    assert any(rel["type"] == "INVOKED_BY_TASK" for rel in rels.values())
    assert any(rel["type"] == "MAPS_TO_KNOWLEDGE" for rel in rels.values())
    assert any(rel["type"] == "MAPS_TO_ARCHITECTURE" for rel in rels.values())


def test_browser_projection_is_static_compact_and_resolvable():
    model = load(MODEL_PATH)
    browser = load(BROWSER_PATH)
    assert browser["live_runtime"] is False
    assert browser["source_fingerprint"] == model["source_fingerprint"]
    assert browser["statistics"]["tracked_files"] == model["statistics"]["tracked_files"]
    node_ids = {node["id"] for node in browser["nodes"]}
    assert browser["root_id"] in node_ids
    assert set(browser["indexes"]["by_path"].values()) == node_ids
    assert set(browser["indexes"]["search"]) == node_ids
    # Browser projection is intentionally smaller than the canonical evidence model.
    assert BROWSER_PATH.stat().st_size < MODEL_PATH.stat().st_size
    assert BROWSER_PATH.stat().st_size < 10_000_000


def test_codebase_map_runtime_network_and_sensitive_data_fence():
    browser_text = BROWSER_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")
    combined = browser_text + js
    forbidden = (
        "api.github.com", "githubusercontent.com", "sourcegraph.com", "WebSocket(", "EventSource(",
        "nats://", "/data/data/com.termux/files/home", "/home/dj/", "C:\\Users\\",
    )
    for token in forbidden:
        assert token not in combined
    assert "generated/assets/knowledge/repository-codebase-map.json" in js
    assert "credentials: 'same-origin'" in js


def test_deep_link_search_filter_and_bounded_impact_contracts_are_present():
    js = JS_PATH.read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    page = PAGE_PATH.read_text(encoding="utf-8")
    for marker in (
        "new URL(window.location.href)", "searchParams.get('path')", "searchParams.get('symbol')", "safePath", "popstate",
        "document$.subscribe", "mountCodebaseMap", "root.isConnected",
        "relationships_from", "relationships_to", "for (let depth = 1; depth <= 2", "visited.size >= 42",
    ):
        assert marker in js
    for marker in ("data-cb-search", "data-cb-role", "data-cb-language", "data-cb-owner", "data-cb-confidence"):
        assert marker in page
    assert "@media (max-width: 52rem)" in css
    assert "prefers-reduced-motion: reduce" in css


def test_repository_map_keeps_reverse_source_to_knowledge_semantics():
    text = REPO_MAP_PAGE.read_text(encoding="utf-8")
    assert "reverse lookup from source paths to generated knowledge entities" in text
    assert "Codebase Map" in text
    assert "Repository Map retains reverse source→Knowledge semantics" in text



def test_codebase_map_has_reciprocal_documentation_platform_links():
    architecture = (ROOT / "docs/generated/production/architecture/index.md").read_text(encoding="utf-8")
    knowledge_graph = (ROOT / "docs/generated/enterprise/knowledgebase/knowledge-graph.md").read_text(encoding="utf-8")
    repository_map = REPO_MAP_PAGE.read_text(encoding="utf-8")
    platform = (ROOT / "docs/generated/enterprise/documentation-platform/index.md").read_text(encoding="utf-8")
    codebase = PAGE_PATH.read_text(encoding="utf-8")

    assert "Codebase Map" in architecture
    assert "Codebase Map" in knowledge_graph
    assert "Codebase Map" in repository_map
    assert "Codebase Map" in platform
    for label in ("Repository Map", "Knowledge Graph", "Architecture", "Change Impact Advisor"):
        assert label in codebase

def test_fixed_pairwise_style_classification_surface_is_deterministic():
    model = load(MODEL_PATH)
    files = [node for node in model["nodes"] if node["kind"] == "file"]
    roles = {node["role"] for node in files}
    owners = {node["execution_owner"] for node in files}
    confidence = {node["explanation"]["confidence"] for node in files}
    # Small deterministic permutation surface: combinations are checked for safe vocabulary,
    # not required to all occur in the repository.
    allowed_roles = {"Frontend", "FastAPI", "Worker", "Node Agent", "Supervisor", "Documentation", "Generated documentation", "Test", "Contract", "Generated contract", "Architecture", "Build tooling", "Development tooling", "CI/CD", "Schema", "Security", "Runbook", "Configuration", "Dependency manifest", "Asset", "Application source", "Unknown"}
    allowed_owners = {"Browser", "Caddy", "FastAPI", "Worker", "Node Agent", "Supervisor", "Build-only", "Documentation-only", "CI-only", "Release-only", "Test-only", "No runtime execution", "Unknown"}
    assert roles <= allowed_roles
    assert owners <= allowed_owners
    assert confidence <= {"verified", "source-derived", "contract-derived", "path-derived", "generated", "stale", "unvalidated"}
    for role, owner in list(product(sorted(roles)[:6], sorted(owners)[:6]))[:24]:
        assert "\n" not in role + owner

def test_codebase_map_generation_runs_last_in_docs_generate() -> None:
    taskfile = Path("tasks/Taskfile.docs.yml").read_text(encoding="utf-8")

    start = taskfile.index("  lite:docs:generate:")
    end = taskfile.index("\n  lite:docs:sync:", start)
    block = taskfile[start:end]

    codebase_map = block.index(
        "- task: lite:docs:codebase-map:generate"
    )

    for source_generator in (
        "- task: lite:docs:intelligence:generate",
        "- task: lite:docs:enterprise:generate",
        "- task: lite:docs:architecture:generate",
        "- task: lite:docs:development:generate",
        "- task: lite:docs:production:generate",
        "scripts/docs/sqlite/generate_schemaspy.py generate",
        "- task: lite:docs:diagrams:generate",
    ):
        assert block.index(source_generator) < codebase_map, (
            f"{source_generator} must run before "
            "lite:docs:codebase-map:generate"
        )
