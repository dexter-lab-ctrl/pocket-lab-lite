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
        assert not re.search(r'(?:src|href|xlink:href)=["\'](?:https?:)?//', svg, re.I)


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
        "externalAssetRequests",
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
