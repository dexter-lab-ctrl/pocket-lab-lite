from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GRAPHVIZ_DIR = ROOT / "scripts" / "docs" / "graphviz"
if str(GRAPHVIZ_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPHVIZ_DIR))

import architecture_model as model_module  # noqa: E402
import architecture_source_verifier as source_module  # noqa: E402
import generate_lite_architecture as generator_module  # noqa: E402
import graphviz_renderer as renderer_module  # noqa: E402
import icon_registry as icon_module  # noqa: E402


def _model() -> dict:
    return model_module.load_model(known_icons=icon_module.load_registry().keys())


def _file_hashes(paths: list[Path]) -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def test_canonical_architecture_model_schema_inventory_and_ownership():
    model = _model()
    assert model["schema_revision"] == 1
    assert len(model["components"]) >= 50
    assert len(model["connections"]) >= 80
    assert len(model["boundaries"]) >= 8
    assert len(model["views"]) >= 14
    assert len(model["components"]) == len(set(model["components"]))
    assert len(model["connections"]) == len({item["id"] for item in model["connections"]})
    assert len(model["views"]) == len(set(model["views"]))
    for component_id, component in model["components"].items():
        assert component["id"] == component_id
        for field in (
            "owner", "runtime_owner", "process_owner", "data_owner", "recovery_owner",
            "security_boundary", "verification_status",
        ):
            assert str(component[field]).strip(), (component_id, field)
        assert component["documentation_links"], component_id
        assert component["source_verification"], component_id


def test_model_validation_rejects_invalid_ids_boundaries_connections_and_ownership():
    model = _model()

    invalid_id = copy.deepcopy(model)
    first_id = next(iter(invalid_id["components"]))
    invalid_id["components"][first_id]["id"] = "Wrong_ID"
    with pytest.raises(model_module.ArchitectureModelError, match="key/id mismatch"):
        model_module.validate_model(invalid_id)

    invalid_boundary = copy.deepcopy(model)
    invalid_boundary["components"][first_id]["security_boundary"] = "missing-boundary"
    with pytest.raises(model_module.ArchitectureModelError, match="unknown boundary"):
        model_module.validate_model(invalid_boundary)

    missing_owner = copy.deepcopy(model)
    missing_owner["components"][first_id]["owner"] = ""
    with pytest.raises(model_module.ArchitectureModelError, match="field owner is empty"):
        model_module.validate_model(missing_owner)

    duplicate_connection = copy.deepcopy(model)
    duplicate_connection["connections"].append(copy.deepcopy(duplicate_connection["connections"][0]))
    with pytest.raises(model_module.ArchitectureModelError, match="Duplicate connection id"):
        model_module.validate_model(duplicate_connection)

    unknown_connection = copy.deepcopy(model)
    unknown_connection["connections"][0]["target"] = "not-a-component"
    with pytest.raises(model_module.ArchitectureModelError, match="unknown component"):
        model_module.validate_model(unknown_connection)


def test_orphan_detection_and_explicit_exemption_behavior():
    model = _model()
    orphan_id = next(
        component_id for component_id, component in model["components"].items()
        if not component["orphan_exempt"]
    )
    orphaned = copy.deepcopy(model)
    orphaned["connections"] = [
        edge for edge in orphaned["connections"]
        if edge["source"] != orphan_id and edge["target"] != orphan_id
    ]
    remaining_connection_ids = {edge["id"] for edge in orphaned["connections"]}
    for flow in orphaned["views"]["complete-system"]["poster"]["primary_flows"]:
        flow["connections"] = [
            connection_id for connection_id in flow["connections"]
            if connection_id in remaining_connection_ids
        ]
    with pytest.raises(model_module.ArchitectureModelError, match="orphaned"):
        model_module.validate_model(orphaned)

    exempted = copy.deepcopy(orphaned)
    exempted["components"][orphan_id]["orphan_exempt"] = True
    model_module.validate_model(exempted)


