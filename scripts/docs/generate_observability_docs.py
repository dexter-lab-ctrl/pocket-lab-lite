#!/usr/bin/env python3
"""Generate observability evidence documentation from the evidence manifest."""
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


def esc(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(str(x) for x in value) or "—"
    elif isinstance(value, dict):
        text = ", ".join(f"{k}={v}" for k, v in value.items()) or "—"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["—" for _ in headers]]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        out.append("| " + " | ".join(esc(x) for x in padded[: len(headers)]) + " |")
    return "\n".join(out)


def source_link(path: str) -> str:
    return f"`{path}`" if path else "—"


def page(title: str, body: str) -> str:
    return f"{MARKER}\n\n# {title}\n\n{body.rstrip()}\n"


def source_summary(m: dict[str, Any]) -> str:
    groups = m.get("source_groups", {})
    rows = [[k, len(v)] for k, v in groups.items()]
    return md_table(["Source group", "Files"], rows)


def prometheus_page(m: dict[str, Any]) -> str:
    prom = m.get("prometheus", {})
    ports = m.get("ports", {})
    job_rows = []
    for job in m.get("prometheus_jobs", []):
        job_rows.append([
            job.get("job_name"),
            job.get("metrics_path"),
            job.get("targets"),
            job.get("params"),
            job.get("notes"),
            source_link(job.get("source_file", "")),
        ])
    port_rows = [[name, data.get("port"), source_link(data.get("source_file", ""))] for name, data in sorted(ports.items())]
    metrics_status = "Verified" if prom.get("fastapi_metrics_endpoint_verified") else "Not verified in this repo snapshot"
    body = f"""This page is generated from the existing Ansible observability role, inventory variables, bootstrap scripts, and runtime contracts. It documents the current Prometheus scrape setup without adding a new metrics stack.

## Port inventory

{md_table(["Component", "Port", "Source"], port_rows)}

## Prometheus global settings

{md_table(["Setting", "Value"], [["Prometheus port", prom.get("port")], ["Scrape interval", prom.get("scrape_interval")], ["Evaluation interval", prom.get("evaluation_interval")], ["FastAPI `/metrics` endpoint", metrics_status], ["Source", source_link(prom.get("source_file", ""))]])}

## Scrape jobs

{md_table(["Job", "Metrics path", "Targets", "Params", "Notes", "Source"], job_rows)}

## Enterprise-readiness notes

- Prometheus integration is verified at the platform/IaC level from the repository sources above.
- FastAPI `/metrics` is intentionally listed as **not verified** unless an endpoint exists in the FastAPI route inventory.
- Vault metrics scraping is documented from the existing Prometheus template and relies on the configured Vault metrics behavior.
- Static documentation evidence does not prove Prometheus is currently running or that all targets are `UP`.
"""
    return page("Prometheus Scrape Reference", body)


