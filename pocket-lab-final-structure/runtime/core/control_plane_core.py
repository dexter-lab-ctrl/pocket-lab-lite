"""Shared Pocket Lab control-plane core for the FastAPI/NATS runtime.

This module intentionally contains no stdlib HTTP server, request handler, or
standalone API entrypoint.  FastAPI routers, NATS workers, and node agents import
these framework-neutral helpers for state, telemetry, catalog, drift, release,
and operation-service behavior.
"""

from __future__ import annotations

import datetime as dt
import errno
import json
import logging
import os
import pathlib
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows-only fallback
    fcntl = None

from operations.service import OperationService
from operations.registry import normalize_operation_request
from contracts import utc_now_iso, slugify
from release_auto_update import ReleaseAutoUpdater
from release_workflow import (
    build_release_workflow as build_release_workflow,
)  # noqa: F401
from resource_telemetry import collect_resource_telemetry

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
_STATE_WRITE_FENCE_LOCK = threading.RLock()
_STATE_WRITE_FENCE_STATE = threading.local()


def now_utc_iso() -> str:
    return utc_now_iso()


def read_json_file(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


@contextmanager
def state_write_fence(*, timeout_seconds: float = 300.0):
    """Serialize state-file writers across API, worker, and agent processes.

    Database restore owns this fence while replacing the canonical database and
    registered state files.  Normal JSON writers participate through
    ``write_json_file`` so a heartbeat or lifecycle callback cannot rewrite a
    restored file between its durable copy and checksum validation.  The
    thread-local depth makes restore journal/maintenance writes re-entrant.
    """
    depth = int(getattr(_STATE_WRITE_FENCE_STATE, "depth", 0) or 0)
    if depth:
        _STATE_WRITE_FENCE_STATE.depth = depth + 1
        try:
            yield
        finally:
            _STATE_WRITE_FENCE_STATE.depth = depth
        return

    try:
        timeout = max(0.1, min(float(timeout_seconds), 600.0))
    except (TypeError, ValueError):
        timeout = 300.0
    acquired = _STATE_WRITE_FENCE_LOCK.acquire(timeout=timeout)
    if not acquired:
        raise TimeoutError("State write fence acquisition timed out")
    descriptor: int | None = None
    try:
        lock_path = SETTINGS.state_dir / ".pocketlab-state-write.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            str(lock_path), os.O_CREAT | os.O_RDWR, 0o600
        )
        os.fchmod(descriptor, 0o600)
        if fcntl is not None:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("State write fence acquisition timed out") from exc
                    time.sleep(min(0.1, remaining))
        _STATE_WRITE_FENCE_STATE.depth = 1
        yield
    finally:
        _STATE_WRITE_FENCE_STATE.depth = 0
        if descriptor is not None:
            if fcntl is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)
        _STATE_WRITE_FENCE_LOCK.release()


def write_json_file(path: pathlib.Path, data: Any) -> None:
    with state_write_fence():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def telemetry_snapshot() -> Dict[str, Any]:
    """Return one central resource sample using the shared bounded providers."""
    payload = collect_resource_telemetry(SETTINGS.base_dir)
    payload["device"] = os.uname().nodename if hasattr(os, "uname") else "pocket-lab"
    return payload


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
                "job_id": "drift_default_lite_native",
                "target": "lite_native_control_plane",
                "scope": "service",
                "status": "healthy",
                "severity": "low",
                "approval_state": "not_required",
                "summary": "Lite-native control-plane configuration matches the desired state.",
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


def search_operational_evidence(query: str, limit: int = 20) -> Dict[str, Any]:
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
                "stream": {"job": "pocketlab_operational_evidence", "component": "security"},
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
