#!/usr/bin/env python3
"""Generate Pocket Lab observability evidence observability evidence from repository sources.

This script is documentation-only. It inspects the existing Pocket Lab
observability implementation (Prometheus, Grafana, Loki, Promtail, Gatus,
Caddy, FastAPI, frontend consumers, contracts, and bootstrap scripts) and
emits a deterministic manifest consumed by generated docs and freshness checks.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"PyYAML is required for observability evidence observability docs: {exc}", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/observability/generated/observability-evidence-manifest.json"
GENERATED_BY = "scripts/docs/generate_observability_evidence.py"
SCHEMA_VERSION = "pocketlab.observability_evidence.v1"

GENERATED_OUTPUTS = {
    "docs/observability/generated/observability-evidence-manifest.json",
    "docs/observability/generated/prometheus-scrape-reference.md",
    "docs/observability/generated/loki-log-pipeline-reference.md",
    "docs/observability/generated/grafana-dashboards-reference.md",
    "docs/observability/generated/gatus-health-reference.md",
    "docs/observability/generated/telemetry-contract-reference.md",
    "docs/observability/generated/alerting-slo-reference.md",
    "docs/observability/generated/observability-runtime-map.md",
}

OBSERVABILITY_SOURCE_PATHS = [
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/observability.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/observability.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/all.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/all.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/caddy.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/caddy.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/drift_check.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/drift_check.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/caddy/templates/Caddyfile.j2",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/caddy/tasks/main.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/caddy/defaults/main.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/defaults/main.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/tasks/main.yml",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/prometheus.yml.j2",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/loki-config.yaml.j2",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/promtail-config.yaml.j2",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/gatus-config.yaml.j2",
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/custom.ini.j2",
    "src/tabs/LogExplorerTab.jsx",
    "src/tabs/SecurityPostureTab.jsx",
    "src/tabs/NocTelemetryTab.jsx",
    "src/components/RuntimeObservabilityStatusPanel.jsx",
    "src/hooks/useObservabilityStatus.js",
    "src/hooks/useHealthEngine.js",
    "src/hooks/useTelemetry.js",
    "src/hooks/usePocketLabEvents.js",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/security.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/health.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/observability.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/telemetry.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/events.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/nats.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/workers.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/live_status.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/observability_status.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py",
    "pocket-lab-final-structure/runtime/core/control_plane_core.py",
    "contracts/generated/openapi.json",
    "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
    "contracts/operations/pocketlab-typed-operations.json",
    "docs/runtime/nats-jetstream-event-contract.md",
    "docs/runtime/typed-operations-catalog.md",
    "docs/observability/observability-logging-guide.md",
    "scripts/dev/observability-snapshot.sh",
]

BOOTSTRAP_DIRS = [
    Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"),
    Path("scripts/dev"),
]

OBSERVABILITY_TOKENS = (
    "prometheus",
    "grafana",
    "loki",
    "promtail",
    "gatus",
    "observability",
    "telemetry",
    "health-engine",
    "pm2_logs",
)

FRONTEND_FILES = [
    Path("src/tabs/LogExplorerTab.jsx"),
    Path("src/tabs/SecurityPostureTab.jsx"),
    Path("src/tabs/NocTelemetryTab.jsx"),
    Path("src/components/RuntimeObservabilityStatusPanel.jsx"),
    Path("src/hooks/useObservabilityStatus.js"),
    Path("src/hooks/useHealthEngine.js"),
    Path("src/hooks/useTelemetry.js"),
    Path("src/hooks/usePocketLabEvents.js"),
]

FASTAPI_FILES = [
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/security.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/health.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/observability.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/telemetry.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/events.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/nats.py"),
    Path("pocket-lab-final-structure/runtime/api_fastapi/routers/workers.py"),
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record(path: Path, kind: str) -> dict[str, Any]:
    return {
        "path": rel(path),
        "kind": kind,
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
    }


def yaml_load(path: Path) -> Any:
    try:
        return yaml.safe_load(read_text(path))
    except Exception as exc:
        return {"__yaml_error__": str(exc)}


def existing(path: str | Path) -> Path | None:
    p = ROOT / path
    return p if p.exists() and p.is_file() else None


def group_for(path: Path) -> str:
    r = rel(path)
    if "/roles/observability/" in r:
        return "ansible_observability_role"
    if "/inventory/" in r and "/group_vars/" in r:
        return "ansible_inventory_vars"
    if "/roles/caddy/" in r:
        return "caddy_routes"
    if r.startswith("src/tabs/") or r.startswith("src/hooks/") or r.startswith("src/components/"):
        return "frontend_observability_consumers"
    if r.startswith("pocket-lab-final-structure/runtime/api_fastapi") or r.startswith("pocket-lab-final-structure/runtime/core"):
        return "fastapi_runtime_observability"
    if r.startswith("contracts/") or r.startswith("docs/runtime/"):
        return "runtime_contracts"
    if r.startswith("docs/observability/"):
        return "observability_human_docs"
    if r.startswith("scripts/dev/") or "bootstrap-production" in r:
        return "bootstrap_observability_scripts"
    return "other_observability_source"


def collect_source_files() -> list[dict[str, Any]]:
    files: dict[str, tuple[Path, str]] = {}
    for candidate in OBSERVABILITY_SOURCE_PATHS:
        p = existing(candidate)
        if p:
            files[rel(p)] = (p, group_for(p))
    for base in BOOTSTRAP_DIRS:
        root = ROOT / base
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.name.endswith((".bak", ".tmp")):
                continue
            text = read_text(p).lower()
            if any(t in text for t in OBSERVABILITY_TOKENS):
                files[rel(p)] = (p, "bootstrap_observability_scripts")
    # Include source-level observability schemas if they exist.
    for p in (ROOT / "contracts").rglob("*telemetry*.*") if (ROOT / "contracts").exists() else []:
        if p.is_file() and rel(p) not in GENERATED_OUTPUTS:
            files[rel(p)] = (p, "runtime_contracts")
    records = []
    for key in sorted(files):
        if key in GENERATED_OUTPUTS:
            continue
        p, kind = files[key]
        records.append(source_record(p, kind))
    return records


def extract_ports(paths: list[Path]) -> dict[str, Any]:
    ports: dict[str, Any] = {}
    for p in paths:
        if not p.exists():
            continue
        for match in re.finditer(r"observability_(prometheus|loki|promtail|grafana|gatus)_port:\s*([0-9]+)", read_text(p)):
            name, port = match.groups()
            ports[name] = {"port": int(port), "source_file": rel(p)}
    return ports


def normalize_template_value(value: str) -> str:
    return value.strip().strip('"').strip("'")


def scrape_jobs_from_prometheus(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = read_text(path)
    jobs: list[dict[str, Any]] = []
    chunks = re.split(r"\n\s*-\s+job_name:\s*", "\n" + text)
    for chunk in chunks[1:]:
        first, _, rest = chunk.partition("\n")
        name = normalize_template_value(first)
        targets = [normalize_template_value(t) for t in re.findall(r'"([^"\n]+:[^"\n]+)"', rest)]
        metrics_path = None
        mm = re.search(r"metrics_path:\s*['\"]?([^'\"\n]+)", rest)
        if mm:
            metrics_path = normalize_template_value(mm.group(1))
        params: dict[str, Any] = {}
        if "format:" in rest and "prometheus" in rest:
            params["format"] = ["prometheus"]
        jobs.append(
            {
                "job_name": name,
                "targets": targets,
                "metrics_path": metrics_path or "/metrics",
                "params": params,
                "source_file": rel(path),
                "notes": "Vault metrics rely on unauthenticated_metrics_access" if name == "vault" else "",
            }
        )
    return jobs


def loki_pipeline(loki_path: Path, promtail_path: Path, caddy_path: Path) -> dict[str, Any]:
    loki_text = read_text(loki_path) if loki_path.exists() else ""
    promtail_text = read_text(promtail_path) if promtail_path.exists() else ""
    caddy_text = read_text(caddy_path) if caddy_path.exists() else ""
    loki_port = re.search(r"http_listen_port:\s*([^\n]+)", loki_text)
    loki_addr = re.search(r"http_listen_address:\s*([^\n]+)", loki_text)
    path_prefix = re.search(r"path_prefix:\s*([^\n]+)", loki_text)
    chunks = re.search(r"chunks_directory:\s*([^\n]+)", loki_text)
    rules = re.search(r"rules_directory:\s*([^\n]+)", loki_text)
    push_url = re.search(r"url:\s*(http[^\n]+)", promtail_text)
    positions = re.search(r"filename:\s*([^\n]+)", promtail_text)
    promtail_port = re.search(r"http_listen_port:\s*([^\n]+)", promtail_text)
    scrape_jobs = []
    for chunk in re.split(r"\n\s*-\s+job_name:\s*", "\n" + promtail_text)[1:]:
        first, _, rest = chunk.partition("\n")
        path_match = re.search(r"__path__:\s*([^\n]+)", rest)
        scrape_jobs.append(
            {
                "job_name": normalize_template_value(first),
                "targets": [normalize_template_value(t) for t in re.findall(r"-\s*([^\n]+)", rest) if t.strip() == "localhost"],
                "log_path_pattern": normalize_template_value(path_match.group(1)) if path_match else "",
                "source_file": rel(promtail_path),
            }
        )
    caddy_routes = []
    for handle in re.finditer(r"handle\s+([^\s]+)\s+\{\s*\n\s*reverse_proxy\s+([^\n]+)", caddy_text, re.MULTILINE):
        route, upstream = handle.groups()
        if "loki" in route or "gatus" in route:
            caddy_routes.append({"route": route, "upstream": upstream.strip(), "source_file": rel(caddy_path)})
    return {
        "loki": {
            "http_listen_port": normalize_template_value(loki_port.group(1)) if loki_port else "",
            "http_listen_address": normalize_template_value(loki_addr.group(1)) if loki_addr else "",
            "path_prefix": normalize_template_value(path_prefix.group(1)) if path_prefix else "",
            "chunks_directory": normalize_template_value(chunks.group(1)) if chunks else "",
            "rules_directory": normalize_template_value(rules.group(1)) if rules else "",
            "query_path": "/loki/api/v1/query",
            "source_file": rel(loki_path) if loki_path.exists() else "",
        },
        "promtail": {
            "http_listen_port": normalize_template_value(promtail_port.group(1)) if promtail_port else "",
            "push_url": normalize_template_value(push_url.group(1)) if push_url else "",
            "positions_file": normalize_template_value(positions.group(1)) if positions else "",
            "scrape_configs": scrape_jobs,
            "source_file": rel(promtail_path) if promtail_path.exists() else "",
        },
        "caddy_routes": caddy_routes,
        "redaction_notes": [
            "Do not expose token, password, secret, api_key, authorization, private_key, value, or join-secret material in logs.",
            "FastAPI Loki-compatible routes should return safe query results only and preserve existing redaction behavior.",
        ],
    }


def gatus_endpoints_from_template(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = read_text(path)
    endpoints: list[dict[str, Any]] = []
    chunks = re.split(r"\n\s*-\s+name:\s*", "\n" + text)
    for chunk in chunks[1:]:
        first, _, rest = chunk.partition("\n")
        name = normalize_template_value(first)
        group = re.search(r"group:\s*([^\n]+)", rest)
        url = re.search(r"url:\s*([^\n]+)", rest)
        interval = re.search(r"interval:\s*([^\n]+)", rest)
        conditions = [normalize_template_value(c) for c in re.findall(r"-\s*\"([^\"]+)\"", rest)]
        endpoints.append(
            {
                "name": name,
                "group": normalize_template_value(group.group(1)) if group else "",
                "url": normalize_template_value(url.group(1)) if url else "",
                "interval": normalize_template_value(interval.group(1)) if interval else "",
                "conditions": conditions,
                "source_file": rel(path),
            }
        )
    return endpoints


def grafana_config(custom_ini: Path, task_file: Path) -> dict[str, Any]:
    text = read_text(custom_ini) if custom_ini.exists() else ""
    def get_ini(name: str) -> str:
        m = re.search(rf"^{re.escape(name)}\s*=\s*(.+)$", text, re.MULTILINE)
        return normalize_template_value(m.group(1)) if m else ""
    dashboard_dirs = []
    datasource_dirs = []
    task_text = read_text(task_file) if task_file.exists() else ""
    for match in re.finditer(r"-\s*\"([^\"]*grafana/provisioning/(dashboards|datasources)[^\"]*)\"", task_text):
        target, kind = match.groups()
        if kind == "dashboards":
            dashboard_dirs.append(target)
        else:
            datasource_dirs.append(target)
    dashboard_files = [rel(p) for p in sorted(ROOT.rglob("*.json")) if "grafana" in rel(p).lower() and "dashboard" in rel(p).lower() and "site/" not in rel(p)]
    datasource_files = [rel(p) for p in sorted(ROOT.rglob("*.yml")) if "grafana" in rel(p).lower() and "datasource" in rel(p).lower() and "site/" not in rel(p)]
    return {
        "port": get_ini("http_port"),
        "http_addr": get_ini("http_addr"),
        "data_path": get_ini("data"),
        "logs_path": get_ini("logs"),
        "plugins_path": get_ini("plugins"),
        "provisioning_path": get_ini("provisioning"),
        "dashboard_provisioning_dirs": sorted(set(dashboard_dirs)),
        "datasource_provisioning_dirs": sorted(set(datasource_dirs)),
        "dashboard_json_files": dashboard_files,
        "datasource_yaml_files": datasource_files,
        "dashboards_as_code_verified": bool(dashboard_files),
        "datasources_as_code_verified": bool(datasource_files),
        "source_files": [rel(p) for p in [custom_ini, task_file] if p.exists()],
    }


def fastapi_routes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in FASTAPI_FILES:
        full = ROOT / path
        if not full.exists():
            continue
        text = read_text(full)
        for method, route in re.findall(r"@router\.(get|post|put|delete|websocket)\(\s*['\"]([^'\"]+)['\"]", text):
            if any(t in route.lower() for t in ["loki", "health", "telemetry", "event", "nats", "worker", "ready", "metrics"]):
                function = ""
                idx = text.find(route)
                fn = re.search(r"def\s+([A-Za-z0-9_]+)|async\s+def\s+([A-Za-z0-9_]+)", text[idx:idx+500]) if idx >= 0 else None
                if fn:
                    function = next(g for g in fn.groups() if g)
                rows.append({"method": method.upper(), "route": route, "function": function, "source_file": rel(full)})
    return sorted(rows, key=lambda r: (r["route"], r["method"]))


def openapi_observability_paths() -> list[str]:
    path = ROOT / "contracts/generated/openapi.json"
    if not path.exists():
        return []
    try:
        data = json.loads(read_text(path))
    except Exception:
        return []
    result = []
    for p in sorted(data.get("paths", {})):
        if any(t in p.lower() for t in ["loki", "health", "telemetry", "event", "nats", "worker", "ready", "metrics"]):
            result.append(p)
    return result


def frontend_consumers() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in FRONTEND_FILES:
        full = ROOT / path
        if not full.exists():
            continue
        text = read_text(full)
        fetch_targets = []
        fetch_targets += re.findall(r"fetch\(\s*`([^`]+)`", text)
        fetch_targets += re.findall(r"fetch\(\s*['\"]([^'\"]+)['\"]", text)
        literal_paths = re.findall(r"['\"](/(?:api|loki|ws)/[^'\"]+)['\"]", text)
        hooks = [name for name in ["useHealthEngine", "useTelemetry", "useObservabilityStatus", "usePocketLabEvents"] if name in text]
        endpoints = sorted({x.strip() for x in fetch_targets + literal_paths if any(t in x.lower() for t in ["loki", "health-engine", "observability", "telemetry", "events", "nats", "workers", "ready", "metrics"])})
        name = path.stem
        if name == "LogExplorerTab":
            ui_purpose = "Log Explorer queries Loki-compatible log data through FastAPI."
        elif name == "SecurityPostureTab":
            ui_purpose = "Security Posture surfaces safety scans and security log activity."
        elif name == "NocTelemetryTab":
            ui_purpose = "NOC Telemetry / System Status consumes health, telemetry, and runtime observability snapshots."
        elif name == "RuntimeObservabilityStatusPanel":
            ui_purpose = "UI card for live Prometheus, Loki, Grafana, Gatus, Promtail, and Prometheus target status through FastAPI."
        elif name == "useObservabilityStatus":
            ui_purpose = "Shared hook that polls FastAPI runtime observability health status."
        elif name == "useHealthEngine":
            ui_purpose = "Shared hook that polls FastAPI health-engine snapshots."
        elif name == "useTelemetry":
            ui_purpose = "Shared hook that polls FastAPI telemetry snapshots."
        elif name == "usePocketLabEvents":
            ui_purpose = "Shared hook that replays recent events and streams live Pocket Lab events."
        else:
            ui_purpose = "Frontend observability consumer."
        rows.append({
            "screen": name,
            "path": rel(full),
            "endpoints_or_tokens": endpoints[:20],
            "hooks": hooks,
            "purpose": ui_purpose,
        })
    return rows


def runtime_contract_links() -> dict[str, Any]:
    links: dict[str, Any] = {
        "openapi_paths": openapi_observability_paths(),
        "asyncapi_subjects": [],
        "operation_contracts": [],
        "redaction_rules": [],
        "contract_sources": [],
    }
    openapi = ROOT / "contracts/generated/openapi.json"
    asyncapi = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"
    ops = ROOT / "contracts/operations/pocketlab-typed-operations.json"
    for p in [openapi, asyncapi, ops, ROOT / "docs/runtime/nats-jetstream-event-contract.md", ROOT / "docs/runtime/typed-operations-catalog.md"]:
        if p.exists():
            links["contract_sources"].append(rel(p))
    if asyncapi.exists():
        text = read_text(asyncapi)
        subjects = sorted(set(re.findall(r"pocketlab\.(?:events|audit|dlq|commands)\.[A-Za-z0-9_.*>-]+", text)))
        links["asyncapi_subjects"] = [s for s in subjects if any(t in s for t in ["telemetry", "health", "worker", "operation", "audit", "dlq"])]
        try:
            data = yaml.safe_load(text)
            red = data.get("x-pocketlab-redaction", {}) if isinstance(data, dict) else {}
            links["redaction_rules"] = list(red.get("sensitive_keys", [])) if isinstance(red, dict) else []
        except Exception:
            pass
    if ops.exists():
        try:
            data = json.loads(read_text(ops))
            operations = data.get("operations", data if isinstance(data, list) else [])
            for item in operations if isinstance(operations, list) else []:
                blob = json.dumps(item).lower()
                name = item.get("operation") or item.get("name") or item.get("metadata", {}).get("name")
                if name and any(t in blob for t in ["health", "telemetry", "security", "nats", "event"]):
                    links["operation_contracts"].append(str(name))
        except Exception:
            pass
    return links


def bootstrap_scripts(source_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in source_files:
        if rec.get("kind") != "bootstrap_observability_scripts":
            continue
        path = ROOT / rec["path"]
        text = read_text(path)
        tokens = sorted({t for t in OBSERVABILITY_TOKENS if t in text.lower()})
        rows.append({**rec, "observability_tokens": tokens, "summary": first_comment(path)})
    return rows


def first_comment(path: Path) -> str:
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and len(stripped.strip("# ")) >= 6 and "!/" not in stripped:
            return stripped.strip("# ")
    return path.name


def caddy_routes(caddy_path: Path, caddy_var_paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    if caddy_path.exists():
        text = read_text(caddy_path)
        for handle in re.finditer(r"handle\s+([^\s]+)\s+\{\s*\n\s*reverse_proxy\s+([^\n]+)", text, re.MULTILINE):
            route, upstream = handle.groups()
            if any(t in route.lower() for t in ["loki", "gatus", "api", "ws", "health", "ready"]):
                rows.append({"route": route, "upstream": upstream.strip(), "source_file": rel(caddy_path)})
    for path in caddy_var_paths:
        if not path.exists():
            continue
        data = yaml_load(path)
        routes = data.get("caddy_routes", {}) if isinstance(data, dict) else {}
        for name, target in routes.items() if isinstance(routes, dict) else []:
            if name in {"loki", "gatus", "api"}:
                rows.append({"route": f"caddy_routes.{name}", "upstream": str(target), "source_file": rel(path)})
    return rows


def has_fastapi_metrics_endpoint(routes: list[dict[str, Any]]) -> bool:
    return any(r.get("route") == "/metrics" for r in routes)


def main() -> int:
    source_files = collect_source_files()
    source_paths = [ROOT / rec["path"] for rec in source_files]
    defaults = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/defaults/main.yml"
    inv_obs = [ROOT / p for p in [
        "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/observability.yml",
        "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/observability.yml",
        "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/defaults/main.yml",
    ]]
    prometheus = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/prometheus.yml.j2"
    loki = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/loki-config.yaml.j2"
    promtail = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/promtail-config.yaml.j2"
    gatus = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/gatus-config.yaml.j2"
    grafana_ini = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/templates/custom.ini.j2"
    obs_tasks = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/observability/tasks/main.yml"
    caddy_template = ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/roles/caddy/templates/Caddyfile.j2"
    caddy_vars = [ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/dev/group_vars/caddy.yml", ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible/inventory/prod/group_vars/caddy.yml"]

    ports = extract_ports(inv_obs)
    routes = fastapi_routes()
    runtime_contracts = runtime_contract_links()
    grafana = grafana_config(grafana_ini, obs_tasks)
    warnings: list[str] = []
    missing_enterprise_features: list[str] = []
    if not has_fastapi_metrics_endpoint(routes):
        warnings.append("FastAPI /metrics endpoint was not verified in the current repository snapshot.")
        missing_enterprise_features.append("First-class FastAPI /metrics endpoint and app-level metrics instrumentation.")
    if not grafana.get("dashboard_json_files"):
        warnings.append("Grafana directories/config exist, but dashboard JSON files were not verified.")
        missing_enterprise_features.append("Grafana dashboards-as-code JSON under a committed provisioning path.")
    if not grafana.get("datasource_yaml_files"):
        warnings.append("Grafana datasource provisioning YAML was not verified.")
        missing_enterprise_features.append("Grafana datasource provisioning as code for Prometheus and Loki.")
    alert_files = [rel(p) for p in sorted((ROOT / "observability").rglob("*") if (ROOT / "observability").exists() else []) if p.is_file() and ("alert" in p.name.lower() or "slo" in p.name.lower())]
    if not alert_files:
        warnings.append("Alert/SLO source files were not verified; observability evidence generates a gap/reference page only.")
        missing_enterprise_features.append("Alert rules and SLO metadata as committed source files.")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_by": GENERATED_BY,
        "source_files": source_files,
        "source_groups": {},
        "observability_components": [
            {"name": "Prometheus", "purpose": "Metrics scrape and storage", "verified_from_source": prometheus.exists()},
            {"name": "Grafana", "purpose": "Dashboards / visualization runtime", "verified_from_source": grafana_ini.exists() and obs_tasks.exists()},
            {"name": "Loki", "purpose": "Log storage and query backend", "verified_from_source": loki.exists()},
            {"name": "Promtail", "purpose": "PM2 log scrape and Loki push agent", "verified_from_source": promtail.exists()},
            {"name": "Gatus", "purpose": "Health aggregation dashboard / health engine", "verified_from_source": gatus.exists()},
            {"name": "Caddy", "purpose": "Reverse proxy routes for API, Loki-compatible logs, Gatus, and UI", "verified_from_source": caddy_template.exists()},
            {"name": "FastAPI Loki-compatible routes", "purpose": "Control API exposes Loki query-compatible endpoints", "verified_from_source": any("loki" in r["route"] for r in routes)},
            {"name": "React observability UI", "purpose": "Log Explorer, Security Posture, and NOC/System Status consumers", "verified_from_source": bool(frontend_consumers())},
        ],
        "ports": ports,
        "routes": caddy_routes(caddy_template, caddy_vars),
        "prometheus_jobs": scrape_jobs_from_prometheus(prometheus),
        "prometheus": {
            "port": ports.get("prometheus", {}).get("port"),
            "scrape_interval": re.search(r"scrape_interval:\s*([^\n]+)", read_text(prometheus)).group(1).strip() if prometheus.exists() and re.search(r"scrape_interval:\s*([^\n]+)", read_text(prometheus)) else "",
            "evaluation_interval": re.search(r"evaluation_interval:\s*([^\n]+)", read_text(prometheus)).group(1).strip() if prometheus.exists() and re.search(r"evaluation_interval:\s*([^\n]+)", read_text(prometheus)) else "",
            "source_file": rel(prometheus) if prometheus.exists() else "",
            "fastapi_metrics_endpoint_verified": has_fastapi_metrics_endpoint(routes),
        },
        "loki_pipeline": loki_pipeline(loki, promtail, caddy_template),
        "promtail_scrape_configs": loki_pipeline(loki, promtail, caddy_template).get("promtail", {}).get("scrape_configs", []),
        "gatus_endpoints": gatus_endpoints_from_template(gatus),
        "gatus": {
            "port": ports.get("gatus", {}).get("port"),
            "health_engine_integration": "control_plane_core.fetch_gatus_statuses()" if (ROOT / "pocket-lab-final-structure/runtime/core/control_plane_core.py").exists() and "fetch_gatus_statuses" in read_text(ROOT / "pocket-lab-final-structure/runtime/core/control_plane_core.py") else "not verified",
            "fallback_behavior": "FastAPI can return fallback health data when Gatus is unreachable" if (ROOT / "pocket-lab-final-structure/runtime/core/control_plane_core.py").exists() and "fallback" in read_text(ROOT / "pocket-lab-final-structure/runtime/core/control_plane_core.py") else "not verified",
            "source_file": rel(gatus) if gatus.exists() else "",
        },
        "grafana_config": grafana,
        "grafana_provisioning_paths": {
            "dashboards": grafana.get("dashboard_provisioning_dirs", []),
            "datasources": grafana.get("datasource_provisioning_dirs", []),
        },
        "fastapi_observability_routes": routes,
        "frontend_observability_consumers": frontend_consumers(),
        "bootstrap_observability_scripts": bootstrap_scripts(source_files),
        "runtime_contract_links": runtime_contracts,
        "alerting_slo_sources": alert_files,
        "warnings": warnings,
        "missing_enterprise_features": missing_enterprise_features,
    }
    groups: dict[str, list[str]] = {}
    for rec in source_files:
        groups.setdefault(rec["kind"], []).append(rec["path"])
    manifest["source_groups"] = {k: sorted(v) for k, v in sorted(groups.items())}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {rel(OUT)}")
    print(
        "Observed components="
        + str(len(manifest["observability_components"]))
        + " ports="
        + str(len(ports))
        + " gatus_endpoints="
        + str(len(manifest["gatus_endpoints"]))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