def loki_page(m: dict[str, Any]) -> str:
    pipeline = m.get("loki_pipeline", {})
    loki = pipeline.get("loki", {})
    promtail = pipeline.get("promtail", {})
    routes = pipeline.get("caddy_routes", [])
    fastapi = [r for r in m.get("fastapi_observability_routes", []) if "loki" in r.get("route", "") or r.get("route") == "/api/v1/query"]
    frontend = [r for r in m.get("frontend_observability_consumers", []) if "LogExplorer" in r.get("screen", "") or "SecurityPosture" in r.get("screen", "")]
    body = f"""This generated page distinguishes the real Loki service, the Promtail log pipeline, Caddy routes, and FastAPI's Loki-compatible query API.

## Loki service

{md_table(["Field", "Value"], [["Listen address", loki.get("http_listen_address")], ["Listen port", loki.get("http_listen_port")], ["Query path", loki.get("query_path")], ["Path prefix", loki.get("path_prefix")], ["Chunks directory", loki.get("chunks_directory")], ["Rules directory", loki.get("rules_directory")], ["Source", source_link(loki.get("source_file", ""))]])}

## Promtail pipeline

{md_table(["Field", "Value"], [["Promtail listen port", promtail.get("http_listen_port")], ["Loki push URL", promtail.get("push_url")], ["Positions file", promtail.get("positions_file")], ["Source", source_link(promtail.get("source_file", ""))]])}

## Promtail scrape jobs

{md_table(["Job", "Targets", "Log path pattern", "Source"], [[j.get("job_name"), j.get("targets"), j.get("log_path_pattern"), source_link(j.get("source_file", ""))] for j in promtail.get("scrape_configs", [])])}

## Caddy observability routes

{md_table(["Route", "Upstream", "Source"], [[r.get("route"), r.get("upstream"), source_link(r.get("source_file", ""))] for r in routes])}

## FastAPI Loki-compatible query routes

{md_table(["Method", "Route", "Function", "Source"], [[r.get("method"), r.get("route"), r.get("function"), source_link(r.get("source_file", ""))] for r in fastapi])}

## UI log consumers

{md_table(["Consumer", "Purpose", "Endpoints / tokens", "Source"], [[r.get("screen"), r.get("purpose"), r.get("endpoints_or_tokens"), source_link(r.get("path", ""))] for r in frontend])}

## Redaction and access notes

{md_table(["Note"], [[n] for n in pipeline.get("redaction_notes", [])])}

- This page does not claim the Loki service is currently running. Use runtime checks such as `curl -fsS http://127.0.0.1:3100/ready` for live validation.
- The route `/loki/api/v1/query` can refer to the real Loki API behind Caddy or the FastAPI Loki-compatible query endpoint depending on the deployment path. Keep that distinction visible during troubleshooting.
"""
    return page("Loki Log Pipeline Reference", body)


def grafana_page(m: dict[str, Any]) -> str:
    g = m.get("grafana_config", {})
    body = f"""This generated page documents Grafana configuration and provisioning paths that exist in the current repository snapshot.

## Grafana runtime config

{md_table(["Field", "Value"], [["Port", g.get("port")], ["HTTP address", g.get("http_addr")], ["Data path", g.get("data_path")], ["Logs path", g.get("logs_path")], ["Plugins path", g.get("plugins_path")], ["Provisioning path", g.get("provisioning_path")], ["Source files", [source_link(p) for p in g.get("source_files", [])]]])}

## Provisioning directories

{md_table(["Type", "Paths"], [["Dashboards", g.get("dashboard_provisioning_dirs")], ["Datasources", g.get("datasource_provisioning_dirs")]])}

## Provisioned source files verified

{md_table(["Artifact type", "Verified", "Files"], [["Dashboard JSON", "yes" if g.get("dashboard_json_files") else "no", [source_link(p) for p in g.get("dashboard_json_files", [])]], ["Datasource YAML", "yes" if g.get("datasource_yaml_files") else "no", [source_link(p) for p in g.get("datasource_yaml_files", [])]]])}

## Enterprise-readiness notes

- Grafana itself is verified from the Ansible observability role and generated `custom.ini` template.
- Dashboard directories and datasource directories are verified as runtime/provisioning paths.
- Dashboards-as-code and datasources-as-code are **not claimed** unless committed dashboard JSON or datasource YAML files are found.
"""
    return page("Grafana Dashboards / Provisioning Reference", body)


