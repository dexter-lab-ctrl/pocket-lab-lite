#!/usr/bin/env python3
"""Generate and strictly check the Pocket Lab Lite Production architecture platform."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from architecture_model import ROOT, build_index, fingerprint, load_model
from architecture_pages import build_pages
from architecture_source_verifier import build_source_inventory, verify_sources
from graphviz_renderer import render_component, render_view
from icon_registry import load_registry, validate_icon

GENERATOR_VERSION = 1
MODEL_PATH = ROOT / "architecture" / "metadata" / "pocket-lab-architecture.json"
DOC_OUTPUT = Path("docs/generated/production/architecture")
DIAGRAM_OUTPUT = Path("docs/assets/diagrams/production")
CONTRACT_OUTPUT = Path("contracts/generated/architecture-catalog.json")
GENERATOR_SOURCES = [
    "scripts/docs/graphviz/generate_lite_architecture.py",
    "scripts/docs/graphviz/architecture_model.py",
    "scripts/docs/graphviz/architecture_pages.py",
    "scripts/docs/graphviz/architecture_source_verifier.py",
    "scripts/docs/graphviz/graphviz_renderer.py",
    "scripts/docs/graphviz/icon_registry.py",
]
FORBIDDEN_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----", re.I),
    re.compile(r"nats://[^\s/@:]+:[^\s/@]+@", re.I),
    re.compile(r"tskey-[A-Za-z0-9_-]+", re.I),
    re.compile(r"(?:/home/[^/\s]+|/mnt/[a-z]/|/tmp/|/data/data/com\.termux|[A-Za-z]:\\)", re.I),
)
EXTERNAL_ASSET_PATTERN = re.compile(
    r"(?:src|href|xlink:href)=[\"'](?:https?:)?//", re.I
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


class ArchitectureGenerationError(RuntimeError):
    """Raised when generation, validation, or drift checking fails."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generator_fingerprint() -> tuple[str, dict[str, str]]:
    values = {path: sha256_path(ROOT / path) for path in GENERATOR_SOURCES}
    digest = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest, values


def _encode(content: str | bytes) -> bytes:
    return content if isinstance(content, bytes) else content.encode("utf-8")


def _artifact_manifest(
    *, model: dict[str, Any], source_report: dict[str, Any], source_fingerprint: str,
    generator_sha: str, generator_sources: dict[str, str], outputs: dict[Path, bytes],
    diagram_count: int, mini_count: int, icon_count: int,
) -> dict[str, Any]:
    artifact_hashes = {
        path.as_posix(): sha256_bytes(payload)
        for path, payload in sorted(outputs.items(), key=lambda item: item[0].as_posix())
        if path.name != "manifest.json"
    }
    return {
        "schema_revision": 1,
        "generated": True,
        "generated_at": os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted",
        "source_commit": os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted",
        "generator": GENERATOR_SOURCES[0],
        "generator_version": GENERATOR_VERSION,
        "generator_sha256": generator_sha,
        "generator_source_fingerprints": generator_sources,
        "architecture_source": MODEL_PATH.relative_to(ROOT).as_posix(),
        "architecture_source_fingerprint": source_fingerprint,
        "repository_source_fingerprint": source_report["inventory_fingerprint"],
        "component_count": len(model["components"]),
        "connection_count": len(model["connections"]),
        "boundary_count": len(model["boundaries"]),
        "view_count": len(model["views"]),
        "domain_diagram_count": diagram_count,
        "mini_diagram_count": mini_count,
        "icon_count": icon_count,
        "validation_state": "generated",
        "generated_file_count": len(artifact_hashes),
        "generated_files": sorted(artifact_hashes),
        "sha256": artifact_hashes,
        "manifest_hash_excluded": True,
    }


