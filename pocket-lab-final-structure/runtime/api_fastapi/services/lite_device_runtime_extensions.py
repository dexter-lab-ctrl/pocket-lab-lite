from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from . import lite_device_facts, lite_runtime_services
from .lite_device_runtime_projection import enrich_device

_HEALTH_EXTENSION_MARKER = "_pocketlab_device_facts_health_extension_v2"
_RUNTIME_EXTENSION_MARKER = "_pocketlab_device_facts_runtime_extensions_v2"

def _overlay_resource_metadata(resources: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "storage": "storage",
        "memory": "memory",
        "load": "cpu_usage",
        "temperature": "temperature",
    }
    result = dict(resources) if isinstance(resources, dict) else {}
    for resource_name, observation_name in mapping.items():
        resource = result.get(resource_name) if isinstance(result.get(resource_name), dict) else {}
        observation = observations.get(observation_name) if isinstance(observations.get(observation_name), dict) else None
        if not observation:
            continue
        result[resource_name] = {
            **resource,
            "observation_status": observation.get("collection_status") or observation.get("status"),
            "observed_at": observation.get("observed_at"),
            "freshness": observation.get("freshness"),
            "reason_code": observation.get("reason_code"),
            "support_state": observation.get("support_state"),
            "source": observation.get("source"),
            "revision": observation.get("revision"),
        }
    return result


def install_health_projection_extension() -> None:
    try:
        from . import lite_device_health as health_module
    except Exception:
        return
    if getattr(health_module, _HEALTH_EXTENSION_MARKER, False):
        return
    original = health_module.evaluate_device_health

    def evaluate_device_health(device, *, signals=None, previous=None, now_epoch=None):
        signals = signals if isinstance(signals, dict) else {}
        previous = previous if isinstance(previous, dict) else {}
        effective = enrich_device(device if isinstance(device, dict) else {})
        facts = effective.get("device_facts") if isinstance(effective.get("device_facts"), dict) else {}
        observations = facts.get("resources") if isinstance(facts.get("resources"), dict) else {}
        canonical_signals = dict(signals)
        if observations:
            existing_telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
            sampled_at = max(
                (
                    str(item.get("observed_at"))
                    for item in observations.values()
                    if isinstance(item, dict) and item.get("observed_at")
                ),
                default=existing_telemetry.get("sampled_at") or existing_telemetry.get("timestamp"),
            )
            canonical_signals["telemetry"] = {
                **existing_telemetry,
                **lite_device_facts.health_signal_telemetry(observations, sampled_at=sampled_at),
            }
            canonical_signals["resource_observations"] = observations
        result = original(
            effective, signals=canonical_signals, previous=previous, now_epoch=now_epoch
        )

        now_value = time.time() if now_epoch is None else float(now_epoch)
        current_resources = result.get("resources") if isinstance(result.get("resources"), dict) else {}
        try:
            previous_resources = previous.get("resources") if isinstance(previous.get("resources"), dict) else {}
            policy = health_module._policy()
            current_resources = health_module._resource_assessment(
                canonical_signals,
                previous_resources,
                policy,
                health_module._now_iso(now_value),
                now_value,
            )
        except Exception:
            pass
        current_resources = _overlay_resource_metadata(current_resources, observations)

        versions = dict(result.get("versions") or {}) if isinstance(result.get("versions"), dict) else {}
        software = facts.get("software") if isinstance(facts.get("software"), dict) else {}
        for component in ("node_agent", "supervisor"):
            part = versions.get(component) if isinstance(versions.get(component), dict) else {}
            fact = software.get(component) if isinstance(software.get(component), dict) else {}
            if fact:
                versions[component] = {
                    **part,
                    "version": fact.get("version") or part.get("version"),
                    "source": fact.get("source"),
                    "freshness": fact.get("freshness"),
                    "observed_at": fact.get("observed_at"),
                    "reason_code": fact.get("reason_code"),
                }
        version_status = str(versions.get("status") or "unknown")
        software_freshness = {
            str((software.get(component) or {}).get("freshness") or "missing")
            for component in ("node_agent", "supervisor")
            if isinstance(software.get(component), dict)
        }
        if version_status == "behind":
            software_status = "outdated"
        elif version_status == "incompatible":
            software_status = "incompatible"
        elif version_status == "current" and software_freshness and software_freshness <= {"stale", "missing"}:
            software_status = "stale"
        elif version_status == "current":
            software_status = "current"
        elif any((software.get(component) or {}).get("version") for component in ("node_agent", "supervisor")):
            software_status = "unknown"
        else:
            software_status = "verification_pending"
        software_posture = dict(result.get("software_posture") or {})
        software_posture.update({
            "status": software_status,
            "verification_pending": software_status == "verification_pending",
            "parts": {key: value for key, value in versions.items() if isinstance(value, dict)},
            "summary": (
                "Device software is current." if software_status == "current"
                else "Agent software update is recommended." if software_status == "outdated"
                else "Device software is incompatible." if software_status == "incompatible"
                else "Software evidence is stale." if software_status == "stale"
                else "Software version evidence is available but compatibility is unknown." if software_status == "unknown"
                else "Software verification is pending."
            ),
        })
        return {
            **result,
            "resources": current_resources,
            "resource_observations": observations,
            "versions": versions,
            "software_posture": software_posture,
            "device_facts": facts,
        }

    health_module.evaluate_device_health = evaluate_device_health
    setattr(health_module, _HEALTH_EXTENSION_MARKER, True)