def gatus_page(m: dict[str, Any]) -> str:
    endpoints = m.get("gatus_endpoints", [])
    gatus = m.get("gatus", {})
    rows = [[e.get("name"), e.get("group"), e.get("url"), e.get("interval"), e.get("conditions"), source_link(e.get("source_file", ""))] for e in endpoints]
    groups = sorted({e.get("group", "") for e in endpoints if e.get("group")})
    body = f"""This generated page documents Gatus as Pocket Lab's health aggregation layer when verified by repository source.

## Gatus integration summary

{md_table(["Field", "Value"], [["Port", gatus.get("port")], ["Health-engine integration", gatus.get("health_engine_integration")], ["Fallback behavior", gatus.get("fallback_behavior")], ["Endpoint groups", groups], ["Source", source_link(gatus.get("source_file", ""))]])}

## Health checks

{md_table(["Name", "Group", "URL", "Interval", "Conditions", "Source"], rows)}

## Operating notes

- Gatus status is consumed by FastAPI health aggregation when reachable.
- Fallback behavior must remain explicit in operator-facing responses; generated documentation distinguishes `source=gatus` from fallback behavior.
- Static source inspection does not prove that Gatus is currently running. Use `curl -fsS http://127.0.0.1:8081/health` for live validation.
"""
    return page("Gatus Health Reference", body)


def telemetry_page(m: dict[str, Any]) -> str:
    links = m.get("runtime_contract_links", {})
    fastapi = m.get("fastapi_observability_routes", [])
    consumers = m.get("frontend_observability_consumers", [])
    subjects = links.get("asyncapi_subjects", [])
    redaction = links.get("redaction_rules", [])
    body = f"""This generated page ties Pocket Lab observability back to the control-plane contract model.

Pocket Lab runtime flow remains:

```text
React / Vite PWA
→ FastAPI Control API
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

## FastAPI observability and telemetry routes

{md_table(["Method", "Route", "Function", "Source"], [[r.get("method"), r.get("route"), r.get("function"), source_link(r.get("source_file", ""))] for r in fastapi])}

## OpenAPI observability paths

{md_table(["OpenAPI path"], [[p] for p in links.get("openapi_paths", [])])}

## AsyncAPI / event subjects related to observability

{md_table(["Subject"], [[s] for s in subjects])}

## Frontend event, health, telemetry, and log consumers

{md_table(["Consumer", "Purpose", "Hooks", "Endpoints", "Source"], [[c.get("screen"), c.get("purpose"), c.get("hooks"), c.get("endpoints_or_tokens"), source_link(c.get("path", ""))] for c in consumers])}

## Redaction rules

{md_table(["Sensitive key"], [[x] for x in redaction])}

## Contract sources

{md_table(["Source"], [[source_link(p)] for p in links.get("contract_sources", [])])}

## Correlation expectations

- Every write workflow should remain traceable through API request, NATS command, worker logs, operation events, audit events, and UI event panels.
- Lifecycle events must remain observable and auditable.
- The frontend must consume runtime observability health through FastAPI only; it must not call Prometheus, Loki, Grafana, Gatus, Promtail, or NATS directly.
- DLQ and retry subjects should remain visible through generated event contracts and operator diagnostics.
"""
    return page("Telemetry Contract Reference", body)


def alerting_page(m: dict[str, Any]) -> str:
    sources = m.get("alerting_slo_sources", [])
    status = "Verified" if sources else "Not verified in the current repo snapshot"
    future = [
        ["observability/alerts/pocketlab-alerts.yaml", "Future alert rule source"],
        ["observability/slo/pocketlab-slos.yaml", "Future SLO metadata source"],
    ]
    slos = [
        ["API ready endpoint availability"],
        ["NATS command publish success"],
        ["Worker heartbeat freshness"],
        ["Runbook execution success ratio"],
        ["Operation failure ratio"],
        ["Vault health"],
        ["Loki ready"],
        ["Prometheus ready"],
        ["Grafana health"],
        ["Fleet node freshness"],
        ["Backup verification success"],
    ]
    body = f"""Alert/SLO source files were **{status}**.

This page is a generated gap and roadmap reference unless alert/SLO source files are present in the manifest. It is not a claim that alerting is implemented.

## Verified alert/SLO source files

{md_table(["Source"], [[source_link(p)] for p in sources])}

## Recommended future source files

{md_table(["Path", "Purpose"], future)}

## Candidate future SLOs

{md_table(["SLO"], slos)}

## Current limitations

- Static source inspection does not prove services are running or alerting is active.
- Alertmanager, SLO burn-rate rules, and notification routing are not part of the observability evidence baseline unless implemented separately with validation.
- Do not expose observability endpoints broadly without access-control guidance.
"""
    return page("Alerting / SLO Reference", body)


