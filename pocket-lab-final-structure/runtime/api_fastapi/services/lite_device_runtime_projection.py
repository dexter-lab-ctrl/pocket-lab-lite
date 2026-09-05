from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from . import lite_capability_projection, lite_device_facts

_HEALTH_EXTENSION_MARKER = "_pocketlab_device_facts_health_extension_v1"


def _is_server(device: dict[str, Any]) -> bool:
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    return bool(device.get("is_current") or device.get("isCurrent") or role == "server_host")


def _prepared_server_evidence(device: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    telemetry: dict[str, Any] = {}
    services: list[dict[str, Any]] = []
    remote_access: dict[str, Any] = {}
    try:
        from .live_status import LIVE_STATUS

        sample = LIVE_STATUS.last_telemetry_snapshot()
        if isinstance(sample, dict):
            telemetry = sample
    except Exception:
        pass
    try:
        from . import lite_phase3b_projections as phase3b

        process_snapshot = phase3b.snapshot("system.processes") or {}
        remote_access = phase3b.snapshot("system.remote_access") or {}
        for item in (process_snapshot.get("items") or [])[:24]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            services.append({
                "service_id": name,
                "label": name,
                "manager": "pm2",
                "state": item.get("status") or "unknown",
                "reported_at": process_snapshot.get("updated_at"),
                "freshness": "current",
            })
        by_name = {
            str(item.get("name") or ""): item
            for item in (process_snapshot.get("items") or [])
            if isinstance(item, dict)
        }
        api_ready = str((by_name.get("pocket-api") or {}).get("status") or "").lower() == "online"
        nats_ready = str((by_name.get("pocket-nats") or {}).get("status") or "").lower() == "online"
        worker_ready = str((by_name.get("pocket-worker") or {}).get("status") or "").lower() == "online"
        agent_ready = str((by_name.get("pocket-node-agent") or {}).get("status") or "").lower() == "online"
        device["control_plane_runtime_ready"] = bool(api_ready and nats_ready)
        device["control_plane_runtime_checked_at"] = process_snapshot.get("updated_at")
        device["security_execution_ready"] = bool(worker_ready)
        device["security_execution_checked_at"] = process_snapshot.get("updated_at")
        device["command_delivery_ready"] = bool(agent_ready and nats_ready)
    except Exception:
        pass
    return telemetry, services, remote_access


def enrich_device(device: dict[str, Any]) -> dict[str, Any]:
    result = dict(device) if isinstance(device, dict) else {}
    remote_access: dict[str, Any] = {}
    if _is_server(result):
        telemetry, runtime_services, remote_access = _prepared_server_evidence(result)
        if runtime_services:
            result["_runtime_service_evidence"] = runtime_services
        source = "server_central_telemetry"
    else:
        signals = result.get("_health_signals") if isinstance(result.get("_health_signals"), dict) else {}
        telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
        if not telemetry and isinstance(result.get("telemetry"), dict):
            telemetry = result["telemetry"]
        source = "agent_telemetry"
    result = lite_device_facts.apply_device_facts(result, telemetry=telemetry, telemetry_source=source)
    dependencies = result.get("dependencies") if isinstance(result.get("dependencies"), dict) else {}
    hosted_apps = dependencies.get("hosted_apps") if isinstance(dependencies.get("hosted_apps"), list) else []
    capability_states = lite_capability_projection.verified_capabilities(
        result,
        remote_access=remote_access if remote_access else None,
        hosted_apps=hosted_apps,
    )
    by_id = {item.get("id"): item for item in capability_states if isinstance(item, dict)}
    result["capability_states"] = capability_states
    result["dependencies"] = {
        **dependencies,
        "remote_access_status": (by_id.get("remote_access") or {}).get("status", dependencies.get("remote_access_status", "unknown")),
        "restore_target_status": (by_id.get("restore_target") or {}).get("status", dependencies.get("restore_target_status", "unknown")),
        "recovery_available": (by_id.get("supervisor_recovery") or {}).get("status") == "verified",
    }
    return result


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
                (str(item.get("observed_at")) for item in observations.values() if isinstance(item, dict) and item.get("observed_at")),
                default=existing_telemetry.get("sampled_at") or existing_telemetry.get("timestamp"),
            )
            canonical_signals["telemetry"] = {
                **existing_telemetry,
                **lite_device_facts.health_signal_telemetry(observations, sampled_at=sampled_at),
            }
            canonical_signals["resource_observations"] = observations
        result = original(effective, signals=canonical_signals, previous=previous, now_epoch=now_epoch)

        # Preserve out-of-order behavior while allowing observation-only refreshes
        # to update the current values without manufacturing a health transition.
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
                    "source": fact.get("source"),
                    "freshness": fact.get("freshness"),
                    "observed_at": fact.get("observed_at"),
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


def install_store_extension() -> None:
    try:
        from .lite_control_plane_store import CONTROL_PLANE
        from .lite_device_fact_store_extension import install_device_fact_store_extension

        install_device_fact_store_extension(CONTROL_PLANE)
    except Exception:
        return
