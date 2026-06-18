#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = ROOT / "operations"
OUT = ROOT / "contracts/operations/pocketlab-typed-operations.json"

REQUIRED_TOP_LEVEL = {"apiVersion", "kind", "metadata", "spec"}
REQUIRED_METADATA = {"name", "title", "description"}
REQUIRED_SPEC = {
    "professionalLabel",
    "simpleLabel",
    "uiEntrypoints",
    "apiEntrypoints",
    "natsSubject",
    "successEvents",
    "failureEvents",
    "backendOwner",
    "targetShape",
    "paramsShape",
    "safety",
    "notes",
}

FORBIDDEN_PATTERNS = [
]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a YAML mapping/object")

    return data


def validate_entity(path: Path, entity: dict[str, Any]) -> None:
    missing_top = REQUIRED_TOP_LEVEL - set(entity)
    if missing_top:
        raise SystemExit(f"{path} missing top-level keys: {sorted(missing_top)}")

    if entity.get("kind") != "TypedOperation":
        raise SystemExit(f"{path} kind must be TypedOperation")

    metadata = entity.get("metadata")
    spec = entity.get("spec")

    if not isinstance(metadata, dict):
        raise SystemExit(f"{path} metadata must be an object")

    if not isinstance(spec, dict):
        raise SystemExit(f"{path} spec must be an object")

    missing_metadata = REQUIRED_METADATA - set(metadata)
    if missing_metadata:
        raise SystemExit(f"{path} missing metadata keys: {sorted(missing_metadata)}")

    missing_spec = REQUIRED_SPEC - set(spec)
    if missing_spec:
        raise SystemExit(f"{path} missing spec keys: {sorted(missing_spec)}")

    name = metadata["name"]
    if path.stem != name:
        raise SystemExit(f"{path} filename must match metadata.name '{name}'")

    for list_key in ["uiEntrypoints", "apiEntrypoints", "successEvents", "failureEvents"]:
        if not isinstance(spec[list_key], list) or not spec[list_key]:
            raise SystemExit(f"{path} spec.{list_key} must be a non-empty list")

    if not isinstance(spec["targetShape"], dict):
        raise SystemExit(f"{path} spec.targetShape must be an object")

    if not isinstance(spec["paramsShape"], dict):
        raise SystemExit(f"{path} spec.paramsShape must be an object")

    serialized = json.dumps(entity, sort_keys=True)
    for forbidden in FORBIDDEN_PATTERNS:
        if forbidden in serialized:
            raise SystemExit(f"{path} contains forbidden retired pattern: {forbidden}")


def normalize_operation(entity: dict[str, Any]) -> dict[str, Any]:
    metadata = entity["metadata"]
    spec = entity["spec"]

    return {
        "operation": metadata["name"],
        "title": metadata["title"],
        "summary": metadata["description"],
        "tags": metadata.get("tags", []),
        "professional_label": spec["professionalLabel"],
        "simple_label": spec["simpleLabel"],
        "ui_entrypoints": spec["uiEntrypoints"],
        "api_entrypoints": spec["apiEntrypoints"],
        "nats_subject": spec["natsSubject"],
        "success_events": spec["successEvents"],
        "failure_events": spec["failureEvents"],
        "backend_owner": spec["backendOwner"],
        "target_shape": spec["targetShape"],
        "params_shape": spec["paramsShape"],
        "safety": spec["safety"],
        "notes": spec["notes"],
        "source_file": f"operations/{metadata['name']}.yaml",
    }


def load_operations() -> list[dict[str, Any]]:
    if not OPS_DIR.exists():
        raise SystemExit(
            "Missing operations directory. Run: python3 scripts/docs/seed_operations_metadata.py"
        )

    paths = sorted(OPS_DIR.glob("*.yaml"))
    if not paths:
        raise SystemExit(
            "No operation metadata files found. Run: python3 scripts/docs/seed_operations_metadata.py"
        )

    operations = []
    names = set()

    for path in paths:
        entity = load_yaml(path)
        validate_entity(path, entity)
        operation = normalize_operation(entity)

        if operation["operation"] in names:
            raise SystemExit(f"Duplicate operation name: {operation['operation']}")

        names.add(operation["operation"])
        operations.append(operation)

    return sorted(operations, key=lambda item: item["operation"])


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    operations = load_operations()

    contract = {
        "schema_version": "1.0.0",
        "app": "Pocket Lab",
        "architecture": "FastAPI + NATS / JetStream + Worker + Event-Sourced Workflow Engine",
        "source": "operations/*.yaml",
        "catalog_model": "Backstage-style per-operation metadata files",
        "operations": operations,
        "forbidden_patterns": FORBIDDEN_PATTERNS,
    }

    OUT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote operations contract: {OUT}")
    print(f"Operations documented: {len(operations)}")
    print("Source model: operations/*.yaml")


if __name__ == "__main__":
    main()
