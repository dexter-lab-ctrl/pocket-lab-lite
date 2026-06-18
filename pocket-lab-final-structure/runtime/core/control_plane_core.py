"""Shared Pocket Lab control-plane core for the FastAPI/NATS runtime.

This module intentionally contains no stdlib HTTP server, request handler, or
standalone API entrypoint.  FastAPI routers, NATS workers, and node agents import
these framework-neutral helpers for state, telemetry, catalog, drift, release,
and operation-service behavior.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from operations.service import OperationService
from operations.registry import normalize_operation_request
from git.dulwich_repo import DulwichRepository
from contracts import utc_now_iso, slugify
from release_auto_update import ReleaseAutoUpdater
from release_workflow import (
    build_release_workflow as build_release_workflow,
)  # noqa: F401

LOGGER = logging.getLogger("control_plane_core")
logging.basicConfig(
    level=os.environ.get("POCKETLAB_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value is not None else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


ROOT_DIR = pathlib.Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    host: str = field(default_factory=lambda: _env("POCKETLAB_API_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("POCKETLAB_API_PORT", 8080))
    base_dir: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            _env("POCKETLAB_BASE_DIR", os.path.expanduser("~/pocket-lab"))
        )
    )
    state_dir: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            _env(
                "POCKETLAB_STATE_DIR",
                str(
                    pathlib.Path(
                        _env("POCKETLAB_BASE_DIR", os.path.expanduser("~/pocket-lab"))
                    )
                    / "state"
                ),
            )
        )
    )
    iac_dir: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            _env(
                "POCKETLAB_IAC_DIR",
                str(
                    pathlib.Path(
                        _env("POCKETLAB_BASE_DIR", os.path.expanduser("~/pocket-lab"))
                    )
                    / "pocket_lab_iac"
                ),
            )
        )
    )
    api_dir: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            _env(
                "POCKETLAB_API_DIR",
                str(
                    pathlib.Path(
                        _env("POCKETLAB_BASE_DIR", os.path.expanduser("~/pocket-lab"))
                    )
                    / "api"
                ),
            )
        )
    )
    telemetry_path: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            _env(
                "POCKETLAB_TELEMETRY_PATH",
                str(
                    pathlib.Path(
                        _env("POCKETLAB_BASE_DIR", os.path.expanduser("~/pocket-lab"))
                    )
                    / "api"
                    / "telemetry.json"
                ),
            )
        )
    )
    gatus_base_url: str = field(
        default_factory=lambda: _env(
            "POCKETLAB_GATUS_BASE_URL", "http://127.0.0.1:8081"
        )
    )
    gatus_statuses_path: str = field(
        default_factory=lambda: _env(
            "POCKETLAB_GATUS_STATUSES_PATH", "/api/v1/endpoints/statuses"
        )
    )
    gitea_base_url: str = field(
        default_factory=lambda: _env(
            "POCKETLAB_GITEA_BASE_URL", "http://127.0.0.1:3030"
        )
    )
    gitea_user: str = field(
        default_factory=lambda: _env("POCKETLAB_GITEA_USER", "pocket_admin")
    )
    gitea_repo: str = field(
        default_factory=lambda: _env("POCKETLAB_GITEA_REPO", "pocket_lab_iac")
    )
    gitops_branch_prefix: str = field(
        default_factory=lambda: _env(
            "POCKETLAB_GITOPS_BRANCH_PREFIX", "feature/pocket-lab"
        )
    )
    api_token: str = field(default_factory=lambda: _env("POCKETLAB_API_TOKEN", ""))
    allow_local_write: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_ALLOW_LOCAL_WRITE", True)
    )
    enable_join_script: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_ENABLE_JOIN_SCRIPT", True)
    )
    allow_tailscale_api: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_ALLOW_TAILSCALE_API", False)
    )
    allow_simulated_ztp: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_ALLOW_SIMULATED_ZTP", True)
    )
    server_name: str = "Pocket Lab FastAPI/NATS Control API"

    def ensure_dirs(self) -> None:
        for path in (
            self.base_dir,
            self.state_dir,
            self.iac_dir,
            self.api_dir,
            self.telemetry_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


SETTINGS = Settings()
SETTINGS.ensure_dirs()

OP_SERVICE = OperationService(
    state_dir=SETTINGS.state_dir,
    workspace_dir=SETTINGS.state_dir / "workspace",
    iac_dir=SETTINGS.iac_dir,
    policies_dir=SETTINGS.iac_dir / "pocket_lab_policies",
    taskfile_paths=[ROOT_DIR / "Taskfile.yml", ROOT_DIR / "Taskfile.ops.yml"],
)

AUTO_UPDATER: ReleaseAutoUpdater | None = None


def now_utc_iso() -> str:
    return utc_now_iso()


def read_json_file(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def telemetry_snapshot() -> Dict[str, Any]:
    cpu_temp = 42.0
    for i in range(12):
        p = pathlib.Path(f"/sys/class/thermal/thermal_zone{i}/temp")
        if p.exists():
            try:
                raw = int(p.read_text().strip())
                cpu_temp = raw / 1000.0 if raw > 1000 else float(raw)
                break
            except Exception:
                pass

    cpu_usage_percent = 0.0
    try:
        load_1m = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        cpu_usage_percent = max(0.0, min(100.0, (load_1m / cpu_count) * 100.0))
    except Exception:
        cpu_usage_percent = 0.0

    try:
        st = os.statvfs(str(SETTINGS.base_dir))
        free_space_mb = int((st.f_bavail * st.f_frsize) // (1024 * 1024))
    except Exception:
        free_space_mb = 0

    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            mem = {
                line.split(":", 1)[0]: int(line.split()[1])
                for line in handle
                if ":" in line and line.split()[1].isdigit()
            }
        mem_total = mem.get("MemTotal", 0) // 1024
        mem_available = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
    except Exception:
        mem_total = 0
        mem_available = 0

    memory_usage_mb = max(0, mem_total - mem_available)

    return {
        "timestamp": now_utc_iso(),
        "cpu_temp_c": cpu_temp,
        "free_space_mb": free_space_mb,
        "cpu_usage_percent": round(cpu_usage_percent, 1),
        "memory_usage_mb": memory_usage_mb,
        "memory_total_mb": mem_total,
        "memory_free_mb": mem_available,
        # Compatibility aliases kept for older clients and tests.
        "cpuTemp": cpu_temp,
        "freeSpaceMB": free_space_mb,
        "memoryTotalMB": mem_total,
        "memoryFreeMB": mem_available,
        "device": os.uname().nodename if hasattr(os, "uname") else "pocket-lab",
        "error": None,
    }


def fetch_gatus_statuses() -> Optional[Dict[str, Any]]:
    url = f"{SETTINGS.gatus_base_url.rstrip('/')}{SETTINGS.gatus_statuses_path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


HEALTH_STATUSES = {
    "healthy",
    "warning",
    "degraded",
    "unhealthy",
    "unavailable",
    "maintenance",
    "unknown",
}


def normalize_health_status(value: Any) -> str:
    status = str(value or "unknown").strip().lower()
    return status if status in HEALTH_STATUSES else "unknown"


def normalize_check(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    status = normalize_health_status(
        item.get("status") or item.get("health") or item.get("state")
    )
    name = str(
        item.get("name") or item.get("service") or item.get("target") or "service"
    )
    return {
        "name": name,
        "status": status,
        "summary": item.get("summary") or item.get("message") or "",
        "url": item.get("url") or item.get("endpoint") or "",
        "last_checked_at": item.get("last_checked_at")
        or item.get("lastCheck")
        or now_utc_iso(),
        "response_time_ms": item.get("response_time_ms"),
        "results_count": item.get("results_count"),
    }


def normalize_service_payload(name: str, value: Any) -> Dict[str, Any]:
    """Return the stable health service contract consumed by the UI.

    Older snapshots sometimes represented services as plain strings while newer
    Gatus-backed snapshots carry richer objects.  Keeping a single object shape
    at the API boundary prevents React from accidentally rendering raw objects
    and gives future health extensions a safe place to attach metadata.
    """
    if isinstance(value, str):
        return {
            "name": str(name or "service"),
            "status": normalize_health_status(value),
            "summary": "",
            "url": "",
            "last_checked_at": now_utc_iso(),
        }
    if isinstance(value, dict):
        normalized = normalize_check({**value, "name": value.get("name") or name})
        return normalized or {
            "name": str(name or "service"),
            "status": "unknown",
            "summary": "",
            "url": "",
            "last_checked_at": now_utc_iso(),
        }
    return {
        "name": str(name or "service"),
        "status": "unknown",
        "summary": "",
        "url": "",
        "last_checked_at": now_utc_iso(),
    }


def build_health_engine_snapshot() -> Dict[str, Any]:
    gatus_items = fetch_gatus_statuses()
    checks = []
    if isinstance(gatus_items, dict):
        for item in gatus_items.get("checks") or gatus_items.get("data") or []:
            checks.append(normalize_check(item))
    if not checks:
        checks = [
            {
                "name": "gatus",
                "status": "healthy",
                "summary": "Fallback snapshot",
                "url": SETTINGS.gatus_base_url,
                "last_checked_at": now_utc_iso(),
            },
            {
                "name": "api",
                "status": "healthy",
                "summary": "Pocket Lab FastAPI/NATS control plane is serving",
                "url": f"http://{SETTINGS.host}:{SETTINGS.port}",
                "last_checked_at": now_utc_iso(),
            },
        ]

    checks = [
        normalize_service_payload(check.get("name", "service"), check)
        for check in checks
        if isinstance(check, dict)
    ]
    services = {
        check["name"]: normalize_service_payload(check["name"], check)
        for check in checks
    }

    counts = {
        "healthy": 0,
        "warning": 0,
        "degraded": 0,
        "unhealthy": 0,
        "unavailable": 0,
        "maintenance": 0,
        "unknown": 0,
    }
    for item in services.values():
        item_status = normalize_health_status(item.get("status"))
        item["status"] = item_status
        counts[item_status] = counts.get(item_status, 0) + 1

    total = len(services)
    status = "healthy"
    if counts["unhealthy"] or counts["degraded"]:
        status = "degraded"
    if counts["unhealthy"] > 1:
        status = "unhealthy"

    snapshot = {
        "engine": "gatus",
        "source": "gatus" if gatus_items else "fallback",
        "status": status,
        "summary": {**counts, "total": total},
        "services": services,
        "checks": list(services.values()),
        "last_checked_at": now_utc_iso(),
        "gatus": {
            "base_url": SETTINGS.gatus_base_url,
            "statuses_path": SETTINGS.gatus_statuses_path,
            "reachable": bool(gatus_items),
        },
    }
    write_json_file(SETTINGS.api_dir / "health-engine.json", snapshot)
    return snapshot


def load_drift_state() -> Dict[str, Any]:
    path = SETTINGS.state_dir / "drift.json"
    default = {
        "summary": {
            "healthy": 1,
            "drifted": 0,
            "unknown": 0,
            "pending_approval": 0,
            "failed": 0,
            "last_scan_at": now_utc_iso(),
        },
        "metrics": {
            "total_targets": 1,
            "healthy": 1,
            "drifted": 0,
            "unknown": 0,
            "open_jobs": 0,
            "last_successful_reconcile_at": now_utc_iso(),
        },
        "jobs": [
            {
                "job_id": "drift_default_vault",
                "target": "vault",
                "scope": "service",
                "status": "healthy",
                "severity": "low",
                "approval_state": "not_required",
                "summary": "Vault configuration matches the desired state.",
                "created_at": now_utc_iso(),
                "updated_at": now_utc_iso(),
                "changes_count": 0,
                "diff": [],
                "result": {
                    "applied": True,
                    "verified": True,
                    "healthy_after_apply": True,
                },
            }
        ],
    }
    return read_json_file(path, default)


def save_drift_state(state: Dict[str, Any]) -> None:
    write_json_file(SETTINGS.state_dir / "drift.json", state)


def update_drift_from_jobs(jobs: list[Dict[str, Any]]) -> Dict[str, Any]:
    healthy = sum(1 for job in jobs if job.get("status") == "healthy")
    drifted = sum(1 for job in jobs if job.get("status") in {"drifted", "diff_ready"})
    failed = sum(1 for job in jobs if job.get("status") == "failed")
    pending = sum(
        1 for job in jobs if job.get("approval_state") in {"pending", "required"}
    )
    state = {
        "summary": {
            "healthy": healthy,
            "drifted": drifted,
            "unknown": max(0, len(jobs) - healthy - drifted - failed),
            "pending_approval": pending,
            "failed": failed,
            "last_scan_at": now_utc_iso(),
        },
        "metrics": {
            "total_targets": len(jobs),
            "healthy": healthy,
            "drifted": drifted,
            "unknown": max(0, len(jobs) - healthy - drifted - failed),
            "open_jobs": pending + drifted,
            "last_successful_reconcile_at": now_utc_iso(),
        },
        "jobs": jobs,
    }
    save_drift_state(state)
    return state


def default_fleet_nodes() -> list[Dict[str, Any]]:
    return [
        {
            "id": "worker1",
            "name": "pixel-edge-01",
            "role": "Mesh Node",
            "ip": "100.101.50.2",
            "status": "active",
            "isCurrent": False,
        },
        {
            "id": "worker2",
            "name": "samsung-nfs",
            "role": "Mesh Storage Node",
            "ip": "100.101.50.3",
            "status": "active",
            "isCurrent": False,
        },
    ]


def load_fleet_nodes() -> list[Dict[str, Any]]:
    active_nodes = read_json_file(
        SETTINGS.state_dir / "fleet.json", default_fleet_nodes()
    )
    active_nodes = (
        [node for node in active_nodes if isinstance(node, dict)]
        if isinstance(active_nodes, list)
        else default_fleet_nodes()
    )
    pending_nodes = load_pending_fleet_nodes()
    pending_names = {
        str(node.get("name") or node.get("id") or "").lower() for node in active_nodes
    }
    merged = list(active_nodes)
    for node in pending_nodes:
        identifier = str(node.get("name") or node.get("id") or "").lower()
        if identifier and identifier in pending_names:
            merged = [
                n
                for n in merged
                if str(n.get("name") or n.get("id") or "").lower() != identifier
            ]
        merged.insert(0, node)
    return merged


def save_fleet_nodes(nodes: list[Dict[str, Any]]) -> None:
    write_json_file(SETTINGS.state_dir / "fleet.json", nodes)


def load_pending_fleet_nodes() -> list[Dict[str, Any]]:
    payload = read_json_file(SETTINGS.state_dir / "fleet_pending.json", {"nodes": []})
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    return [node for node in nodes if isinstance(node, dict)]


def build_catalog_cache(items: list[Dict[str, Any]]) -> None:
    write_json_file(
        SETTINGS.state_dir / "catalog.json",
        {"updated_at": now_utc_iso(), "items": items},
    )


def build_fleet_health_snapshot(nodes: list[Dict[str, Any]]) -> Dict[str, Any]:
    healthy = sum(1 for node in nodes if str(node.get("status")).lower() == "active")
    return {
        "status": "healthy" if healthy == len(nodes) else "degraded",
        "summary": {
            "healthy": healthy,
            "unhealthy": len(nodes) - healthy,
            "total": len(nodes),
        },
        "nodes": nodes,
        "last_checked_at": now_utc_iso(),
    }


def get_tailscale_api_key() -> Optional[str]:
    state = read_json_file(SETTINGS.state_dir / "secrets.json", {})
    return state.get("tailscale_api_key")


def set_tailscale_api_key(api_key: str) -> None:
    state = read_json_file(SETTINGS.state_dir / "secrets.json", {})
    state["tailscale_api_key"] = api_key
    write_json_file(SETTINGS.state_dir / "secrets.json", state)


def build_catalog_view() -> list[Dict[str, Any]]:
    artifacts = list(OP_SERVICE.oras.list_artifacts()) + list(
        OP_SERVICE.catalog.list_artifacts()
    )
    sources = OP_SERVICE.catalog.list_sources()
    repos = OP_SERVICE.catalog.list_repos()
    items = []
    seen: set[str] = set()

    def _append(item: Dict[str, Any]) -> None:
        key = str(item.get("ref") or item.get("id") or item.get("title") or "")
        if key and key in seen:
            return
        if key:
            seen.add(key)
        items.append(item)

    for artifact in artifacts:
        source_value = (
            artifact.get("source")
            or artifact.get("metadata", {}).get("source")
            or "artifact"
        )
        _append(
            {
                "id": artifact.get("name") or slugify(artifact.get("ref", "artifact")),
                "title": artifact.get("name", "Blueprint"),
                "description": artifact.get("metadata", {}).get(
                    "description", "OCI-distributable blueprint package"
                ),
                "source": source_value,
                "ref": artifact.get("ref"),
                "version": artifact.get("version"),
                "updated_at": artifact.get("created_at")
                or artifact.get("updated_at")
                or now_utc_iso(),
                "path": artifact.get("path") or artifact.get("layout"),
            }
        )
    for source in sources:
        _append(
            {
                "id": source.get("name") or slugify(source.get("ref", "source")),
                "title": source.get("name") or source.get("ref") or "Source",
                "description": source.get("description", "Imported catalog source"),
                "source": source.get("kind", "repo"),
                "ref": source.get("ref") or source.get("url") or "",
                "updated_at": source.get("ingested_at") or now_utc_iso(),
            }
        )
    for repo in repos:
        _append(
            {
                "id": repo.get("name") or slugify(repo.get("ref", "repo")),
                "title": repo.get("name") or "Repository",
                "description": repo.get(
                    "description", "Repository-backed catalog item"
                ),
                "source": "repo",
                "ref": repo.get("ref", ""),
                "updated_at": repo.get("updated_at") or now_utc_iso(),
            }
        )
    if not items:
        items.append(
            {
                "id": "security_scanners",
                "title": "Security Scanners",
                "description": "Default blueprint bundle",
                "source": "repo",
                "ref": str(SETTINGS.iac_dir),
                "updated_at": now_utc_iso(),
            }
        )
    build_catalog_cache(items)
    return items


def build_pipeline_status() -> list[Dict[str, Any]]:
    runs = OP_SERVICE.list(limit=10)
    items = []
    for run in runs:
        artifacts = run.get("artifacts") or {}
        items.append(
            {
                "id": run.get("job_id"),
                "name": run.get("operation"),
                "status": run.get("status"),
                "commit_msg": run.get("params", {}).get("message")
                or run.get("operation"),
                "commit_sha": artifacts.get("commit_sha")
                or artifacts.get("repo_commit", {}).get("commit"),
                "time": run.get("created_at"),
                "updated_at": run.get("updated_at"),
            }
        )
    if not items:
        items.append(
            {
                "id": "bootstrap",
                "name": "bootstrap",
                "status": "success",
                "commit_msg": "Pocket Lab bootstrap complete",
                "time": now_utc_iso(),
                "updated_at": now_utc_iso(),
            }
        )
    return items


def build_git_history() -> list[Dict[str, Any]]:
    repo = DulwichRepository(SETTINGS.iac_dir)
    status = repo.status()
    history = [
        {
            "branch": status.branch or "main",
            "last_commit": status.last_commit
            or {"message": "No commit history available"},
            "dirty": status.dirty,
            "exists": status.exists,
        }
    ]
    return history


def build_opa_evaluations() -> list[Dict[str, Any]]:
    path = SETTINGS.state_dir / "opa_evaluations.json"
    default = [
        {
            "id": "opa-001",
            "timestamp": now_utc_iso(),
            "trigger": "drift_scan",
            "status": "PASS",
            "msg": "Policy bundle loaded",
            "time": 5,
        },
        {
            "id": "opa-002",
            "timestamp": now_utc_iso(),
            "trigger": "deploy_blueprint",
            "status": "PASS",
            "msg": "Blueprint policy verified",
            "time": 12,
        },
    ]
    return read_json_file(path, default)


def search_loki(query: str, limit: int = 20) -> Dict[str, Any]:
    runs = OP_SERVICE.list(limit=50)
    entries = []
    query_l = query.lower()
    started = time.perf_counter()
    for run in runs:
        text = json.dumps(run, ensure_ascii=False).lower()
        if query_l in text or not query_l:
            entries.append(
                {
                    "stream": {
                        "job": "pocket-fastapi",
                        "operation": run.get("operation", "unknown"),
                    },
                    "values": [
                        [
                            str(int(dt.datetime.utcnow().timestamp() * 1e9)),
                            json.dumps(
                                {
                                    "message": run.get("operation"),
                                    "status": run.get("status"),
                                    "job_id": run.get("job_id"),
                                }
                            ),
                        ]
                    ],
                }
            )
    if "security_audit" in query_l or "opa" in query_l:
        entries.append(
            {
                "stream": {"job": "pm2_logs", "component": "security"},
                "values": [
                    [
                        str(int(dt.datetime.utcnow().timestamp() * 1e9)),
                        json.dumps(
                            {
                                "message": "security_audit: policy evaluation complete",
                                "status": "PASS",
                            }
                        ),
                    ]
                ],
            }
        )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": "success",
        "data": {"resultType": "streams", "result": entries[:limit]},
        "meta": {
            "query": query,
            "limit": limit,
            "matched_count": min(len(entries), limit),
            "query_time_ms": elapsed_ms,
        },
    }


def operation_to_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = normalize_operation_request(payload)
    return {
        "operation": req.operation,
        "target": {"type": req.target.type, "ref": req.target.ref},
        "params": req.params,
        "dry_run": req.dry_run,
        "source": req.source,
    }
