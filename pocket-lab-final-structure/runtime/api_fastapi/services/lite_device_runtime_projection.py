from __future__ import annotations

from typing import Any

from . import lite_capability_projection, lite_device_facts, lite_runtime_services


def _is_server(device: dict[str, Any]) -> bool:
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    return bool(
        device.get("is_current")
        or device.get("isCurrent")
        or device.get("protected_server_host")
        or role == "server_host"
    )


def _healthy(value: Any) -> bool:
    return str(value or "").strip().lower().replace("-", "_") in {
        "healthy", "ready", "online", "active", "success", "succeeded",
    }


def _snapshot_time(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("updated_at") or payload.get("checked_at") or payload.get("sampled_at")
    return str(value)[:64] if value else None


def _prepared_server_evidence(
    device: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Read only already-prepared/cached Server Host evidence.

    This helper intentionally performs no process/network probing. Collection is
    owned by the existing background Phase3B/LiveStatus pipelines; request models
    only reconcile their last prepared snapshots.
    """
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
        health_snapshot = phase3b.snapshot("system.health") or {}
        remote_access = phase3b.snapshot("system.remote_access") or {}
        nats_snapshot = phase3b.snapshot("system.nats_remote") or {}
        security_snapshot = phase3b.snapshot("security.summary") or {}
        agent_snapshot = phase3b.snapshot("system.agent") or {}

        services = lite_runtime_services.runtime_services_from_snapshot(process_snapshot)

        components = (
            health_snapshot.get("components")
            if isinstance(health_snapshot.get("components"), dict)
            else {}
        )
        api_ready = _healthy(components.get("api") or health_snapshot.get("status"))
        nats_ready = bool(
            nats_snapshot.get("primary_ready")
            if isinstance(nats_snapshot.get("primary_ready"), bool)
            else nats_snapshot.get("connected")
        )
        device["control_plane_runtime_ready"] = bool(api_ready and nats_ready)
        device["control_plane_runtime_checked_at"] = (
            _snapshot_time(health_snapshot) or _snapshot_time(nats_snapshot)
        )

        security_run_present = bool(security_snapshot.get("latest_run_id"))
        security_status = str(security_snapshot.get("status") or "").lower()
        device["security_execution_ready"] = (
            security_status in {"healthy", "ready", "succeeded", "success"}
            if security_run_present
            else None
        )
        device["security_execution_checked_at"] = _snapshot_time(security_snapshot)

        agent_items = agent_snapshot.get("items") if isinstance(agent_snapshot.get("items"), list) else []
        server_id = str(device.get("id") or device.get("node_id") or "")
        server_agent = next(
            (
                item for item in agent_items
                if isinstance(item, dict) and str(item.get("device_id") or "") == server_id
            ),
            None,
        )
        agent_delivery = (
            bool(server_agent.get("command_deliverable"))
            if isinstance(server_agent, dict) and isinstance(server_agent.get("command_deliverable"), bool)
            else None
        )
        device["command_delivery_ready"] = (
            bool(agent_delivery and nats_ready) if agent_delivery is not None else None
        )
        device["command_delivery_checked_at"] = _snapshot_time(agent_snapshot) or _snapshot_time(nats_snapshot)
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

    result = lite_device_facts.apply_device_facts(
        result, telemetry=telemetry, telemetry_source=source
    )
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
        "remote_access_status": (by_id.get("remote_access") or {}).get(
            "status", dependencies.get("remote_access_status", "unknown")
        ),
        "restore_target_status": (by_id.get("restore_target") or {}).get(
            "status", dependencies.get("restore_target_status", "unknown")
        ),
        "recovery_available": (by_id.get("supervisor_recovery") or {}).get("status") == "verified",
    }
    return result


def install_runtime_extensions() -> None:
    """Compatibility entrypoint for callers that imported the old location.

    Runtime installation is owned by ``lite_device_runtime_extensions``. Keeping
    this lazy delegate avoids a circular import while preserving the published
    test/integration contract.
    """
    from .lite_device_runtime_extensions import install_runtime_extensions as _install

    _install()
