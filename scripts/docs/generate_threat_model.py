#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

WORKSPACE = ROOT / "architecture/structurizr/workspace.dsl"
OPENAPI = ROOT / "contracts/generated/openapi.json"
ASYNCAPI = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"
OPERATIONS_CONTRACT = ROOT / "contracts/operations/pocketlab-typed-operations.json"
OPERATIONS_DIR = ROOT / "operations"

OUT_YAML = ROOT / "threat-model/pocketlab-threat-model.yaml"
OUT_JSON = ROOT / "docs/security/generated/threat-model/pocketlab-threat-model.json"
OUT_INDEX = ROOT / "docs/security/generated/threat-model/index.md"

TIER5B_VIEWS = [
    "security-review",
    "nats-command-event-boundaries",
    "audit-and-dlq-paths",
]

STRIDE_ORDER = [
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
]

LEGACY_TOKENS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Required input missing: {path.relative_to(ROOT)}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def operation_records_from_contract(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in data.get("operations", []):
        name = item.get("operation") or item.get("name") or item.get("metadata", {}).get("name")
        if not name:
            continue
        records[str(name)] = {
            "name": str(name),
            "tags": item.get("tags") or item.get("metadata", {}).get("tags") or [],
            "nats_subject": item.get("nats_subject") or item.get("natsSubject") or item.get("spec", {}).get("natsSubject"),
            "api_entrypoints": item.get("api_entrypoints") or item.get("apiEntrypoints") or item.get("spec", {}).get("apiEntrypoints") or [],
        }
    return records


def load_operation_metadata() -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for path in sorted(OPERATIONS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        name = data.get("metadata", {}).get("name") or path.stem
        security = data.get("security") or {}
        spec = data.get("spec") or {}
        operations.append(
            {
                "name": str(name),
                "title": data.get("metadata", {}).get("title", str(name)),
                "description": data.get("metadata", {}).get("description", ""),
                "tags": data.get("metadata", {}).get("tags", []),
                "source_file": str(path.relative_to(ROOT)),
                "nats_subject": spec.get("natsSubject"),
                "api_entrypoints": spec.get("apiEntrypoints", []),
                "security": security,
            }
        )
    return operations


def run_enrichment() -> None:
    subprocess.run(["python3", "scripts/docs/enrich_operations_security_metadata.py"], cwd=ROOT, check=True)


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def build_operation_threats(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    threats: list[dict[str, Any]] = []
    for op in operations:
        security = op.get("security") or {}
        for stride in security.get("stride", []):
            threat_id = f"OP-{op['name'].upper().replace('-', '_')}-{stride.split()[0].upper()}"
            threats.append(
                {
                    "id": threat_id,
                    "source": "operation_metadata",
                    "operation": op["name"],
                    "stride": stride,
                    "scenario": f"{op['name']} may be abused or fail across {', '.join(security.get('trust_boundaries', []))}.",
                    "affected": security.get("attack_surfaces", []),
                    "mitigations": security.get("mitigations", []),
                    "residualRisk": " ".join(security.get("residual_risks", [])),
                    "evidence": security.get("evidence", []),
                }
            )
    return threats


def baseline_threats() -> list[dict[str, Any]]:
    return [
        {
            "id": "TM-S-001",
            "source": "baseline",
            "stride": "Spoofing",
            "scenario": "An untrusted client attempts to impersonate the UI, worker, or fleet agent.",
            "affected": ["FastAPI Control API", "NATS / JetStream", "Fleet Agent Control"],
            "mitigations": ["API auth/write gates", "NATS subject role separation", "fleet join validation"],
            "residualRisk": "Misconfigured local development credentials can weaken role boundaries.",
            "evidence": ["architecture/structurizr/workspace.dsl"],
        },
        {
            "id": "TM-T-001",
            "source": "baseline",
            "stride": "Tampering",
            "scenario": "A caller modifies operation payloads, catalog data, or NATS command bodies.",
            "affected": ["Typed Operations Catalog", "NATS / JetStream", "Worker"],
            "mitigations": ["typed operation schema validation", "AsyncAPI subject governance", "operation metadata checks"],
            "residualRisk": "A compromised operator account can still submit authorized destructive changes.",
            "evidence": ["contracts/operations/pocketlab-typed-operations.json"],
        },
        {
            "id": "TM-R-001",
            "source": "baseline",
            "stride": "Repudiation",
            "scenario": "A sensitive release, vault, drift, or restore action cannot be traced after execution.",
            "affected": ["Audit Trail / Evidence Store", "Event Journal / Workflow Store"],
            "mitigations": ["correlation IDs", "audit events", "event-sourced workflow journal"],
            "residualRisk": "Local storage loss can remove evidence unless backed up.",
            "evidence": ["architecture/structurizr/workspace.dsl"],
        },
        {
            "id": "TM-I-001",
            "source": "baseline",
            "stride": "Information Disclosure",
            "scenario": "Secrets leak through logs, events, audit payloads, UI streams, or DLQ records.",
            "affected": ["Vault / OpenBao Runtime", "Event Journal", "DLQ / Retry Subjects"],
            "mitigations": ["redaction rules", "journal redaction tests", "DLQ payload review"],
            "residualRisk": "New secret field names need continuous review.",
            "evidence": ["tests/backend/test_journal_redaction.py"],
        },
        {
            "id": "TM-D-001",
            "source": "baseline",
            "stride": "Denial of Service",
            "scenario": "NATS, worker, OPA, Vault, or the API becomes unavailable during an operation.",
            "affected": ["FastAPI", "NATS / JetStream", "Worker", "OPA", "Vault"],
            "mitigations": ["readiness gates", "JetStream retry/DLQ", "degraded-mode tests"],
            "residualRisk": "Single-device edge deployments remain capacity constrained.",
            "evidence": ["contracts/asyncapi/pocketlab-nats-jetstream.yaml"],
        },
        {
            "id": "TM-E-001",
            "source": "baseline",
            "stride": "Elevation of Privilege",
            "scenario": "A lower-privileged path triggers privileged operations such as release apply, restore, or secret rotation.",
            "affected": ["FastAPI Control API", "Policy Guardrails", "Typed Operations Catalog"],
            "mitigations": ["write authorization", "OPA policy decisions", "operation safety metadata"],
            "residualRisk": "Policy gaps can appear when new operations are added without matching guardrails.",
            "evidence": ["operations/*.yaml"],
        },
    ]


def validate_no_retired_terms(model: dict[str, Any]) -> None:
    rendered = json.dumps(model, sort_keys=True)
    found = [token for token in LEGACY_TOKENS if token in rendered]
    if found:
        raise SystemExit("Generated threat model contains retired tokens: " + ", ".join(found))


def build_model() -> dict[str, Any]:
    run_enrichment()

    for path in [WORKSPACE, OPENAPI, ASYNCAPI, OPERATIONS_CONTRACT]:
        require(path)

    workspace_text = WORKSPACE.read_text(encoding="utf-8")
    missing_views = [view for view in TIER5B_VIEWS if view not in workspace_text]
    if missing_views:
        raise SystemExit("enterprise security-review views missing from Structurizr workspace: " + ", ".join(missing_views))

    openapi = load_json(OPENAPI)
    asyncapi = load_yaml(ASYNCAPI)
    operations_contract = load_json(OPERATIONS_CONTRACT)

    contract_ops = operation_records_from_contract(operations_contract)
    metadata_ops = load_operation_metadata()

    for op in metadata_ops:
        contract = contract_ops.get(op["name"], {})
        op["nats_subject"] = op.get("nats_subject") or contract.get("nats_subject")
        op["api_entrypoints"] = op.get("api_entrypoints") or contract.get("api_entrypoints", [])

    api_paths = sorted(openapi.get("paths", {}).keys())
    channels = sorted(asyncapi.get("channels", {}).keys())

    operation_security = [
        {
            "name": op["name"],
            "title": op["title"],
            "source_file": op["source_file"],
            "nats_subject": op.get("nats_subject"),
            "api_entrypoints": op.get("api_entrypoints", []),
            "security": op.get("security", {}),
        }
        for op in metadata_ops
    ]

    trust_boundaries = {
        boundary
        for op in metadata_ops
        for boundary in (op.get("security", {}).get("trust_boundaries") or [])
    }

    attack_surfaces = {
        surface
        for op in metadata_ops
        for surface in (op.get("security", {}).get("attack_surfaces") or [])
    }

    mitigations = {
        mitigation
        for op in metadata_ops
        for mitigation in (op.get("security", {}).get("mitigations") or [])
    }

    residual_risks = [
        {
            "operation": op["name"],
            "risk": risk,
            "owner": "feature_owner",
            "treatment": "Review during operation metadata and Threat Dragon review.",
        }
        for op in metadata_ops
        for risk in (op.get("security", {}).get("residual_risks") or [])
    ]

    threats = baseline_threats() + build_operation_threats(metadata_ops)

    model: dict[str, Any] = {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "ThreatModel",
        "metadata": {
            "name": "pocketlab-threat-model",
            "title": "Pocket Lab Security Architecture & Threat Model",
            "tier": "6.5",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceOfTruth": "Repository-generated metadata. Operation-level security blocks in operations/*.yaml are required for new features.",
        },
        "evidence_sources": [
            {
                "type": "structurizr",
                "path": str(WORKSPACE.relative_to(ROOT)),
                "notes": "C4 architecture model and enterprise security-review views.",
            },
            {
                "type": "openapi",
                "path": str(OPENAPI.relative_to(ROOT)),
                "api_path_count": len(api_paths),
            },
            {
                "type": "asyncapi",
                "path": str(ASYNCAPI.relative_to(ROOT)),
                "channel_count": len(channels),
            },
            {
                "type": "typed_operations",
                "path": str(OPERATIONS_CONTRACT.relative_to(ROOT)),
                "operation_count": len(metadata_ops),
            },
            {
                "type": "operation_security_metadata",
                "paths": [op["source_file"] for op in metadata_ops],
            },
        ],
        "tier5b_views": TIER5B_VIEWS,
        "assets": [
            {"name": "FastAPI Control API", "classification": "control-plane API", "evidence": "OpenAPI paths"},
            {"name": "NATS / JetStream", "classification": "command and event backbone", "evidence": "AsyncAPI channels"},
            {"name": "Pocket Lab Worker", "classification": "typed operation executor", "evidence": "Structurizr worker container"},
            {"name": "Typed Operations Catalog", "classification": "execution contract", "evidence": "operations/*.yaml"},
            {"name": "Event Journal / Workflow Store", "classification": "workflow recovery evidence", "evidence": "enterprise security-review audit view"},
            {"name": "Audit Trail / Evidence Store", "classification": "audit evidence", "evidence": "enterprise security-review audit view"},
            {"name": "Vault / OpenBao Runtime", "classification": "secret backend", "evidence": "enterprise security-review view"},
            {"name": "OPA Runtime", "classification": "policy decision point", "evidence": "enterprise security-review view"},
        ],
        "trust_boundaries": [
            {
                "name": boundary,
                "description": f"Operation metadata declares crossing of {boundary}.",
                "controls": sorted(mitigations),
            }
            for boundary in sorted(trust_boundaries)
        ],
        "data_flows": [
            {
                "name": f"{op['name']} operation flow",
                "source": "React / Vite PWA",
                "destination": "FastAPI → NATS / JetStream → Worker",
                "data": "typed operation target, params, correlation ID, lifecycle events",
                "trustBoundary": ", ".join(op.get("security", {}).get("trust_boundaries", [])),
                "stride": op.get("security", {}).get("stride", []),
                "evidence": op.get("security", {}).get("evidence", []),
            }
            for op in metadata_ops
        ],
        "attack_surfaces": [
            {
                "name": surface,
                "evidence_count": sum(
                    1 for op in metadata_ops if surface in (op.get("security", {}).get("attack_surfaces") or [])
                ),
                "examples": [
                    op["name"]
                    for op in metadata_ops
                    if surface in (op.get("security", {}).get("attack_surfaces") or [])
                ][:12],
            }
            for surface in sorted(attack_surfaces)
        ],
        "operation_security": operation_security,
        "threats": threats,
        "mitigations": [
            {
                "name": mitigation,
                "covers": unique(
                    [
                        stride
                        for op in metadata_ops
                        if mitigation in (op.get("security", {}).get("mitigations") or [])
                        for stride in (op.get("security", {}).get("stride") or [])
                    ]
                ),
                "evidence": "operations/*.yaml",
            }
            for mitigation in sorted(mitigations)
        ],
        "residual_risks": residual_risks,
    }

    validate_no_retired_terms(model)
    return model


def main() -> None:
    model = build_model()

    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    OUT_YAML.write_text(yaml.safe_dump(model, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(model, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    OUT_INDEX.write_text(
        "# Generated Threat Model Artifacts\n\n"
        "This directory contains generated Pocket Lab threat-model metadata.\n\n"
        "- `pocketlab-threat-model.json` mirrors `threat-model/pocketlab-threat-model.yaml`.\n"
        "- `operations/*.yaml` security blocks are the feature-level source of truth.\n"
        "- OWASP Threat Dragon is used as a local review/editing tool.\n",
        encoding="utf-8",
    )

    print(f"Wrote {OUT_YAML.relative_to(ROOT)}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
