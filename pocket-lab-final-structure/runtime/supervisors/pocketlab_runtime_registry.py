#!/usr/bin/env python3
"""Canonical Lite runtime desired-state registry.

This module deliberately contains only the current Pocket Lab Lite runtime.
Legacy Pocket Lab services (Vault, MariaDB, Gitea, Gitea runner, Gatus,
Prometheus, Grafana, Loki and Promtail) are excluded from the Lite desired
state and must never be started by Lite reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    role: str
    required: bool = True
    dependencies: Tuple[str, ...] = ()


CONTROL_PLANE_SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("pocket-nats", "messaging"),
    ServiceSpec("pocket-opa", "policy"),
    ServiceSpec("pocket-worker", "execution", dependencies=("pocket-nats", "pocket-opa")),
    ServiceSpec("pocket-api", "control-api", dependencies=("pocket-nats", "pocket-opa")),
    ServiceSpec("pocket-node-agent", "server-host-agent", dependencies=("pocket-nats",)),
    ServiceSpec("caddy-proxy", "same-origin-proxy", dependencies=("pocket-api",)),
    ServiceSpec("pocket-telemetry", "host-telemetry", required=False),
    ServiceSpec("pocketlab-core-supervisor", "core-recovery"),
)

RECONCILER_PROCESS = "pocketlab-runtime-reconciler"
PHOTOPRISM_PROCESS = "pocketlab-app-photoprism"

LEGACY_LITE_SERVICES = frozenset(
    {
        "vault",
        "mariadb",
        "gitea",
        "gitea-runner",
        "pocket-gatus",
        "gatus",
        "prometheus-db",
        "prometheus",
        "grafana-ui",
        "grafana",
        "loki-kms",
        "loki",
        "promtail-agent",
        "promtail",
    }
)

REPAIRABLE_PM2_STATUSES = frozenset({"missing", "stopped", "errored", "error"})


def control_plane_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in CONTROL_PLANE_SERVICES)


def is_legacy_lite_service(name: str) -> bool:
    return str(name or "").strip().lower() in LEGACY_LITE_SERVICES