def runtime_map_page(m: dict[str, Any]) -> str:
    rows = [
        ["Log Explorer", "/loki/api/v1/query", "control_plane_core.search_loki()", "Loki-compatible logs", "Loki / Promtail", "Observability / Log Explorer", "—"],
        ["Security Posture", "/loki/api/v1/query?query={job=\"pm2_logs\"} |= \"security_audit\"", "security audit log query", "Security audit log activity", "Loki / Promtail", "Safety Center / Security Posture", "rotate_secret_with_audit, security_scan"],
        ["NOC Telemetry / System Status", "/api/telemetry.json, /api/health-engine.json", "LIVE_STATUS sampler and health engine", "Health + telemetry snapshots", "Gatus when reachable, fallback otherwise", "System Status", "health_check"],
        ["Runtime Observability Health", "/api/observability/status", "observability_status service", "Prometheus/Loki/Grafana/Gatus readiness, Prometheus target summary, inferred Promtail log shipping", "FastAPI-owned bounded runtime probes", "System Status", "health_check"],
        ["Event panels", "/api/events/recent, /ws/events", "FastAPI event bus replay/stream", "NATS / event journal", "NATS / JetStream", "Operation activity panels", "All runbooks via lifecycle events"],
        ["NATS status", "/api/nats/status", "NATS bus status service", "NATS monitor/runtime status", "NATS / JetStream", "Runtime diagnostics", "—"],
        ["Worker status", "/api/workers/status", "worker registry/status route", "Worker runtime status", "Workers", "Runtime diagnostics", "—"],
        ["Gatus health dashboard", "/gatus/* via Caddy", "Caddy reverse proxy", "Health checks", "Gatus", "Health Engine", "health_check"],
        ["Loki route", "/loki/* via Caddy", "Caddy reverse proxy", "Log query API", "Loki or FastAPI-compatible route depending on deployment", "Log Explorer", "—"],
    ]
    warnings = m.get("warnings", [])
    missing = m.get("missing_enterprise_features", [])
    body = f"""This generated map connects operator-facing UI surfaces to FastAPI endpoints, runtime events, and observability components.

## Runtime map

{md_table(["UI surface", "FastAPI / Route", "Runtime function", "Observability source", "Component", "Operator-facing page", "Related runbook"], rows)}

## Source inventory

{source_summary(m)}

## Warnings from source inspection

{md_table(["Warning"], [[w] for w in warnings])}

## Missing enterprise hardening features

{md_table(["Missing / planned item"], [[x] for x in missing])}

## Validation boundary

- observability evidence static validation proves generated evidence and documentation freshness from repository sources.
- runtime observability status runtime health is exposed through FastAPI at `/api/observability/status` and must be validated separately from observability evidence static evidence.
- Runtime health can also be cross-checked with service checks such as Prometheus `/-/ready`, Loki `/ready`, Grafana `/api/health`, Gatus `/health`, and bounded Loki `pm2_logs` queries.
"""
    return page("Observability Runtime Map", body)


def main() -> int:
    m = load_manifest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = {
        OUTPUTS["prometheus"]: prometheus_page(m),
        OUTPUTS["loki"]: loki_page(m),
        OUTPUTS["grafana"]: grafana_page(m),
        OUTPUTS["gatus"]: gatus_page(m),
        OUTPUTS["telemetry"]: telemetry_page(m),
        OUTPUTS["alerting"]: alerting_page(m),
        OUTPUTS["runtime_map"]: runtime_map_page(m),
    }
    for path, content in pages.items():
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
