#!/usr/bin/env python3
"""Adjunct runtime verifier for canonical architecture components.

The canonical architecture model remains authoritative for component existence. This
module only attaches optional promoted-runtime classifications to known component IDs.
It intentionally does not participate in live capture or delete/insert components.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime_common import BASELINE_PATH, BASELINE_SCHEMA_PATH, ROOT, validate_json

MODEL_PATH = ROOT / "architecture" / "metadata" / "pocket-lab-architecture.json"
SELECTORS = {
    "pm2": ("services", "pm2", True),
    "caddy": ("services", "caddy", True),
    "lite-api": ("services", "lite-api", True),
    "nats-jetstream": ("services", "nats", True),
    "worker": ("services", "worker", True),
    "node-agent": ("services", "node-agent", True),
    "agent-supervisor": ("services", "core-supervisor", True),
    "tailscaled": ("services", "tailscaled", False),
    "tailscale": ("routes", "remote-access", False),
    "sqlite": ("services", "sqlite", True),
    "proot-ubuntu": ("services", "proot-ubuntu", False),
    "photoprism": ("runtime_apps", "photoprism", False),
}
HEALTHY = {"online", "healthy", "ready"}


def load_model() -> dict[str, Any]:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload.get("components"), dict):
        raise ValueError("canonical architecture model components are unavailable")
    return payload


def load_baseline() -> dict[str, Any] | None:
    if not BASELINE_PATH.exists():
        return None
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    validate_json(payload, BASELINE_SCHEMA_PATH)
    return payload


def _find(baseline: dict[str, Any], collection: str, item_id: str) -> dict[str, Any] | None:
    for item in baseline.get(collection, []):
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def verify_runtime_components() -> dict[str, Any]:
    model = load_model()
    missing_model_ids = sorted(set(SELECTORS) - set(model["components"]))
    if missing_model_ids:
        raise ValueError("runtime selector references unknown canonical component(s): " + ", ".join(missing_model_ids))
    baseline = load_baseline()
    baseline_state = (
        baseline.get("verification", {}).get("runtime_verification_state")
        if baseline else "unavailable"
    )
    components: list[dict[str, Any]] = []
    for component_id in sorted(model["components"]):
        selector = SELECTORS.get(component_id)
        classification = "source-verified"
        evidence_state = "not-selected"
        selector_text = None
        if selector:
            collection, item_id, required = selector
            selector_text = f"{collection}.{item_id}"
            if not baseline or baseline_state == "unavailable":
                classification = "runtime-unavailable"
                evidence_state = "unavailable"
            else:
                item = _find(baseline, collection, item_id)
                if not item:
                    classification = "runtime-mismatch" if required else "runtime-unavailable"
                    evidence_state = "missing"
                else:
                    presence = item.get("presence")
                    status = item.get("status")
                    if collection == "runtime_apps":
                        healthy = presence == "present" and bool(item.get("pm2_owned")) and bool(item.get("route_present"))
                    elif collection == "routes":
                        healthy = presence == "present"
                    else:
                        healthy = presence == "present" and status in HEALTHY
                    if healthy:
                        classification = "source-and-runtime-verified"
                        evidence_state = "verified"
                    elif required:
                        classification = "runtime-mismatch"
                        evidence_state = "mismatch"
                    else:
                        classification = "runtime-unavailable"
                        evidence_state = "unavailable"
        components.append({
            "component_id": component_id,
            "component_name": model["components"][component_id]["name"],
            "classification": classification,
            "runtime_selector": selector_text,
            "runtime_evidence_state": evidence_state,
        })
    return {
        "baseline": BASELINE_PATH.relative_to(ROOT).as_posix(),
        "baseline_state": baseline_state or "unavailable",
        "canonical_component_count": len(model["components"]),
        "runtime_selected_component_count": len(SELECTORS),
        "components": components,
    }
