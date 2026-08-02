from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_PATH = ROOT / "scripts/docs/lite/generate_platform_catalogs.py"
GRAPHVIZ_PATH = ROOT / "scripts/docs/graphviz/generate_lite_diagrams.py"
SCHEMASPY_PATH = ROOT / "scripts/docs/sqlite/generate_schemaspy.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_platform_outputs_are_deterministic_current_and_safe():
    platform = load_module("platform_docs_test", PLATFORM_PATH)
    first = platform.build_outputs("all")
    second = platform.build_outputs("all")
    assert first == second
    assert platform.validate_output_safety(first) == []
    assert platform.check_outputs(first) == 0
    required = {
        "contracts/generated/frontend-api-usage.json",
        "contracts/generated/api-compatibility.json",
        "contracts/generated/lite-asyncapi.json",
        "contracts/generated/device-capabilities.json",
        "contracts/generated/device-roles.json",
        "contracts/generated/ui-state-catalog.json",
        "contracts/generated/recovery-contract.json",
        "contracts/generated/security-profiles.json",
        "contracts/generated/lite-sqlite-schema.json",
        "contracts/generated/projection-catalog.json",
        "contracts/generated/reason-codes.json",
        "contracts/generated/configuration-reference.json",
        "contracts/generated/service-catalog.json",
        "contracts/generated/bootstrap-stages.json",
        "contracts/generated/redaction-coverage.json",
        "contracts/generated/documentation-links.json",
        "docs/reference/api/lite-api.md",
    }
    actual = {path.relative_to(ROOT).as_posix() for path in first}
    assert required <= actual


def test_frontend_api_mapping_resolves_active_calls_and_tracks_unused_backend_routes():
    platform = load_module("platform_frontend_test", PLATFORM_PATH)
    inventory, unsupported, unused = platform.frontend_inventory()
    assert inventory
    assert unsupported == []
    assert any(item["source_module"] == "src/lite/LiteSecurity.jsx" and item["owner"].startswith("liteApi.") for item in inventory)
    assert all(item["route"].startswith("/api/lite/") for item in inventory)
    assert isinstance(unused, list)
    payload = json.loads((ROOT / "contracts/generated/frontend-api-usage.json").read_text())
    assert payload["frontend_api_usage"]["unsupported_frontend_routes"] == []


def test_field_level_compatibility_detects_breaking_and_non_breaking_changes():
    platform = load_module("platform_compat_test", PLATFORM_PATH)
    baseline = {
        "paths": {"/api/lite/example": {"get": {"responses": {"200": {}}}}},
        "components": {"schemas": {"Example": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "mode": {"type": "string", "enum": ["a", "b"]}}}}},
    }
    current = {
        "paths": {"/api/lite/example": {"get": {"responses": {"200": {}, "202": {}}}}, "/api/lite/new": {"get": {"responses": {"200": {}}}}},
        "components": {"schemas": {"Example": {"type": "object", "required": ["id", "name"], "properties": {"id": {"type": "integer"}, "name": {"type": "string"}, "mode": {"type": "string", "enum": ["a", "b", "c"]}}}}},
    }
    changes = platform.compatibility_changes(current, baseline)
    kinds = {(item["classification"], item["kind"]) for item in changes}
    assert ("breaking", "type_changed") in kinds
    assert ("breaking", "field_became_required") in kinds
    assert ("non_breaking", "enum_added") in kinds
    assert ("non_breaking", "status_added") in kinds
    assert ("non_breaking", "path_added") in kinds


def test_sqlite_generation_uses_only_temporary_data_free_database():
    platform = load_module("platform_sqlite_test", PLATFORM_PATH)
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "schema.sqlite3"
        migrations = platform.build_empty_database(database)
        assert migrations
        connection = sqlite3.connect(database)
        try:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            assert tables
            for table in tables:
                escaped = table.replace('"', '""')
                assert connection.execute(f'SELECT COUNT(*) FROM "{escaped}"').fetchone()[0] == 0
        finally:
            connection.close()
    schema = json.loads((ROOT / "contracts/generated/lite-sqlite-schema.json").read_text())
    assert schema["lite_sqlite_schema"]["row_count_enforced"] == 0
    assert schema["lite_sqlite_schema"]["objects"]