def _canonical_resource_revision_material(telemetry: Any, source: str) -> dict[str, Any]:
    observations = lite_device_facts.normalize_resource_observations(
        telemetry if isinstance(telemetry, dict) else {}, source=source
    )
    return {
        metric: {
            "value": item.get("value"),
            "status": item.get("status"),
            "collection_status": item.get("collection_status"),
            "freshness": item.get("freshness"),
            "reason_code": item.get("reason_code"),
            "revision": item.get("revision"),
        }
        for metric, item in sorted(observations.items())
        if isinstance(item, dict)
    }


def _semantic_revision(namespace: str, material: Any) -> int:
    encoded = json.dumps(
        {"namespace": namespace, "material": material},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )
    return max(
        1,
        int.from_bytes(hashlib.sha256(encoded.encode("utf-8")).digest()[:8], "big")
        & ((1 << 63) - 1),
    )


def install_status_projection_extension() -> None:
    """Make canonical Server Host Device Facts part of the prepared `/status` contract."""
    try:
        from . import lite_status
    except Exception:
        return
    marker = "_pocketlab_device_facts_status_extension_v1"
    if getattr(lite_status, marker, False):
        return

    original_build = lite_status._build_lite_status_from_inputs
    original_default = lite_status.default_lite_status_state

    def lite_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}

        def first(*keys: str) -> Any:
            for key in keys:
                if key in payload and payload.get(key) is not None:
                    return payload.get(key)
            return None

        result = {
            "status": lite_status._status(payload.get("status", "unknown")),
            "cpu_temp_c": first("cpu_temp_c", "cpuTemp"),
            "free_space_mb": first("free_space_mb", "freeSpaceMB"),
            "total_space_mb": first("total_space_mb", "totalSpaceMB"),
            "cpu_usage_percent": first("cpu_usage_percent"),
            "memory_usage_mb": first("memory_usage_mb"),
            "memory_total_mb": first("memory_total_mb", "memoryTotalMB"),
            "memory_free_mb": first("memory_free_mb", "memoryFreeMB"),
            "sampled_at": first("sampled_at", "timestamp", "time", "updated_at"),
            "schema_version": payload.get("schema_version"),
            "resource_observations": payload.get("resource_observations")
            if isinstance(payload.get("resource_observations"), dict)
            else {},
        }
        if isinstance(payload.get("devices"), list) or isinstance(payload.get("counts"), dict):
            result.update({
                "summary": str(payload.get("summary") or "Telemetry is not available.")[:192],
                "counts": payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
                "device_count": len(payload.get("devices") or []),
                "semantic": True,
            })
        return result

    def build_from_inputs(*, checked_at, engine, bus, live, remote_access, telemetry, fleet, fleet_nodes, current_state):
        payload = original_build(
            checked_at=checked_at,
            engine=engine,
            bus=bus,
            live=live,
            remote_access=remote_access,
            telemetry=telemetry,
            fleet=fleet,
            fleet_nodes=fleet_nodes,
            current_state=current_state,
        )
        server_id = lite_status.normalize_node_id(
            os.environ.get("POCKETLAB_SERVER_NODE_ID")
            or os.environ.get("POCKETLAB_NODE_ID")
            or "pocket-lab-lite-server"
        )
        device = dict(payload.get("device") or {})
        device.update({
            "id": server_id,
            "role": "server_host",
            "is_current": True,
            "protected_server_host": True,
        })
        facts = lite_device_facts.build_device_facts(
            device,
            telemetry=telemetry if isinstance(telemetry, dict) else {},
            telemetry_source="server_central_telemetry",
        )
        device["device_facts"] = facts
        payload["device"] = device
        payload["device_facts"] = facts
        payload["resource_observations"] = facts.get("resources") or {}
        payload["telemetry"] = lite_telemetry(telemetry if isinstance(telemetry, dict) else {})
        payload["sanitized"] = True
        return payload

    def default_state():
        payload = original_default()
        server_id = lite_status.normalize_node_id(
            os.environ.get("POCKETLAB_SERVER_NODE_ID")
            or os.environ.get("POCKETLAB_NODE_ID")
            or "pocket-lab-lite-server"
        )
        facts = lite_device_facts.build_device_facts(
            {"id": server_id, "role": "server_host", "is_current": True},
            telemetry={}, telemetry_source="server_central_telemetry",
        )
        device = dict(payload.get("device") or {})
        device.update({
            "id": server_id, "role": "server_host", "is_current": True,
            "protected_server_host": True, "device_facts": facts,
        })
        payload.update({
            "device": device,
            "device_facts": facts,
            "resource_observations": {},
            "sanitized": True,
        })
        return payload

    lite_status._lite_telemetry = lite_telemetry
    lite_status._build_lite_status_from_inputs = build_from_inputs
    lite_status.default_lite_status_state = default_state
    setattr(lite_status, marker, True)