def test_model_normalization_and_fingerprints_are_stable():
    raw = json.loads(model_module.MODEL_PATH.read_text(encoding="utf-8"))
    first = model_module.normalize_model(raw)
    second = model_module.normalize_model(copy.deepcopy(raw))
    assert first == second
    assert model_module.fingerprint(first) == model_module.fingerprint(second)
    assert list(first["components"]) == sorted(first["components"])
    assert [item["id"] for item in first["connections"]] == sorted(
        item["id"] for item in first["connections"]
    )


def test_source_verifier_accepts_repository_truth_and_rejects_missing_route():
    model = _model()
    inventory = source_module.build_source_inventory(model)
    report = source_module.verify_sources(model, inventory)
    assert report["status"] == "verified"
    assert report["component_count"] == len(model["components"])
    assert report["verified_reference_count"] >= len(model["components"])

    broken = copy.deepcopy(model)
    component_id = next(iter(broken["components"]))
    broken["components"][component_id]["source_verification"] = [
        {"kind": "route", "value": "GET /api/lite/route-that-does-not-exist"}
    ]
    with pytest.raises(source_module.SourceVerificationError, match="missing FastAPI route"):
        source_module.verify_sources(broken, inventory)


def test_mini_diagrams_are_graph_derived_bounded_and_deterministic():
    model = _model()
    index = model_module.build_index(model)
    component_id = "lite-api"
    first = model_module.derive_mini_graph(model, index, component_id)
    second = model_module.derive_mini_graph(model, index, component_id)
    policy = model["mini_diagram_policy"]
    assert first == second
    assert first["component_id"] == component_id
    assert len(first["component_ids"]) <= policy["max_total_neighbors"] + 1
    assert len(first["connections"]) <= policy["max_incoming"] + policy["max_outgoing"]
    assert first["connections"] == sorted(first["connections"], key=lambda item: item["id"])
    if first["omitted_connection_count"]:
        assert first["additional_dependencies_label"] == policy["collapse_label"]


def test_icon_registry_checksums_licenses_and_svg_safety():
    records = icon_module.load_registry()
    assert records
    for record in records.values():
        icon_module.validate_icon(record)
        assert record.license
        assert re.fullmatch(r"[0-9a-f]{64}", record.sha256)

    record = next(iter(records.values()))
    payload = record.path.read_bytes()
    wrong_checksum = replace(record, sha256="0" * 64)
    with pytest.raises(icon_module.IconRegistryError, match="checksum mismatch"):
        icon_module.validate_svg_bytes(payload, wrong_checksum)

    unsafe_cases = (
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.invalid/a.svg"/></svg>',
        b'<html><body>not svg</body></html>',
    )
    for unsafe in unsafe_cases:
        unsafe_record = replace(record, sha256=hashlib.sha256(unsafe).hexdigest())
        with pytest.raises(icon_module.IconRegistryError):
            icon_module.validate_svg_bytes(unsafe, unsafe_record)


def test_icon_registry_rejects_license_omission(tmp_path: Path):
    registry = json.loads(icon_module.REGISTRY_PATH.read_text(encoding="utf-8"))
    del registry["icons"][0]["license"]
    path = tmp_path / "icon-sources.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(icon_module.IconRegistryError, match="missing: license"):
        icon_module.load_registry(path)


def test_graphviz_light_dark_rendering_is_stable_accessible_and_local_only():
    model = _model()
    index = model_module.build_index(model)
    icons = icon_module.load_registry()
    first, first_fallback = renderer_module.render_view(model, index, icons, "request-control")
    second, second_fallback = renderer_module.render_view(model, index, icons, "request-control")
    assert first == second
    assert first_fallback == second_fallback
    for theme in ("light", "dark"):
        dot = first[f"{theme}.dot"]
        svg = first[f"{theme}.svg"]
        assert dot.strip().startswith("digraph")
        assert '<title id="' in svg
        assert '<desc id="' in svg
        assert 'role="img"' in svg
        assert '<image href="../icons/' in svg
        assert 'preserveAspectRatio="xMidYMid meet"' in svg
        root = re.search(r'<svg[^>]+>', svg)
        assert root is not None
        assert re.search(r'\bwidth="[0-9]+(?:\.[0-9]+)?"', root.group(0))
        assert re.search(r'\bheight="[0-9]+(?:\.[0-9]+)?"', root.group(0))
        assert 'height="auto"' not in root.group(0)
        assert 'width="100%"' not in root.group(0)
        assert not re.search(r'(?:src|href|xlink:href)=["\'](?:https?:)?//', svg, re.I)



