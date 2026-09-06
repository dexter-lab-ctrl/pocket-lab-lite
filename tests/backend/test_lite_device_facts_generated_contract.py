from __future__ import annotations

import json
from pathlib import Path

from pocket_lab_test_utils import ensure_runtime_path


CONTRACT = Path("contracts/generated/lite-device-facts.json")


def test_generated_device_facts_contract_matches_backend_owned_registries():
    ensure_runtime_path()
    import resource_telemetry
    from api_fastapi.services import lite_capability_projection

    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["contract"] == "pocket-lab-lite-device-facts"
    assert payload["resource_observation_schema_version"] == resource_telemetry.RESOURCE_OBSERVATION_SCHEMA_VERSION
    assert payload["resource_metrics"] == [provider.metric for provider in resource_telemetry.RESOURCE_PROVIDERS]
    assert payload["capability_schema_version"] == lite_capability_projection.CAPABILITY_SCHEMA_VERSION
    assert [item["id"] for item in payload["capability_registry"]] == [item["id"] for item in lite_capability_projection.CAPABILITY_REGISTRY]


def test_generated_contract_records_full_state_and_api_surface_matrix():
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert set(payload["resource_states"]) >= {
        "available", "verification_pending", "stale", "missing", "unsupported",
        "permission_denied", "unavailable", "transient_failure", "blocked", "not_applicable",
    }
    assert set(payload["capability_states"]) == {
        "not_advertised", "advertised", "verification_pending", "verified", "unavailable",
        "unsupported", "stale", "blocked", "not_applicable",
    }
    assert payload["api_surfaces"] == [
        "/api/lite/status", "/api/lite/fleet", "/api/lite/devices/{device_id}",
        "/api/lite/devices/{device_id}/health",
    ]
    assert payload["compatibility"]["legacy_telemetry_fields_retained"] is True
    assert payload["compatibility"]["read_side_effects"] is False