def install_source_revision_extensions() -> None:
    """Refresh prepared facts on observation changes without creating health transitions."""
    try:
        from . import fleet_registry, lite_phase3b_projections as phase3b
        from .live_status import LIVE_STATUS
    except Exception:
        return
    marker = "_pocketlab_device_facts_source_revision_v1"
    if getattr(phase3b, marker, False):
        return

    original_status_revision = phase3b.status_source_revision
    original_fleet_revision = fleet_registry.fleet_source_revision

    def status_source_revision() -> int:
        try:
            resources = _canonical_resource_revision_material(
                LIVE_STATUS.last_telemetry_snapshot(), "server_central_telemetry"
            )
        except Exception:
            resources = {}
        return _semantic_revision(
            "system.status.device_facts",
            {"base_revision": int(original_status_revision()), "resources": resources},
        )

    def fleet_source_revision() -> int:
        agents: list[dict[str, Any]] = []
        try:
            for raw in fleet_registry.list_agents(include_stale=True)[:512]:
                if not isinstance(raw, dict):
                    continue
                telemetry = raw.get("telemetry") if isinstance(raw.get("telemetry"), dict) else {}
                agents.append({
                    "id": str(raw.get("node_id") or raw.get("id") or "")[:120],
                    "resources": _canonical_resource_revision_material(telemetry, "agent_telemetry"),
                    "agent_version": str(raw.get("agent_version") or "")[:80],
                    "supervisor_version": str(raw.get("supervisor_version") or "")[:80],
                })
        except Exception:
            agents = []
        try:
            server_resources = _canonical_resource_revision_material(
                LIVE_STATUS.last_telemetry_snapshot(), "server_central_telemetry"
            )
        except Exception:
            server_resources = {}
        return _semantic_revision(
            "fleet.device_facts",
            {
                "base_revision": int(original_fleet_revision()),
                "agents": sorted(agents, key=lambda item: item.get("id") or ""),
                "server_resources": server_resources,
            },
        )

    phase3b.status_source_revision = status_source_revision
    fleet_registry.fleet_source_revision = fleet_source_revision
    setattr(phase3b, marker, True)


def install_store_extension() -> None:
    try:
        from .lite_control_plane_store import CONTROL_PLANE
        from .lite_device_fact_store_extension import install_device_fact_store_extension

        install_device_fact_store_extension(CONTROL_PLANE)
    except Exception:
        return


def install_runtime_extensions() -> None:
    """Install all Device Facts adapters before the projection scheduler starts."""
    try:
        from . import lite_phase3b_projections as phase3b
    except Exception:
        return
    if getattr(phase3b, _RUNTIME_EXTENSION_MARKER, False):
        return
    # All adapters are installed before the scheduler captures builders and
    # source-revision callbacks. They only reconcile prepared/cached evidence.
    lite_runtime_services.install_phase3b_runtime_service_extension()
    install_status_projection_extension()
    install_source_revision_extensions()
    install_health_projection_extension()
    install_store_extension()
    setattr(phase3b, _RUNTIME_EXTENSION_MARKER, True)