def test_reason_codes_capabilities_roles_and_services_are_unique_and_complete():
    metadata = json.loads((ROOT / "contracts/metadata/documentation-platform.json").read_text())
    codes = [item["code"] for item in metadata["reason_codes"]]
    assert len(codes) == len(set(codes))
    assert set(metadata["capability_states"]) == {"verified", "pending", "unavailable", "not_advertised", "expired", "stale"}
    capability_names = {item["name"] for item in metadata["capabilities"]}
    for role in metadata["roles"]:
        assert set(role["required_capabilities"]) <= capability_names
    patterns = {item["pattern"] for item in metadata["services"]}
    assert {"pocket-api", "pocket-worker", "pocket-nats", "pocket-node-agent", "pocketlab-agent-<node_id>", "pocketlab-agent-supervisor-<node_id>"} <= patterns


def test_graphviz_outputs_have_accessible_light_dark_svg_and_relative_links():
    subprocess.run(["python3", str(GRAPHVIZ_PATH), "check"], cwd=ROOT, check=True)
    manifest = json.loads((ROOT / "docs/assets/diagrams/manifest.json").read_text())
    assert manifest["diagram_count"] == 8
    for name in (
        "control-plane", "runtime-deployment", "device-onboarding", "recovery-state-machine",
        "agent-supervisor-recovery", "projection-flow", "trust-boundaries", "release-flow",
    ):
        for theme in ("light", "dark"):
            svg = (ROOT / f"docs/assets/diagrams/{name}.{theme}.svg").read_text()
            assert '<title id="' in svg
            assert '<desc id="' in svg
            assert 'role="img"' in svg
            assert "xlink:href=\"../" in svg or "href=\"../" in svg
            assert not re.search(r"(?:/home/[A-Za-z0-9._-]+/|/mnt/[A-Za-z]/|(?<![A-Za-z])[A-Za-z]:[\\/])", svg)


def test_schemaspy_generator_is_pinned_data_free_and_fail_closed():
    setup = (ROOT / "scripts/dev/lite/setup-documentation-tools.sh").read_text()
    generator = SCHEMASPY_PATH.read_text()
    for value in ("6.2.4", "3.46.1.0", "sha256sum --check", "--install-missing"):
        assert value in setup
    assert "build_empty_database" in generator
    assert '"-norows"' in generator
    assert "never opens a live database" not in generator.lower() or "temporary" in generator.lower()
    assert "POCKETLAB_SCHEMASPY_JAR" in generator
    assert "POCKETLAB_SQLITE_JDBC_JAR" in generator
    assert "sqlite-xerial" in generator
    assert not list(ROOT.rglob("*.jar"))


def test_documentation_tasks_and_mkdocs_navigation_are_wired():
    taskfile = (ROOT / "tasks/Taskfile.docs.yml").read_text()
    for task in (
        "lite:docs:openapi", "lite:docs:events", "lite:docs:frontend-api", "lite:docs:capabilities",
        "lite:docs:reason-codes", "lite:docs:sqlite", "lite:docs:projections", "lite:docs:bootstrap",
        "lite:docs:services", "lite:docs:ui", "lite:docs:validation", "lite:docs:release-evidence",
        "lite:docs:redaction", "lite:docs:diagrams:generate", "lite:docs:diagrams:check",
        "lite:docs:sqlite:check", "lite:docs:tools:check",
    ):
        assert f"  {task}:" in taskfile
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    for page in (
        "reference/api/lite-api.md", "generated/development/lite-events.md",
        "generated/development/lite-sqlite-schema.md", "generated/development/projection-catalog.md",
        "generated/development/ui-state-catalog.md", "generated/development/redaction-coverage.md",
    ):
        assert page in mkdocs


def test_generated_artifacts_exclude_absolute_paths_and_secret_values():
    forbidden_paths = re.compile(r"(?:/home/[A-Za-z0-9._-]+/|/data/data/[^/]+/|/mnt/[A-Za-z]/|(?<![A-Za-z])[A-Za-z]:[\\/])")
    forbidden_secret = re.compile(r"(?i)(?:password|token|secret|api[_-]?key)\s*[:=]\s*[^\s<]{4,}")
    for root in (ROOT / "contracts/generated", ROOT / "docs/generated/development", ROOT / "docs/reference/api", ROOT / "docs/assets/diagrams"):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".svg", ".dot"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not forbidden_paths.search(text), path
            assert not forbidden_secret.search(text), path
