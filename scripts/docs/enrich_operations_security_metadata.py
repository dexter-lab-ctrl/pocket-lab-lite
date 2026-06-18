#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
OPERATIONS_DIR = ROOT / "operations"

REQUIRED_SECURITY_FIELDS = [
    "data_classification",
    "stride",
    "trust_boundaries",
    "attack_surfaces",
    "mitigations",
    "residual_risks",
    "evidence",
]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )


def operation_name(data: dict[str, Any], path: Path) -> str:
    return str(data.get("metadata", {}).get("name") or path.stem)


def operation_tags(data: dict[str, Any]) -> list[str]:
    tags = data.get("metadata", {}).get("tags") or data.get("tags") or []
    return [str(tag).lower() for tag in tags]


def classify(name: str, tags: list[str]) -> str:
    joined = " ".join([name.lower(), *tags])
    if any(token in joined for token in ["secret", "vault", "rotate"]):
        return "secret"
    if any(token in joined for token in ["security", "opa", "policy"]):
        return "policy"
    if "release" in joined:
        return "release"
    if any(token in joined for token in ["backup", "restore"]):
        return "recovery"
    if "fleet" in joined:
        return "fleet"
    if "drift" in joined:
        return "configuration"
    if "health" in joined:
        return "telemetry"
    return "operational"


def default_security(name: str, tags: list[str]) -> dict[str, Any]:
    classification = classify(name, tags)

    stride = ["Tampering", "Repudiation"]
    trust_boundaries = ["browser_to_fastapi", "fastapi_to_nats", "nats_to_worker"]
    attack_surfaces = ["api_endpoint", "nats_subject", "worker_handler"]
    mitigations = [
        "typed_operation_schema",
        "openapi_validation",
        "asyncapi_subject_governance",
        "operation_audit_events",
    ]
    residual_risks = [
        "Authorized operators can still trigger high-impact changes if policy or approval controls are incomplete."
    ]

    if classification in {"secret", "policy"}:
        stride.extend(["Information Disclosure", "Elevation of Privilege"])
        trust_boundaries.append("worker_to_secrets_policy")
        attack_surfaces.extend(["vault_or_policy_adapter", "audit_event_payload"])
        mitigations.extend(["opa_policy_decision", "secret_redaction", "vault_or_openbao_leases"])
        residual_risks.append("New secret or policy fields may require manual redaction review.")

    if classification in {"release", "recovery", "fleet", "configuration"}:
        stride.extend(["Denial of Service", "Elevation of Privilege"])
        trust_boundaries.append("worker_to_state_audit")
        attack_surfaces.extend(["state_store", "event_journal", "dlq_subject"])
        mitigations.extend(["event_sourced_workflow_journal", "dlq_review_path", "correlation_ids"])
        residual_risks.append("Edge-first deployments remain sensitive to host, storage, and network availability.")

    if classification == "telemetry":
        stride.extend(["Information Disclosure", "Denial of Service"])
        attack_surfaces.extend(["telemetry_payload", "status_stream"])
        mitigations.extend(["payload_minimization", "event_redaction"])
        residual_risks.append("Telemetry schemas can drift if new fields are added without privacy review.")

    stride = list(dict.fromkeys(stride))
    trust_boundaries = list(dict.fromkeys(trust_boundaries))
    attack_surfaces = list(dict.fromkeys(attack_surfaces))
    mitigations = list(dict.fromkeys(mitigations))
    residual_risks = list(dict.fromkeys(residual_risks))

    return {
        "data_classification": classification,
        "stride": stride,
        "trust_boundaries": trust_boundaries,
        "attack_surfaces": attack_surfaces,
        "mitigations": mitigations,
        "residual_risks": residual_risks,
        "evidence": [
            "architecture/structurizr/workspace.dsl",
            "contracts/generated/openapi.json",
            "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
            "contracts/operations/pocketlab-typed-operations.json",
            f"operations/{name}.yaml",
        ],
    }


def merge_missing_security(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    security = dict(existing or {})
    for key, value in generated.items():
        if key not in security or security[key] in (None, "", []):
            security[key] = value
    return security


def main() -> None:
    if not OPERATIONS_DIR.exists():
        raise SystemExit("operations/ directory is missing")

    changed = []
    for path in sorted(OPERATIONS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        name = operation_name(data, path)
        tags = operation_tags(data)
        generated = default_security(name, tags)
        data["security"] = merge_missing_security(data.get("security") or {}, generated)

        missing = [field for field in REQUIRED_SECURITY_FIELDS if not data["security"].get(field)]
        if missing:
            raise SystemExit(f"{path}: missing security fields after enrichment: {', '.join(missing)}")

        before = path.read_text(encoding="utf-8")
        rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)
        if rendered != before:
            path.write_text(rendered, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))

    print(f"Security metadata checked for {len(list(OPERATIONS_DIR.glob('*.yaml')))} operation files.")
    if changed:
        print("Updated operation security metadata:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("No operation metadata changes needed.")


if __name__ == "__main__":
    main()