def test_architecture_presentation_is_responsive_and_density_aware():
    pages = (ROOT / "scripts/docs/graphviz/architecture_pages.py").read_text(encoding="utf-8")
    css = (ROOT / "docs/stylesheets/components.css").read_text(encoding="utf-8")
    renderer = (ROOT / "scripts/docs/graphviz/graphviz_renderer.py").read_text(encoding="utf-8")
    assert 'pl-architecture-diagram pl-architecture-diagram--{kind}' in pages
    assert 'kind = "component" if component else "system"' in pages
    assert 'WIDE_DIAGRAMS' in pages
    assert 'pl-architecture-diagram--wide' in css
    assert 'View full-size diagram' in pages
    assert 'overflow-x: auto' in css
    assert 'object-fit: contain' in css
    assert 'max-width: 72rem' in css
    assert 'VERTICAL_VIEW_IDS' in renderer
    assert 'ratio' in renderer and 'compress' in renderer
    assert '_wrap_label' in renderer

def test_unchanged_committed_svgs_do_not_require_graphviz(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(renderer_module.shutil, "which", lambda _name: None)
    outputs, _details = generator_module.build_outputs()
    assert outputs
    assert all(
        b"pocketlab-source-fingerprint" in payload
        for path, payload in outputs.items()
        if path.suffix == ".svg" and "icons" not in path.parts
    )


def test_generated_architecture_inventory_manifests_and_pairs_are_current():
    outputs, details = generator_module.build_outputs()
    assert generator_module.check(outputs) == 0
    assert details["manifest"]["component_count"] == len(details["model"]["components"])
    assert details["manifest"]["connection_count"] == len(details["model"]["connections"])
    assert details["manifest"]["mini_diagram_count"] >= 15
    required = {
        Path("docs/generated/production/architecture/index.md"),
        Path("docs/generated/production/architecture/component-catalog.md"),
        Path("contracts/generated/architecture-catalog.json"),
        Path("docs/assets/diagrams/production/manifest.json"),
    }
    assert required <= set(outputs)
    for component_id, component in details["model"]["components"].items():
        assert Path(f"docs/generated/production/architecture/components/{component_id}.md") in outputs
        if component["mini_diagram"]:
            for theme in ("light", "dark"):
                assert Path(
                    f"docs/assets/diagrams/production/components/{component_id}.{theme}.svg"
                ) in outputs


def test_two_consecutive_generation_runs_are_byte_identical():
    managed_roots = (
        ROOT / "docs/generated/production/architecture",
        ROOT / "docs/assets/diagrams/production",
    )
    before_paths = [path for root in managed_roots for path in root.rglob("*") if path.is_file()]
    before_paths.append(ROOT / "contracts/generated/architecture-catalog.json")
    before = _file_hashes(before_paths)
    subprocess.run(
        [sys.executable, str(GRAPHVIZ_DIR / "generate_lite_architecture.py"), "generate"],
        cwd=ROOT,
        check=True,
    )
    middle_paths = [path for root in managed_roots for path in root.rglob("*") if path.is_file()]
    middle_paths.append(ROOT / "contracts/generated/architecture-catalog.json")
    middle = _file_hashes(middle_paths)
    subprocess.run(
        [sys.executable, str(GRAPHVIZ_DIR / "generate_lite_architecture.py"), "generate"],
        cwd=ROOT,
        check=True,
    )
    after_paths = [path for root in managed_roots for path in root.rglob("*") if path.is_file()]
    after_paths.append(ROOT / "contracts/generated/architecture-catalog.json")
    after = _file_hashes(after_paths)
    assert before == middle == after


def test_mkdocs_tasks_ci_and_browser_contract_are_wired():
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for page in (
        "generated/production/architecture/index.md",
        "generated/production/architecture/complete-system.md",
        "generated/production/architecture/runtime-topology.md",
        "generated/production/architecture/network-boundaries.md",
        "generated/production/architecture/component-catalog.md",
    ):
        assert page in mkdocs
    assert mkdocs.count("Pocket Lab Lite Architecture:") == 1

    taskfile = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    for task in (
        "lite:docs:architecture:icons:check",
        "lite:docs:architecture:generate",
        "lite:docs:architecture:check",
        "lite:docs:architecture:validate",
    ):
        assert f"  {task}:" in taskfile
    assert "task: lite:docs:architecture:generate" in taskfile
    assert "task: lite:docs:architecture:check" in taskfile

    workflow = (ROOT / ".github/workflows/lite-quality.yml").read_text(encoding="utf-8")
    assert "test_lite_production_architecture_platform.py" in workflow

    browser_test = (ROOT / "tests/docs/mkdocs.spec.ts").read_text(encoding="utf-8")
    for marker in (
        "Pocket Lab Lite Architecture",
        "generated/production/architecture/",
        "generated/production/architecture/component-catalog",
        "failedRequests",
    ):
        assert marker in browser_test


def test_generated_outputs_have_no_secrets_absolute_paths_or_broken_links():
    outputs, details = generator_module.build_outputs()
    generator_module.validate_outputs(outputs, details)
    forbidden_paths = re.compile(
        r"(?:/home/[^/\s]+|/data/data/com\.termux|/mnt/[a-z]/|/tmp/|(?<![A-Za-z])[A-Za-z]:[\\/])",
        re.I,
    )
    forbidden_secret = re.compile(
        r"(?i)(?:password|token|secret|api[_-]?key)\s*[:=]\s*[^\s<]{4,}"
    )
    for path, payload in outputs.items():
        if path.suffix not in {".json", ".md", ".dot", ".svg"}:
            continue
        text = payload.decode("utf-8")
        assert not forbidden_paths.search(text), path
        assert not forbidden_secret.search(text), path


def test_broken_generated_link_is_rejected():
    outputs, details = generator_module.build_outputs()
    broken = dict(outputs)
    page = Path("docs/generated/production/architecture/index.md")
    broken[page] = outputs[page] + b"\n[Broken](missing-generated-page.md)\n"
    with pytest.raises(generator_module.ArchitectureGenerationError, match="broken generated link"):
        generator_module.validate_outputs(broken, details)


def test_hybrid_icon_taxonomy_provenance_and_active_component_mapping():
    records = icon_module.load_registry()
    model = _model()
    assert {record.icon_class for record in records.values()} == {"brand", "semantic"}
    assert sum(record.icon_class == "brand" for record in records.values()) >= 15
    assert sum(record.icon_class == "semantic" for record in records.values()) >= 20

    for record in records.values():
        icon_module.validate_icon(record)
        if record.icon_class == "brand":
            assert "/brands/" in f"/{record.local_path}"
            assert record.source_type == "remote"
            assert record.upstream_project.strip()
            assert record.source_revision.strip()
            assert record.trademark_note.strip()
            assert record.allowed_redirect_hosts
        assert record.dark_mode_suitable
        assert record.light_mode_suitable

    expected_brands = {
        "caddy": "brand-caddy",
        "lite-api": "brand-fastapi",
        "nats-jetstream": "brand-nats",
        "sqlite": "brand-sqlite",
        "pm2": "brand-pm2",
        "tailscale": "brand-tailscale",
        "photoprism": "brand-photoprism",
        "proot-ubuntu": "brand-ubuntu",
        "github-repository": "brand-github",
        "github-release": "brand-github",
        "pwa": "brand-react",
    }
    for component_id, icon_id in expected_brands.items():
        assert model["components"][component_id]["icon"] == icon_id
        assert records[icon_id].icon_class == "brand"

    internal_components = {
        "api-guards", "api-domain-surfaces", "command-lifecycle", "completion-evidence",
        "prepared-state", "device-state", "invite-state", "recovery-state",
        "security-state", "agent-recovery", "agent-supervisor", "worker",
    }
    for component_id in internal_components:
        icon_id = model["components"][component_id]["icon"]
        assert records[icon_id].icon_class == "semantic", (component_id, icon_id)

    for component_id, component in model["components"].items():
        assert component["icon"] in records
        active_record = records[component["icon"]]
        expected_folder = "brands" if active_record.icon_class == "brand" else "semantic"
        assert f"architecture/icons/{expected_folder}/" in active_record.local_path, component_id
        assert len(component.get("technology_icons", [])) == len(
            set(component.get("technology_icons", []))
        )
        assert set(component.get("technology_icons", [])) <= set(records), component_id


def test_icon_registry_rejects_duplicates_and_missing_brand_provenance(tmp_path: Path):
    registry = json.loads(icon_module.REGISTRY_PATH.read_text(encoding="utf-8"))

    duplicate = copy.deepcopy(registry)
    duplicate["icons"].append(copy.deepcopy(duplicate["icons"][0]))
    duplicate_path = tmp_path / "duplicate-icon-sources.json"
    duplicate_path.write_text(json.dumps(duplicate), encoding="utf-8")
    with pytest.raises(icon_module.IconRegistryError, match="Duplicate icon id"):
        icon_module.load_registry(duplicate_path)

    missing_provenance = copy.deepcopy(registry)
    brand = next(item for item in missing_provenance["icons"] if item["icon_class"] == "brand")
    brand["trademark_note"] = ""
    provenance_path = tmp_path / "missing-provenance-icon-sources.json"
    provenance_path.write_text(json.dumps(missing_provenance), encoding="utf-8")
    with pytest.raises(icon_module.IconRegistryError, match="empty provenance field trademark_note"):
        icon_module.load_registry(provenance_path)


def test_icon_check_mode_is_idempotent_and_read_only():
    tracked = [icon_module.REGISTRY_PATH, icon_module.LICENSES_PATH]
    tracked.extend(record.path for record in icon_module.load_registry().values())
    before = _file_hashes(tracked)
    completed = subprocess.run(
        [sys.executable, str(GRAPHVIZ_DIR / "icon_registry.py"), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout
    assert before == _file_hashes(tracked)


def test_failed_icon_refresh_preserves_previous_valid_asset(monkeypatch: pytest.MonkeyPatch):
    source = next(
        record for record in icon_module.load_registry().values()
        if record.icon_class == "brand"
    )
    test_path = ROOT / "architecture/icons/brands/test-preserve-refresh.svg"
    test_path.write_bytes(source.path.read_bytes())
    test_record = replace(
        source,
        id="test-preserve-refresh",
        local_path=test_path.relative_to(ROOT).as_posix(),
    )
    before = test_path.read_bytes()

    def fail_download(**_kwargs):
        raise icon_module.IconRegistryError("simulated download failure")

    monkeypatch.setattr(icon_module, "_download_url", fail_download)
    try:
        with pytest.raises(icon_module.IconRegistryError, match="simulated download failure"):
            icon_module.install_icon(test_record)
        assert test_path.read_bytes() == before
    finally:
        test_path.unlink(missing_ok=True)


def test_arbitrary_icon_download_validates_and_stays_inside_icon_root(
    monkeypatch: pytest.MonkeyPatch,
):
    payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        b'<path d="M4 4h40v40H4z"/></svg>\n'
    )
    output = "architecture/icons/semantic/test-arbitrary-download.svg"
    target = ROOT / output

    def write_download(*, destination: Path, **_kwargs):
        destination.write_bytes(payload)

    monkeypatch.setattr(icon_module, "_download_url", write_download)
    try:
        assert icon_module.add_arbitrary_icon(
            icon_id="test-arbitrary-download",
            name="Test arbitrary download",
            url="https://icons.example.invalid/test.svg",
            output=output,
            allow_hosts=["icons.example.invalid"],
            maximum_size_bytes=8192,
        ) == 0
        assert target.read_bytes() == payload
        icon_module.validate_svg_structure(
            target.read_bytes(), icon_id="test-arbitrary-download", maximum_size_bytes=8192
        )
        with pytest.raises(icon_module.IconRegistryError, match="Unsafe icon path"):
            icon_module._safe_icon_path("../outside.svg")
    finally:
        target.unlink(missing_ok=True)


def test_complete_system_executive_poster_metadata_is_valid_and_deterministic():
    model = _model()
    view = model["views"]["complete-system"]
    poster = view["poster"]
    assert poster["layout_mode"] == "executive-poster"
    assert [zone["label"] for zone in poster["zones"]] == [
        "Zone A — Experience",
        "Zone B — Control plane",
        "Zone C — Event and execution",
        "Zone D — Durable state",
        "Zone E — Device runtime",
        "Zone F — Remote access and apps",
    ]
    assigned = [component for zone in poster["zones"] for component in zone["components"]]
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(view["components"])
    connection_ids = {item["id"] for item in model["connections"]}
    assert len(poster["primary_flows"]) == 8
    for flow in poster["primary_flows"]:
        assert set(flow["connections"]) <= connection_ids
    assert set(poster["trust_boundary_bands"]) <= set(model["boundaries"])
    assert model_module.normalize_model(model) == model_module.normalize_model(copy.deepcopy(model))


def test_complete_system_poster_graphviz_contains_zones_legend_primary_flows_and_local_icons():
    model = _model()
    index = model_module.build_index(model)
    icons = icon_module.load_registry()
    first, _ = renderer_module.render_view(model, index, icons, "complete-system")
    second, _ = renderer_module.render_view(model, index, icons, "complete-system")
    assert first == second
    for theme in ("light", "dark"):
        dot = first[f"{theme}.dot"]
        svg = first[f"{theme}.svg"]
        for label in (
            "Zone A — Experience", "Zone B — Control plane",
            "Zone C — Event and execution", "Zone D — Durable state",
            "Zone E — Device runtime", "Zone F — Remote access and apps",
            "Legend and flow key",
        ):
            assert label in dot
        assert 'penwidth="2.8"' in dot
        assert '1 · uses' in dot
        for filename in ("fastapi.svg", "nats.svg", "caddy.svg", "sqlite.svg", "evidence.svg"):
            assert f'<image href="../icons/{filename}"' in svg
        assert '<title id="' in svg and '<desc id="' in svg and 'role="img"' in svg
        assert not re.search(r'(?:href|xlink:href)=["\'](?:https?:)?//', svg, re.I)


def test_generated_icon_copies_match_authoritative_vendored_assets():
    outputs, _details = generator_module.build_outputs()
    for record in icon_module.load_registry().values():
        generated = Path("docs/assets/diagrams/production/icons") / record.path.name
        assert outputs[generated] == record.path.read_bytes(), record.id


def test_generated_poster_pages_include_accessible_text_equivalents_and_brand_assets():
    outputs, _details = generator_module.build_outputs()
    page = outputs[Path("docs/generated/production/architecture/complete-system.md")].decode()
    assert 'pl-architecture-diagram__image--light' in page
    assert 'pl-architecture-diagram__image--dark' in page
    assert '#only-light' not in page
    assert '#only-dark' not in page
    for marker in (
        "## Executive summary", "## Six architecture zones", "## Legend and icon key",
        "## Primary flows", "## Trust boundaries", "## Runtime technology stack",
        "## Architecture callouts", "Zone A — Experience", "Zone F — Remote access and apps",
    ):
        assert marker in page
    for icon in ("fastapi.svg", "nats.svg", "caddy.svg", "tailscale.svg"):
        assert f"icons/{icon}" in page
    assert "http://" not in page and "https://" not in page


def test_architecture_poster_does_not_use_inline_size_containment() -> None:
    css = (ROOT / "docs/stylesheets/components.css").read_text(encoding="utf-8")
    poster_rule = re.search(
        r"\.pl-architecture-diagram--poster\s*\{(?P<body>[^}]*)\}",
        css,
        flags=re.DOTALL,
    )
    assert poster_rule is not None
    body = poster_rule.group("body")
    assert "contain: inline-size" not in body
    assert "inline-size: 100%" in body
    assert "min-inline-size: 0" in body
