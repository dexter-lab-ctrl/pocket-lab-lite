#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

MODEL = ROOT / "threat-model/pocketlab-threat-model.yaml"
DOC = ROOT / "docs/security/security-architecture-threat-model.md"
GENERATED_JSON = ROOT / "docs/security/generated/threat-model/pocketlab-threat-model.json"
WORKSPACE = ROOT / "architecture/structurizr/workspace.dsl"
OPERATIONS_DIR = ROOT / "operations"

REQUIRED_VIEWS = [
    "security-review",
    "nats-command-event-boundaries",
    "audit-and-dlq-paths",
]

REQUIRED_MODEL_SECTIONS = [
    "trust_boundaries",
    "data_flows",
    "attack_surfaces",
    "operation_security",
    "threats",
    "mitigations",
    "residual_risks",
    "evidence_sources",
]

REQUIRED_OPERATION_SECURITY_FIELDS = [
    "data_classification",
    "stride",
    "trust_boundaries",
    "attack_surfaces",
    "mitigations",
    "residual_risks",
    "evidence",
]

REQUIRED_STRIDE = {
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
}

LEGACY_TOKENS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}; run task docs:threat-model")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate_operation_security() -> None:
    operation_files = sorted(OPERATIONS_DIR.glob("*.yaml"))
    if not operation_files:
        fail("operations/*.yaml files are missing")

    for path in operation_files:
        data = load_yaml(path)
        security = data.get("security") or {}
        missing = [field for field in REQUIRED_OPERATION_SECURITY_FIELDS if not security.get(field)]
        if missing:
            fail(f"{path.relative_to(ROOT)} missing security metadata fields: {', '.join(missing)}")


def validate_no_retired_terms(paths: list[Path]) -> None:
    for path in paths:
        if path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file()]
        else:
            files = [path]
        for item in files:
            text = item.read_text(encoding="utf-8", errors="ignore")
            found = [token for token in LEGACY_TOKENS if token in text]
            if found:
                fail(f"{item.relative_to(ROOT)} contains retired token(s): {', '.join(found)}")


def main() -> None:
    workspace_text = WORKSPACE.read_text(encoding="utf-8")
    missing_views = [view for view in REQUIRED_VIEWS if view not in workspace_text]
    if missing_views:
        fail("enterprise security-review Structurizr views missing: " + ", ".join(missing_views))

    validate_operation_security()

    model = load_yaml(MODEL)
    if model.get("kind") != "ThreatModel":
        fail("threat model kind must be ThreatModel")

    for section in REQUIRED_MODEL_SECTIONS:
        if not model.get(section):
            fail(f"required threat-model section is empty: {section}")

    categories = {item.get("stride") for item in model.get("threats", [])}
    missing_stride = sorted(REQUIRED_STRIDE - categories)
    if missing_stride:
        fail("missing STRIDE categories: " + ", ".join(missing_stride))

    for path in [DOC, GENERATED_JSON]:
        if not path.exists():
            fail(f"missing generated output: {path.relative_to(ROOT)}")

    json_model = json.loads(GENERATED_JSON.read_text(encoding="utf-8"))
    if json_model.get("metadata", {}).get("name") != model.get("metadata", {}).get("name"):
        fail("generated JSON does not match YAML metadata name")

    validate_no_retired_terms(
        [
            MODEL,
            DOC,
            GENERATED_JSON,
            ROOT / "docs/security/generated/threat-model",
        ]
    )

    print("Threat model check passed")
    print("Operation security metadata coverage passed")


if __name__ == "__main__":
    main()
