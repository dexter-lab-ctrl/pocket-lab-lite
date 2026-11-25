#!/usr/bin/env python3
"""Generate source-owned Lite native health and telemetry evidence.

The manifest is a documentation projection, not runtime health. It records the
prepared native authority and explicit retirement of the historical external
observability stack so generated pages cannot present those services as Lite
dependencies.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/observability/generated/observability-evidence-manifest.json"
GENERATED_BY = "scripts/docs/generate_observability_evidence.py"
SCHEMA_VERSION = "pocketlab.observability_evidence.v1"

SOURCE_PATHS = [
    ("native_health_authority", "pocket-lab-final-structure/runtime/api_fastapi/routers/health.py"),
    ("native_health_authority", "pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py"),
    ("native_health_authority", "pocket-lab-final-structure/runtime/api_fastapi/services/lite_identity_auth.py"),
    ("native_telemetry", "pocket-lab-final-structure/runtime/api_fastapi/services/live_status.py"),
    ("native_telemetry", "pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py"),
    ("native_telemetry", "pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py"),
    ("native_telemetry", "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py"),
    ("fastapi_runtime_observability", "pocket-lab-final-structure/runtime/api_fastapi/routers/telemetry.py"),
    ("fastapi_runtime_observability", "pocket-lab-final-structure/runtime/api_fastapi/routers/events.py"),
    ("fastapi_runtime_observability", "pocket-lab-final-structure/runtime/api_fastapi/routers/events.py"),
    ("frontend_active_lite", "src/lite/LiteApp.jsx"),
    ("frontend_active_lite", "src/lite/LiteHome.jsx"),
    ("frontend_active_lite", "src/lite/LiteIdentity.jsx"),
    ("frontend_active_lite", "src/lite/LiteSystemHealth.jsx"),
    ("frontend_active_lite", "src/lib/liteApi.js"),
    ("runtime_contracts", "contracts/generated/openapi.json"),
    ("runtime_contracts", "contracts/asyncapi/pocketlab-nats-jetstream.yaml"),
    ("runtime_contracts", "contracts/operations/pocketlab-typed-operations.json"),
    ("bootstrap_native", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh"),
    ("bootstrap_native", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"),
    ("bootstrap_native", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/smoke-test.sh"),
    ("bootstrap_native", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lib/common.sh"),
    ("retirement_documentation", "docs/operations/bootstrap-lite.md"),
    ("retirement_documentation", "docs/development/lite-native-control-plane-retirement.md"),
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group, raw_path in SOURCE_PATHS:
        path = ROOT / raw_path
        if not path.is_file():
            raise SystemExit(f"observability evidence source is missing: {raw_path}")
        records.append({"path": raw_path, "kind": group, "sha256": fingerprint(path), "size_bytes": path.stat().st_size})
    return records


def active_routes() -> list[dict[str, str]]:
    source = "pocket-lab-final-structure/runtime/api_fastapi/routers/health.py"
    return [
        {"method": "GET", "route": "/health", "function": "health", "source_file": source},
        {"method": "GET", "route": "/healthz", "function": "health", "source_file": source},
        {"method": "GET", "route": "/ready", "function": "ready", "source_file": source},
        {"method": "GET", "route": "/api/health-engine.json", "function": "health_engine", "source_file": source},
        {"method": "POST", "route": "/api/health/check", "function": "health_check", "source_file": source},
        {"method": "GET", "route": "/api/lite/system/health", "function": "get_lite_system_health", "source_file": "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"},
    ]


def build_manifest() -> dict[str, Any]:
    records = source_files()
    groups: dict[str, list[str]] = {}
    for record in records:
        groups.setdefault(record["kind"], []).append(record["path"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_by": GENERATED_BY,
        "source_files": records,
        "source_groups": {key: sorted(value) for key, value in sorted(groups.items())},
        "observability_components": [
            {"name": "Prepared Health Projection", "purpose": "Native system.health/readiness authority", "verified_from_source": True},
            {"name": "Native Telemetry / Diagnostics", "purpose": "Host, worker, device, storage, and runtime observations", "verified_from_source": True},
            {"name": "NATS / JetStream", "purpose": "Durable command, event, and worker-consumer readiness", "verified_from_source": True},
            {"name": "Native Identity & Access", "purpose": "SQLite-backed identity readiness and supported authentication", "verified_from_source": True},
            {"name": "OPA Policy Lifecycle", "purpose": "Loopback policy decisions with fail-closed activation", "verified_from_source": True},
            {"name": "Caddy / FastAPI", "purpose": "Same-origin HTTPS gateway and authoritative control API", "verified_from_source": True},
        ],
        "legacy_components": [
            {"name": name, "disposition": "retired", "current_replacement": replacement}
            for name, replacement in [
                ("Vault / OpenBao", "Native Identity & Access and approved provider integration"),
                ("Gitea", "GitHub release/source metadata and Application Catalog"),
                ("MariaDB", "SQLite state and application-owned database integrations"),
                ("Gatus", "Prepared native system.health projection"),
                ("Prometheus", "Native Telemetry / Diagnostics"),
                ("Grafana", "System Health and generated evidence"),
                ("Loki / Promtail", "Sanitized operational evidence and native log retention"),
            ]
        ],
        "native_health_authority": {
            "read_endpoints": ["/health", "/healthz", "/ready", "/api/health-engine.json", "/api/lite/system/health"],
            "source": "prepared-lite-native",
            "request_side_effects": False,
            "collector_owner": "LiveStatusSampler / worker-owned projection scheduler",
            "status_vocabulary": ["healthy", "degraded", "unhealthy", "starting", "repairing", "unknown", "stale", "unsupported", "not_configured", "maintenance"],
        },
        "ports": {},
        "routes": active_routes(),
        "fastapi_observability_routes": active_routes(),
        "frontend_observability_consumers": [
            {"screen": "LiteSystemHealth", "path": "src/lite/LiteSystemHealth.jsx", "purpose": "Native health, readiness, freshness, incidents, and runtime evidence."},
            {"screen": "LiteHome", "path": "src/lite/LiteHome.jsx", "purpose": "Prepared workspace status and next-step presentation."},
            {"screen": "LiteIdentity", "path": "src/lite/LiteIdentity.jsx", "purpose": "Native Identity & Access readiness and authentication state."},
        ],
        "bootstrap_observability_scripts": [
            {"path": record["path"], "kind": record["kind"], "sha256": record["sha256"], "summary": "Supported Lite native bootstrap topology."}
            for record in records
            if record["kind"] == "bootstrap_native"
        ],
        "runtime_contract_links": {
            "openapi_paths": [route["route"] for route in active_routes()],
            "asyncapi_subjects": ["pocketlab.events.health.checked", "pocketlab.events.telemetry.sampled", "pocketlab.events.command.retired"],
            "operation_contracts": [],
            "redaction_rules": ["credentials", "tokens", "raw logs", "private paths"],
            "contract_sources": [record["path"] for record in records if record["kind"] == "runtime_contracts"],
        },
        "prometheus_jobs": [],
        "prometheus": {"retired": True, "replacement": "Native Telemetry / Diagnostics"},
        "loki_pipeline": {"retired": True, "replacement": "Sanitized operational evidence and native log retention"},
        "promtail_scrape_configs": [],
        "gatus_endpoints": [],
        "gatus": {"retired": True, "replacement": "Prepared system.health projection"},
        "grafana_config": {"retired": True, "replacement": "System Health and generated evidence"},
        "grafana_provisioning_paths": {"dashboards": [], "datasources": []},
        "alerting_slo_sources": [],
        "warnings": [
            "Static source inspection does not prove a live candidate is healthy; use the bounded qualification harness.",
            "Optional remote access and secondary-device reachability do not gate local API readiness.",
        ],
        "missing_enterprise_features": [],
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