def _contract_payload(
    model: dict[str, Any], source_report: dict[str, Any], source_fingerprint: str,
    generator_sha: str,
) -> dict[str, Any]:
    components = []
    for component_id, component in sorted(model["components"].items()):
        components.append({
            "id": component_id,
            "name": component["name"],
            "category": component["category"],
            "responsibility": component["responsibility"],
            "runtime_location": component["runtime_location"],
            "owner": component["owner"],
            "runtime_owner": component["runtime_owner"],
            "process_owner": component["process_owner"],
            "data_owner": component["data_owner"],
            "recovery_owner": component["recovery_owner"],
            "security_boundary": component["security_boundary"],
            "platforms": component["supported_platforms"],
            "documentation_links": component["documentation_links"],
            "protocols": component["protocols"],
            "durable_state_dependencies": component["durable_state_dependencies"],
            "evidence_produced": component["evidence_produced"],
            "health_signals": component["health_signals"],
            "verification_status": component["verification_status"],
            "generated_page": f"docs/generated/production/architecture/components/{component_id}.md",
            "mini_diagram": component["mini_diagram"],
        })
    return {
        "metadata": {
            "schema_revision": 1,
            "generated": True,
            "generated_at": os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted",
            "source_commit": os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted",
            "generator": GENERATOR_SOURCES[0],
            "generator_version": GENERATOR_VERSION,
            "generator_sha256": generator_sha,
            "architecture_source_fingerprint": source_fingerprint,
            "repository_source_fingerprint": source_report["inventory_fingerprint"],
            "validation_state": "generated",
        },
        "architecture_catalog": {
            "title": model["title"],
            "description": model["description"],
            "operational_guarantees": model["operational_guarantees"],
            "boundaries": [
                {"id": key, **value} for key, value in sorted(model["boundaries"].items())
            ],
            "components": components,
            "connections": model["connections"],
            "views": [model["views"][key] for key in sorted(model["views"])],
            "counts": {
                "components": len(model["components"]),
                "connections": len(model["connections"]),
                "boundaries": len(model["boundaries"]),
                "views": len(model["views"]),
            },
        },
    }


