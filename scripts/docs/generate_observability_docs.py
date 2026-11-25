#!/usr/bin/env python3
"""Generate Lite-native telemetry and legacy-retirement documentation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/observability/generated/observability-evidence-manifest.json"
OUT_DIR = ROOT / "docs/observability/generated"
MARKER = "<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:observability`. -->"

OUTPUTS = {
    "prometheus": OUT_DIR / "prometheus-scrape-reference.md",
    "loki": OUT_DIR / "loki-log-pipeline-reference.md",
    "grafana": OUT_DIR / "grafana-dashboards-reference.md",
    "gatus": OUT_DIR / "gatus-health-reference.md",
    "telemetry": OUT_DIR / "telemetry-contract-reference.md",
    "alerting": OUT_DIR / "alerting-slo-reference.md",
    "runtime_map": OUT_DIR / "observability-runtime-map.md",
}


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        print(f"Missing {MANIFEST.relative_to(ROOT)}. Run task docs:observability:evidence first.", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def page(title: str, body: str) -> str:
    return f"{MARKER}\n\n# {title}\n\n{body.rstrip()}\n"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    rows = rows or [["—"] * len(headers)]
    clean = lambda value: str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", "<br>")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(clean(value) for value in row[: len(headers)]) + " |" for row in rows)
    return "\n".join(lines)


def retirement_page(title: str, component: str, replacement: str, manifest: dict[str, Any]) -> str:
    item = next((entry for entry in manifest.get("legacy_components", []) if entry.get("name") == component), {})
    return page(title, f"""The historical **{component}** integration is retired from the supported Pocket Lab Lite bootstrap and execution path.

| Field | Value |
| --- | --- |
| Disposition | `{item.get('disposition', 'retired')}` |
| Current replacement | {replacement} |
| Runtime status | Not installed, started, probed, or required by the Lite-native control plane |

The filename remains in the generated documentation navigation for stable links and historical discoverability. It is a retirement notice, not an installation or troubleshooting guide for the old service. Native telemetry, prepared System Health, sanitized evidence, and the existing control API remain supported.
""")


def telemetry_page(manifest: dict[str, Any]) -> str:
    authority = manifest.get("native_health_authority", {})
    routes = manifest.get("fastapi_observability_routes", [])
    consumers = manifest.get("frontend_observability_consumers", [])
    contracts = manifest.get("runtime_contract_links", {})
    route_rows = [[r.get("method"), r.get("route"), r.get("function"), r.get("source_file")] for r in routes]
    consumer_rows = [[c.get("screen"), c.get("purpose"), c.get("path")] for c in consumers]
    return page("Telemetry Contract Reference", f"""Pocket Lab Lite uses the edge-first native flow:

```text
React / Vite PWA → Caddy → FastAPI → NATS / JetStream → workers and agents → prepared SQLite reads → UI
```

## Native health authority

{table(["Property", "Value"], [["Source", authority.get("source")], ["Request side effects", authority.get("request_side_effects")], ["Collector owner", authority.get("collector_owner")], ["Status vocabulary", ", ".join(authority.get("status_vocabulary", []))]])}

## FastAPI routes

{table(["Method", "Route", "Function", "Source"], route_rows)}

## Native frontend consumers

{table(["Screen", "Purpose", "Source"], consumer_rows)}

## Contract references

{table(["Contract", "Values"], [["OpenAPI paths", ", ".join(contracts.get("openapi_paths", []))], ["AsyncAPI subjects", ", ".join(contracts.get("asyncapi_subjects", []))], ["Redaction rules", ", ".join(contracts.get("redaction_rules", []))], ["Sources", ", ".join(contracts.get("contract_sources", []))]])}

Health GETs read prepared evidence and do not call Gatus, launch PM2 subprocesses, run scanners, migrate databases, or perform live external fan-out. Explicit sampling remains an owned background/command path. The browser reaches telemetry only through FastAPI; it never connects directly to NATS.
""")


def alerting_page(manifest: dict[str, Any]) -> str:
    return page("Alerting / SLO Reference", f"""This generated page records the native evidence boundary. It does not claim that an external alerting service is installed or running.

## Current evidence sources

{table(["Source group", "Files"], [[name, len(paths)] for name, paths in sorted(manifest.get("source_groups", {}).items())])}

## Candidate native SLO signals

{table(["Signal"], [[signal] for signal in ["API liveness and control-plane readiness", "Prepared health freshness", "NATS/JetStream and worker-consumer readiness", "Identity and OPA policy readiness", "SQLite/storage availability", "Fleet heartbeat freshness", "Backup verification and recovery evidence"]])}

Missing or stale observations remain visible as `unknown`/`stale`; they are not converted into green status. Alert routing and notifications are outside this retirement and require separate implementation and qualification.
""")


def runtime_map_page(manifest: dict[str, Any]) -> str:
    rows = [
        ["Native System Health", "/health, /healthz, /ready, /api/health-engine.json, /api/lite/system/health", "Prepared native projection", "LiteSystemHealth / LiteHome"],
        ["Native Identity & Access", "/api/lite/identity", "SQLite-backed identity readiness", "LiteIdentity"],
        ["Native telemetry / diagnostics", "/api/telemetry.json, /api/telemetry/live/status, /api/nats/status, /api/workers/status", "Prepared runtime observations", "System Health / diagnostics"],
        ["Events", "/api/events/recent, /ws/events", "NATS / event journal", "Operation activity"],
        ["Retired observability status", "/api/observability/status", "Deterministic HTTP 410", "Native System Health and diagnostics"],
        ["Retired GitOps compatibility", "/api/pipeline_status.json, /api/gitops/health.json, /api/git_history.json", "Deterministic HTTP 410", "Native release/source and drift checks"],
    ]
    return page("Observability Runtime Map", f"""This map connects current Lite-native UI surfaces to the authoritative control-plane paths. Legacy pages remain as generated retirement notices so historical links do not become misleading setup instructions.

{table(["Surface", "Route", "Authority", "Consumer / replacement"], rows)}

## Source groups

{table(["Group", "Files"], [[name, len(paths)] for name, paths in sorted(manifest.get("source_groups", {}).items())])}

## Validation boundary

Static generation proves source fingerprints and documentation freshness only. Runtime readiness, performance, disposable installation/upgrade, mocked browser behavior, CI, and physical Android qualification must be reported separately.
""")


def main() -> int:
    manifest = load_manifest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = {
        OUTPUTS["prometheus"]: retirement_page("Prometheus Scrape Reference", "Prometheus", "Native Telemetry / Diagnostics", manifest),
        OUTPUTS["loki"]: retirement_page("Loki Log Pipeline Reference", "Loki / Promtail", "Sanitized operational evidence and native log retention", manifest),
        OUTPUTS["grafana"]: retirement_page("Grafana Dashboards / Provisioning Reference", "Grafana", "System Health and generated evidence", manifest),
        OUTPUTS["gatus"]: retirement_page("Gatus Health Reference", "Gatus", "Prepared native `system.health` projection", manifest),
        OUTPUTS["telemetry"]: telemetry_page(manifest),
        OUTPUTS["alerting"]: alerting_page(manifest),
        OUTPUTS["runtime_map"]: runtime_map_page(manifest),
    }
    for path, content in pages.items():
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
