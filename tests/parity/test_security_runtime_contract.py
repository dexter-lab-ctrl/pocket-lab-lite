from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "contracts" / "parity" / "parity-model.json"


def _security_domain() -> dict[str, Any]:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def walk(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            if (
                value.get("id") == "security"
                and "live_observation_contract" in value
            ):
                return value

            for child in value.values():
                found = walk(child)
                if found is not None:
                    return found

        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found is not None:
                    return found

        return None

    security = walk(model)
    assert security is not None
    return security


def _resolve_path(payload: Any, path: str) -> tuple[bool, Any]:
    current = payload

    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]

    return True, current


def test_security_live_contract_uses_current_summary_schema() -> None:
    security = _security_domain()
    fields = security["live_observation_contract"]["backend"]["fields"]
    field_paths = {field["id"]: field["path"] for field in fields}

    assert field_paths == {
        "status": "status",
        "summary": "summary",
        "score": "score",
        "active_scan": "scan_progress.active_scan",
        "profile": "last_run.scan_profile",
        "finding_count": "findings_count",
    }

    assert "read_degraded" not in field_paths


def test_security_live_contract_observes_false_and_zero_values() -> None:
    security = _security_domain()
    fields = security["live_observation_contract"]["backend"]["fields"]

    payload = {
        "status": "healthy",
        "summary": "App Check completed.",
        "score": 100,
        "findings_count": 0,
        "last_run": {"scan_profile": "app"},
        "scan_progress": {"active_scan": False},
    }

    observed = {}

    for field in fields:
        found, value = _resolve_path(payload, field["path"])
        assert found, field
        observed[field["id"]] = value

    assert observed == {
        "status": "healthy",
        "summary": "App Check completed.",
        "score": 100,
        "active_scan": False,
        "profile": "app",
        "finding_count": 0,
    }


def test_security_live_contract_does_not_restore_legacy_paths() -> None:
    security = _security_domain()
    fields = security["live_observation_contract"]["backend"]["fields"]
    paths = {field["path"] for field in fields}

    assert "active_scan" not in paths
    assert "last_run.profile" not in paths
    assert "finding_count" not in paths
    assert "read_degraded" not in paths
