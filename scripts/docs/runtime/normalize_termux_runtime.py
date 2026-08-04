#!/usr/bin/env python3
"""Normalize a bounded raw Termux probe into deterministic safe semantic evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import (
    EXPECTED_SERVICE_IDS,
    OPTIONAL_SERVICE_IDS,
    RAW_SCHEMA_PATH,
    SANITIZED_SCHEMA_PATH,
    SERVICE_ROLE_MAP,
    atomic_write,
    normalize_android_major,
    normalize_architecture,
    normalized_status,
    safe_bucket_memory,
    safe_bucket_restarts,
    semantic_fingerprint,
    stable_json,
    stable_sorted,
    validate_json,
)
from runtime_redaction import assert_safe


def _presence(value: bool | None) -> str:
    if value is True:
        return "present"
    if value is False:
        return "missing"
    return "unknown"


def _service(
    service_id: str,
    role: str,
    presence: str,
    status: str,
    runtime_type: str,
    owner: str,
    *,
    restart_bucket: str = "not-applicable",
    memory_bucket: str = "not-applicable",
    optional: bool = False,
) -> dict[str, Any]:
    expected_match = "matched"
    if presence == "unknown":
        expected_match = "not-evaluated"
    elif presence == "missing":
        expected_match = "not-evaluated" if optional else "mismatched"
    return {
        "id": service_id,
        "logical_role": role,
        "presence": presence,
        "status": status,
        "runtime_type": runtime_type,
        "execution_owner": owner,
        "restart_bucket": restart_bucket,
        "memory_bucket": memory_bucket,
        "expected_source_match": expected_match,
    }


def normalize_capture(raw: dict[str, Any]) -> dict[str, Any]:
    validate_json(raw, RAW_SCHEMA_PATH)
    probes = raw["probes"]
    platform_raw = probes["platform"]
    platform_verified = (
        platform_raw["state"] == "ok"
        and str(platform_raw["kernel"]).strip().lower() in {"linux", "android"}
        and platform_raw["termux_prefix_kind"] == "termux"
    )
    platform = {
        "platform": "android-termux" if platform_verified else "unknown",
        "android_release_major": normalize_android_major(platform_raw["android_release"]),
        "architecture_family": normalize_architecture(platform_raw["architecture"]),
        "abi_family": normalize_architecture(platform_raw["abi"]),
        "termux_prefix_type": platform_raw["termux_prefix_kind"],
        "runtime_verification_state": "verified" if platform_verified else "partial",
    }

    services: dict[str, dict[str, Any]] = {}
    pm2 = probes["pm2"]
    pm2_presence = _presence(pm2["command_available"])
    services["pm2"] = _service(
        "pm2", "Termux process manager", pm2_presence,
        "ready" if pm2["state"] == "ok" else ("degraded" if pm2["command_available"] else "unavailable"),
        "node", "Termux runtime",
    )
    for process in pm2["processes"]:
        mapped = SERVICE_ROLE_MAP.get(str(process["name"]))
        if not mapped:
            continue
        service_id, role, default_runtime = mapped
        status = normalized_status(process["status"])
        services[service_id] = _service(
            service_id,
            role,
            "present",
            status,
            process.get("runtime_type") if process.get("runtime_type") != "unknown" else default_runtime,
            "PM2",
            restart_bucket=safe_bucket_restarts(process.get("restarts")),
            memory_bucket=safe_bucket_memory(process.get("memory_bytes")),
            optional=service_id in OPTIONAL_SERVICE_IDS,
        )

    caddy = probes["caddy"]
    caddy_presence = _presence(bool(caddy["command_available"] and caddy["config_present"]))
    caddy_status = "healthy" if caddy["validation_state"] == "valid" else (
        "invalid" if caddy["validation_state"] == "invalid" else "unavailable"
    )
    services["caddy"] = _service(
        "caddy", "same-origin proxy", caddy_presence, caddy_status, "native", "PM2"
    )

    nats = probes["nats"]
    nats_presence = _presence(bool(nats["command_available"] and nats["listener_present"]))
    nats_ready = (
        nats_presence == "present"
        and nats["jetstream_enabled"] is True
        and nats["bind_scope"] == "private-or-all"
    )
    services["nats"] = _service(
        "nats", "NATS/JetStream service", nats_presence,
        "ready" if nats_ready else ("degraded" if nats_presence == "present" else "unavailable"),
        "native", "PM2",
    )

    agent = probes["agent_supervisor"]
    if "node-agent" not in services:
        services["node-agent"] = _service(
            "node-agent", "server-host node agent", _presence(agent["agent_present"]),
            "online" if agent["agent_present"] else "missing", "python", "PM2"
        )
    if "core-supervisor" not in services:
        services["core-supervisor"] = _service(
            "core-supervisor", "server-host recovery supervisor", _presence(agent["core_supervisor_present"]),
            "online" if agent["core_supervisor_present"] else "missing", "python", "PM2"
        )

    tailscale = probes["tailscale"]
    tailscale_present = bool(tailscale["daemon_running"])
    services["tailscaled"] = _service(
        "tailscaled", "private remote-access daemon", _presence(tailscale_present),
        "ready" if tailscale["private_connectivity_ready"] else (
            "degraded" if tailscale_present else "unavailable"
        ),
        "native", "startup scripts", optional=True,
    )

    sqlite = probes["sqlite"]
    sqlite_present = bool(sqlite["database_present"])
    sqlite_healthy = sqlite["integrity"] == "ok" and sqlite["expected_tables_present"]
    services["sqlite"] = _service(
        "sqlite", "SQLite control-plane store", _presence(sqlite_present),
        "healthy" if sqlite_healthy else ("degraded" if sqlite_present else "unavailable"),
        "sqlite", "FastAPI and workers",
    )

    proot = probes["proot_apps"]
    services["proot-ubuntu"] = _service(
        "proot-ubuntu", "PROot Ubuntu application runtime", _presence(proot["ubuntu_present"]),
        "ready" if proot["ubuntu_present"] else "unavailable", "proot", "proot-distro",
        optional=True,
    )
    services["photoprism"] = _service(
        "photoprism", "managed PhotoPrism application", _presence(proot["photoprism_present"]),
        "online" if proot["photoprism_present"] else "unavailable", "proot", "PM2 / PROot Ubuntu",
        optional=True,
        restart_bucket=services.get("photoprism", {}).get("restart_bucket", "not-applicable"),
        memory_bucket=services.get("photoprism", {}).get("memory_bucket", "not-applicable"),
    )

    for service_id in sorted(EXPECTED_SERVICE_IDS):
        if service_id not in services:
            services[service_id] = _service(
                service_id,
                service_id.replace("-", " "),
                "unknown",
                "unknown",
                "unknown",
                "repository expected owner",
                optional=service_id in OPTIONAL_SERVICE_IDS,
            )

    messaging = {
        "service_id": "nats",
        "process_owner": nats["process_owner"],
        "client_listener_presence": _presence(nats["listener_present"]),
        "expected_client_port_present": bool(nats["expected_client_port_present"]),
        "bind_scope": nats["bind_scope"],
        "jetstream_state": (
            "enabled" if nats["jetstream_enabled"] is True
            else "disabled" if nats["jetstream_enabled"] is False
            else "unknown"
        ),
    }

    listeners = [{
        "id": "nats-client",
        "service": "nats",
        "presence": _presence(nats["listener_present"]),
        "port_kind": "nats-client",
        "bind_scope": nats["bind_scope"],
    }]

    https_owner = "caddy" if caddy["routes"]["https"] else "unavailable"
    https_mode = caddy["routes"]["https_mode"]
    route_order = caddy["routes"]["route_order"]
    routes = [
        {
            "id": "pwa",
            "presence": _presence(caddy["routes"]["pwa"]),
            "route_kind": "pwa",
            "https_owner": https_owner,
            "https_mode": https_mode,
            "route_order": route_order,
            "upstream_kind": "static-assets",
            "peer_reachability": "not-applicable",
        },
        {
            "id": "api-lite",
            "presence": _presence(caddy["routes"]["api_lite"]),
            "route_kind": "api-lite",
            "https_owner": https_owner,
            "https_mode": https_mode,
            "route_order": route_order,
            "upstream_kind": (
                caddy["routes"]["api_upstream_kind"]
                if caddy["routes"]["api_upstream_kind"] == "loopback-fastapi"
                else "unknown"
            ),
            "peer_reachability": "not-applicable",
        },
        {
            "id": "photoprism",
            "presence": _presence(caddy["routes"]["photoprism"] and proot["photoprism_route_present"]),
            "route_kind": "managed-app",
            "https_owner": https_owner,
            "https_mode": https_mode,
            "route_order": route_order,
            "upstream_kind": (
                caddy["routes"]["app_upstream_kind"]
                if caddy["routes"]["app_upstream_kind"] == "loopback-app"
                else "unknown"
            ),
            "peer_reachability": "not-applicable",
        },
        {
            "id": "remote-access",
            "presence": _presence(tailscale["private_connectivity_ready"]),
            "route_kind": "remote-access",
            "https_owner": https_owner,
            "https_mode": https_mode,
            "route_order": "not-applicable",
            "upstream_kind": "private-network",
            "peer_reachability": tailscale["peer_reachability"],
        },
    ]

    remote_access = {
        "service_id": "tailscaled",
        "command_variant": tailscale["command_variant"],
        "daemon_running": bool(tailscale["daemon_running"]),
        "ipv4_ready": bool(tailscale["ipv4_ready"]),
        "private_connectivity_ready": bool(tailscale["private_connectivity_ready"]),
        "peer_reachability": tailscale["peer_reachability"],
        "address_redacted": True,
        "hostname_redacted": True,
    }

    datastores = [{
        "id": "sqlite-control-plane",
        "service_id": "sqlite",
        "role": "control-plane-state",
        "presence": _presence(sqlite_present),
        "integrity": sqlite["integrity"],
        "journal_mode": sqlite["journal_mode"],
        "expected_tables_present": bool(sqlite["expected_tables_present"]),
        "schema_revision": sqlite["schema_revision"],
    }]

    runtime_relationships = [{
        "id": "agent-supervisor-command-path",
        "agent_presence": _presence(agent["agent_present"]),
        "supervisor_presence": _presence(agent["core_supervisor_present"]),
        "joined_supervisor_presence": _presence(agent["joined_supervisor_present"]),
        "worker_command_owner_presence": _presence(agent["worker_command_owner_present"]),
        "nats_connectivity": agent["nats_connectivity"],
        "recovery_capability": agent["recovery_capability"],
        "last_evidence_freshness_bucket": agent["last_evidence_freshness_bucket"],
        "agent_version_major": agent["agent_version_major"],
        "supervisor_version_major": agent["supervisor_version_major"],
        "expected_pm2_ownership": bool(agent["expected_pm2_ownership"]),
    }]

    runtime_apps = [{
        "id": "photoprism",
        "presence": _presence(proot["photoprism_present"]),
        "runtime": "proot-ubuntu" if proot["ubuntu_present"] else "unknown",
        "container": "ubuntu" if proot["ubuntu_present"] else "unknown",
        "pm2_owned": bool(proot["photoprism_pm2_present"]),
        "route_present": bool(proot["photoprism_route_present"]),
    }]

    unresolved: list[str] = []
    required_services = {"pm2", "caddy", "lite-api", "nats", "worker", "node-agent", "core-supervisor", "sqlite"}
    for service_id in sorted(required_services):
        item = services[service_id]
        if item["presence"] != "present":
            unresolved.append(f"services.{service_id}: required runtime missing")
        elif item["expected_source_match"] != "matched":
            unresolved.append(f"services.{service_id}: source expectation mismatch")
        elif item["status"] in {"offline", "stopped", "missing", "invalid", "degraded", "unavailable"}:
            unresolved.append(f"services.{service_id}: runtime state unhealthy")
    if messaging["jetstream_state"] != "enabled":
        unresolved.append("messaging.nats: jetstream not verified")
    if messaging["bind_scope"] != "private-or-all":
        unresolved.append("messaging.nats: fleet listener not verified")
    if next(item for item in routes if item["id"] == "pwa")["presence"] != "present":
        unresolved.append("routes.pwa: required route missing")
    api_route = next(item for item in routes if item["id"] == "api-lite")
    if api_route["presence"] != "present" or api_route["upstream_kind"] != "loopback-fastapi":
        unresolved.append("routes.api-lite: required route mismatch")
    if route_order == "pwa-before-api":
        unresolved.append("routes.api-lite: route ordering mismatch")
    relationship = runtime_relationships[0]
    if relationship["worker_command_owner_presence"] != "present":
        unresolved.append("relationships.agent-supervisor: command owner missing")
    if relationship["recovery_capability"] != "supervised":
        unresolved.append("relationships.agent-supervisor: recovery unavailable")

    runtime_state = "mismatch" if unresolved else ("verified" if platform_verified else "partial")
    projection: dict[str, Any] = {
        "schema_revision": 1,
        "capture_kind": "termux-runtime",
        "sanitized": True,
        "source": "allowlisted-read-only-ssh-probe",
        "host_role": "server-phone",
        "platform": platform,
        "services": stable_sorted(services.values()),
        "listeners": stable_sorted(listeners),
        "routes": stable_sorted(routes),
        "runtime_apps": stable_sorted(runtime_apps),
        "messaging": messaging,
        "remote_access": remote_access,
        "datastores": stable_sorted(datastores),
        "runtime_relationships": stable_sorted(runtime_relationships),
        "verification": {
            "runtime_verification_state": runtime_state,
            "forbidden_fields_found": False,
            "raw_paths_removed": True,
            "network_identity_removed": True,
            "secrets_removed": True,
            "certificate_material_removed": True,
            "private_key_material_removed": True,
            "media_paths_removed": True,
            "source_expectations_compared": True,
            "unresolved_mismatches": sorted(unresolved),
        },
    }
    projection["semantic_fingerprint"] = semantic_fingerprint(projection)
    assert_safe(projection, context="sanitized Termux runtime projection")
    validate_json(projection, SANITIZED_SCHEMA_PATH)
    return projection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    projection = normalize_capture(raw)
    atomic_write(args.output, stable_json(projection), mode=0o600)
    print(f"PASS sanitized Termux runtime projection: {projection['semantic_fingerprint'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