def build_outputs() -> tuple[dict[Path, bytes], dict[str, Any]]:
    icons = load_registry()
    for record in icons.values():
        validate_icon(record)
    model = load_model(known_icons=icons.keys())
    index = build_index(model)
    inventory = build_source_inventory(model)
    source_report = verify_sources(model, inventory)
    source_fingerprint = fingerprint(model)
    generator_sha, generator_sources = generator_fingerprint()
    outputs: dict[Path, bytes] = {}
    mini_graphs: dict[str, dict[str, Any]] = {}
    icon_fallbacks: list[str] = []
    for icon_id, record in sorted(icons.items()):
        outputs[DIAGRAM_OUTPUT / "icons" / record.path.name] = record.path.read_bytes()
    for view_id in sorted(model["views"]):
        rendered, fallback = render_view(
            model, index, icons, view_id,
            existing_outputs={
                f"{theme}.svg": ROOT / DIAGRAM_OUTPUT / "views" / f"{view_id}.{theme}.svg"
                for theme in ("light", "dark")
            },
        )
        if fallback:
            icon_fallbacks.append(f"view:{view_id}")
        for suffix, content in rendered.items():
            outputs[DIAGRAM_OUTPUT / "views" / f"{view_id}.{suffix}"] = _encode(content)
    for component_id, component in sorted(model["components"].items()):
        if not component["mini_diagram"]:
            continue
        rendered, mini, fallback = render_component(
            model, index, icons, component_id,
            existing_outputs={
                f"{theme}.svg": ROOT / DIAGRAM_OUTPUT / "components" / f"{component_id}.{theme}.svg"
                for theme in ("light", "dark")
            },
        )
        mini_graphs[component_id] = mini
        if fallback:
            icon_fallbacks.append(f"component:{component_id}")
        for suffix, content in rendered.items():
            outputs[DIAGRAM_OUTPUT / "components" / f"{component_id}.{suffix}"] = _encode(content)
    pages = build_pages(model, index, mini_graphs, source_report, source_fingerprint)
    for path, content in pages.items():
        outputs[path] = _encode(content)
    contract = _contract_payload(model, source_report, source_fingerprint, generator_sha)
    outputs[CONTRACT_OUTPUT] = _encode(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    diagram_manifest = {
        "schema_revision": 1,
        "generated": True,
        "generator": GENERATOR_SOURCES[0],
        "generator_version": GENERATOR_VERSION,
        "architecture_source_fingerprint": source_fingerprint,
        "view_count": len(model["views"]),
        "mini_diagram_count": len(mini_graphs),
        "icon_count": len(icons),
        "icon_rendering": "local SVG references injected into Graphviz SVG nodes",
        "native_graphviz_icon_fallbacks": icon_fallbacks,
        "themes": ["light", "dark"],
        "outputs": sorted(
            path.as_posix() for path in outputs
            if path.is_relative_to(DIAGRAM_OUTPUT) and path.name != "manifest.json"
        ),
    }
    outputs[DIAGRAM_OUTPUT / "manifest.json"] = _encode(
        json.dumps(diagram_manifest, indent=2, sort_keys=True) + "\n"
    )
    manifest = _artifact_manifest(
        model=model, source_report=source_report, source_fingerprint=source_fingerprint,
        generator_sha=generator_sha, generator_sources=generator_sources, outputs=outputs,
        diagram_count=len(model["views"]), mini_count=len(mini_graphs), icon_count=len(icons),
    )
    outputs[DOC_OUTPUT / "manifest.json"] = _encode(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    details = {
        "model": model,
        "source_report": source_report,
        "source_fingerprint": source_fingerprint,
        "manifest": manifest,
        "mini_graphs": mini_graphs,
    }
    validate_outputs(outputs, details)
    return outputs, details


def _strip_anchor(target: str) -> str:
    return target.split("#", 1)[0].split("?", 1)[0]


def _resolve_generated_link(source: Path, target: str, outputs: dict[Path, bytes]) -> bool:
    cleaned = _strip_anchor(target)
    if not cleaned or cleaned.startswith(("http://", "https://", "mailto:")):
        return True
    resolved = (source.parent / cleaned).as_posix()
    normalized = Path(os.path.normpath(resolved))
    if normalized in outputs or (ROOT / normalized).exists():
        return True
    if cleaned.endswith("/"):
        candidate = normalized / "index.md"
        return candidate in outputs or (ROOT / candidate).exists()
    if not Path(cleaned).suffix:
        candidate = normalized.with_suffix(".md")
        return candidate in outputs or (ROOT / candidate).exists()
    return False


def validate_outputs(outputs: dict[Path, bytes], details: dict[str, Any]) -> None:
    errors: list[str] = []
    for path, payload in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"unsafe output path {path}")
            continue
        if not payload:
            errors.append(f"empty generated file {path}")
            continue
        if path.suffix in {".md", ".json", ".dot", ".svg"}:
            text = payload.decode("utf-8", errors="strict")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    errors.append(f"forbidden secret/path pattern in {path}: {pattern.pattern}")
            if path.suffix in {".svg", ".dot", ".md"} and EXTERNAL_ASSET_PATTERN.search(text):
                errors.append(f"external asset URL in {path}")
            if path.suffix == ".svg" and "icons" not in path.parts:
                if "<title id=" not in text or "<desc id=" not in text:
                    errors.append(f"missing SVG accessibility metadata in {path}")
                if "<image href=\"../icons/" not in text:
                    errors.append(f"missing local icon reference in {path}")
            if path.suffix == ".md":
                for target in MARKDOWN_LINK_PATTERN.findall(text):
                    if not _resolve_generated_link(path, target, outputs):
                        errors.append(f"broken generated link in {path}: {target}")
    diagram_files = {path.as_posix() for path in outputs if path.suffix in {".dot", ".svg"}}
    for path in sorted(diagram_files):
        if path.endswith(".light.svg"):
            for partner in (path.replace(".light.svg", ".dark.svg"), path.replace(".light.svg", ".light.dot")):
                if partner not in diagram_files:
                    errors.append(f"missing diagram pair for {path}: {partner}")
        if path.endswith(".dark.svg"):
            partner = path.replace(".dark.svg", ".dark.dot")
            if partner not in diagram_files:
                errors.append(f"missing diagram DOT for {path}: {partner}")
    for component_id, component in details["model"]["components"].items():
        page = DOC_OUTPUT / "components" / f"{component_id}.md"
        if page not in outputs:
            errors.append(f"missing component page {page}")
        if component["mini_diagram"]:
            for theme in ("light", "dark"):
                diagram = DIAGRAM_OUTPUT / "components" / f"{component_id}.{theme}.svg"
                if diagram not in outputs:
                    errors.append(f"missing component diagram {diagram}")
    for view_id, view in details["model"]["views"].items():
        if DOC_OUTPUT / view["page"] not in outputs:
            errors.append(f"missing view page {view['page']}")
        for theme in ("light", "dark"):
            diagram = DIAGRAM_OUTPUT / "views" / f"{view_id}.{theme}.svg"
            if diagram not in outputs:
                errors.append(f"missing view diagram {diagram}")
    if errors:
        raise ArchitectureGenerationError(
            "Architecture output validation failed:\n" + "\n".join(f" - {item}" for item in errors[:80])
        )


def _stage_outputs(outputs: dict[Path, bytes]) -> Path:
    stage = Path(tempfile.mkdtemp(prefix=".pocketlab-architecture-stage-", dir=ROOT))
    for relative, payload in outputs.items():
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return stage


def _managed_existing_files() -> set[Path]:
    files: set[Path] = set()
    for directory in (ROOT / DOC_OUTPUT, ROOT / DIAGRAM_OUTPUT):
        if directory.exists():
            files.update(path.relative_to(ROOT) for path in directory.rglob("*") if path.is_file())
    if (ROOT / CONTRACT_OUTPUT).is_file():
        files.add(CONTRACT_OUTPUT)
    return files


def _diff(outputs: dict[Path, bytes]) -> tuple[list[Path], list[Path], list[Path]]:
    expected = set(outputs)
    existing = _managed_existing_files()
    added = sorted(path for path in expected if not (ROOT / path).is_file())
    removed = sorted(existing - expected)
    changed = sorted(
        path for path in expected
        if (ROOT / path).is_file() and (ROOT / path).read_bytes() != outputs[path]
    )
    return added, removed, changed


def generate(outputs: dict[Path, bytes]) -> None:
    stage = _stage_outputs(outputs)
    try:
        expected = set(outputs)
        for stale in sorted(_managed_existing_files() - expected, reverse=True):
            (ROOT / stale).unlink(missing_ok=True)
        for relative in sorted(outputs):
            source = stage / relative
            destination = ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        for directory in (ROOT / DOC_OUTPUT, ROOT / DIAGRAM_OUTPUT):
            if directory.exists():
                for child in sorted(directory.rglob("*"), reverse=True):
                    if child.is_dir():
                        try:
                            child.rmdir()
                        except OSError:
                            pass
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def check(outputs: dict[Path, bytes]) -> int:
    stage = _stage_outputs(outputs)
    try:
        added, removed, changed = _diff(outputs)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if added or removed or changed:
        print("Production architecture drift detected:")
        for label, values in (("ADDED", added), ("REMOVED", removed), ("CHANGED", changed)):
            for path in values:
                print(f" {label} {path.as_posix()}")
        return 1
    print(f"PASS {len(outputs)} Production architecture artifacts are current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check", "validate"))
    args = parser.parse_args()
    try:
        outputs, details = build_outputs()
        if args.command == "validate":
            print(
                "PASS architecture model, sources, icons, links, accessibility, and outputs validated "
                f"({len(details['model']['components'])} components, "
                f"{len(details['model']['connections'])} connections)"
            )
            return 0
        if args.command == "generate":
            generate(outputs)
            print(f"Generated {len(outputs)} Production architecture artifacts")
            return 0
        return check(outputs)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
