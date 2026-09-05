#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
CORE = RUNTIME / "core"
CONTRACT_OUT = ROOT / "contracts" / "generated" / "lite-device-facts.json"
DOC_OUT = ROOT / "docs" / "generated" / "development" / "device-facts-contract.md"
SCENARIO_OUT = ROOT / "src" / "test" / "fixtures" / "generated" / "device-facts" / "manifest.json"

SCENARIOS = (
    "devices-resource-complete", "devices-resource-partial", "devices-resource-stale",
    "devices-resource-unsupported", "devices-resource-permission-denied", "devices-resource-missing",
    "devices-capability-verified", "devices-capability-pending", "devices-capability-stale",
    "devices-capability-unsupported", "devices-capability-blocked", "devices-capability-not-applicable",
    "devices-capability-missing", "devices-capability-mixed", "devices-capability-unknown",
    "devices-services-mixed", "devices-services-stale", "devices-services-unknown", "devices-services-disappeared",
    "devices-software-current", "devices-software-outdated", "devices-software-incompatible", "devices-software-stale",
    "devices-secondary-complete", "devices-secondary-offline-saved", "devices-long-name",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def contract() -> dict[str, Any]:
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(0, str(CORE))
    import resource_telemetry  # type: ignore
    from api_fastapi.services import lite_capability_projection  # type: ignore

    return {
        "contract": "pocket-lab-lite-device-facts",
        "schema_version": 1,
        "resource_observation_schema_version": int(resource_telemetry.RESOURCE_OBSERVATION_SCHEMA_VERSION),
        "resource_metrics": [provider.metric for provider in resource_telemetry.RESOURCE_PROVIDERS],
        "resource_states": [
            "available", "verification_pending", "stale", "missing", "unsupported",
            "permission_denied", "unavailable", "transient_failure", "blocked", "not_applicable",
        ],
        "capability_schema_version": int(lite_capability_projection.CAPABILITY_SCHEMA_VERSION),
        "capability_states": [
            "not_advertised", "advertised", "verification_pending", "verified", "unavailable",
            "unsupported", "stale", "blocked", "not_applicable",
        ],
        "capability_registry": [
            {
                "id": item["id"], "label": item["label"], "category": item["category"],
                "verification_strategy": item["verification_strategy"],
                "schema_version": int(item.get("schema_version") or 1),
            }
            for item in lite_capability_projection.CAPABILITY_REGISTRY
        ],
        "runtime_service_fields": [
            "service_id", "label", "category", "manager", "state", "reported_at", "freshness",
            "restart_supported", "restart_reason", "source", "schema_version", "sanitized",
        ],
        "software_components": ["node_agent", "supervisor"],
        "software_states": ["current", "outdated", "incompatible", "unknown", "stale", "verification_pending"],
        "api_surfaces": [
            "/api/lite/status", "/api/lite/fleet", "/api/lite/devices/{device_id}",
            "/api/lite/devices/{device_id}/health",
        ],
        "regression_scenarios": list(SCENARIOS),
        "compatibility": {
            "legacy_telemetry_fields_retained": True,
            "old_agent_missing_metrics": "unsupported_or_not_reported",
            "read_side_effects": False,
        },
        "security": {
            "sanitized": True,
            "forbidden_metadata": [
                "environment", "command_args", "password", "token", "api_key", "nats_credentials", "private_paths",
            ],
        },
    }


def document(payload: dict[str, Any]) -> str:
    capabilities = "\n".join(
        f"- `{item['id']}` — {item['label']} (`{item['verification_strategy']}`)"
        for item in payload["capability_registry"]
    )
    surfaces = "\n".join(f"- `{item}`" for item in payload["api_surfaces"])
    return f"""---
title: Device Facts contract
description: Generated resource, capability, runtime-service, software, and API projection contract for Pocket Lab Lite.
status: verified
generated: true
audience: development
generator: scripts/docs/lite/generate_device_facts_contract.py
schema_revision: 1
validation_status: generated
---

# Device Facts contract

This page is generated from backend-owned resource-provider and capability registries.

## Resource observations

States: {', '.join(f'`{item}`' for item in payload['resource_states'])}.

Metrics: {', '.join(f'`{item}`' for item in payload['resource_metrics'])}.

Every observation is sanitized and carries source, observed time, freshness, reason, support state, schema version, revision, and a bounded value when available. Unsupported or failed collection never becomes a fabricated numeric zero.

## Capability lifecycle

States: {', '.join(f'`{item}`' for item in payload['capability_states'])}.

{capabilities}

Advertisement alone does not verify a capability. `verified_at` is present only when authoritative runtime evidence verifies the capability.

## Runtime services

Runtime services are backend-owned, dynamic, device-specific, and sanitized. Process environment values, command arguments, credentials, and private paths are excluded. Secondary devices show only services they actually report.

## API parity

The same canonical facts are projected through:

{surfaces}

Legacy telemetry fields remain compatibility aliases during migration; canonical `device_facts` is authoritative.

## Regression scenarios

The generated scenario manifest is `src/test/fixtures/generated/device-facts/manifest.json`. Runtime fixture payloads are owned by `src/mocks/deviceFactsScenarios.js` so Storybook and Playwright use the same deterministic states.
"""


def outputs() -> dict[Path, str]:
    payload = contract()
    scenario_manifest = {
        "contract": "pocket-lab-lite-device-facts-scenarios",
        "schema_version": 1,
        "scenario_owner": "src/mocks/deviceFactsScenarios.js",
        "scenarios": list(SCENARIOS),
        "sanitized": True,
    }
    return {CONTRACT_OUT: stable_json(payload), DOC_OUT: document(payload), SCENARIO_OUT: stable_json(scenario_manifest)}


def write_outputs(values: dict[Path, str]) -> None:
    for path, content in values.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(values: dict[Path, str]) -> int:
    stale = [path for path, content in values.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if stale:
        for path in stale:
            print(f"STALE {path.relative_to(ROOT)}")
        return 1
    print(f"PASS Device Facts generated artifacts ({len(values)})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("generate", "check"), default="generate")
    args = parser.parse_args()
    values = outputs()
    if args.mode == "check":
        return check_outputs(values)
    write_outputs(values)
    print(f"Generated {len(values)} Device Facts artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
