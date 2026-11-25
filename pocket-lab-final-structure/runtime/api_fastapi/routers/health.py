from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import deps
from ..services import lite_phase3b_projections as phase3b
from ..services.live_status import LIVE_STATUS
from ..services.nats_bus import BUS

router = APIRouter(tags=["health"])


def _prepared_health() -> dict:
    """Read the worker-owned native health projection without collecting."""
    try:
        snapshot = phase3b.snapshot("system.health", ensure_schema=False)
    except Exception:
        snapshot = None
    if isinstance(snapshot, dict):
        return snapshot
    return {
        "engine": "lite-native",
        "source": "prepared-lite-native",
        "status": "starting",
        "summary": "Native health projection is not available yet.",
        "components": {"api": "healthy"},
        "services": {},
        "status_counts": {"starting": 1},
        "prepared": False,
        "sanitized": True,
    }


def _status_counts(engine: dict) -> dict[str, int]:
    counts = engine.get("status_counts")
    if isinstance(counts, dict):
        return {str(key): max(0, int(value or 0)) for key, value in counts.items()}
    counts = {}
    services = engine.get("services")
    if isinstance(services, dict):
        for value in services.values():
            status = str(value.get("status") if isinstance(value, dict) else value or "unknown")
            counts[status] = counts.get(status, 0) + 1
    return counts


def _ready_from_prepared(engine: dict) -> bool:
    """Evaluate only required local-owner evidence; remote access is optional."""
    if engine.get("prepared") is False:
        return False
    components = engine.get("components") if isinstance(engine.get("components"), dict) else {}
    identity = str(components.get("identity") or "unknown").lower()
    nats = str(components.get("nats") or "unknown").lower()
    worker = str(components.get("worker") or "unknown").lower()
    sqlite = str(components.get("sqlite") or "unknown").lower()
    storage = str(components.get("storage") or "unknown").lower()
    identity_ready = identity in {"healthy", "ready", "not_configured"}
    required_ready = {"healthy", "ready"}
    return (
        identity_ready
        and nats in required_ready
        and worker in required_ready
        and sqlite in required_ready
        and storage not in {"unavailable", "unhealthy", "critical", "read_only", "unknown"}
    )


@router.get("/health")
@router.get("/healthz")
def health() -> dict:
    engine = _prepared_health()
    counts = _status_counts(engine)
    return {
        # Liveness describes the serving API process.  Control-plane status is
        # returned separately so an unready projection never makes liveness
        # falsely claim that FastAPI is down.
        "status": "healthy",
        "control_plane_status": engine.get("status", "unknown"),
        "service": deps.settings().server_name,
        "healthy": counts.get("healthy", 0),
        "warning": counts.get("warning", 0),
        "degraded": counts.get("degraded", 0),
        "unhealthy": counts.get("unhealthy", 0),
        "unavailable": counts.get("unavailable", 0),
        "maintenance": counts.get("maintenance", 0),
        "unknown": counts.get("unknown", 0),
        "total": sum(counts.values()),
        "services": engine.get("services", {}),
        "health_engine": engine,
        "source": "api-process",
        "time": deps.now_utc_iso(),
    }


@router.get("/ready")
def ready() -> dict:
    engine = _prepared_health()
    bus = BUS.status()
    ready_state = _ready_from_prepared(engine)
    payload = {
        "status": "ready" if ready_state else engine.get("status", "degraded"),
        "ready": ready_state,
        "health_engine": engine.get("status"),
        "health_engine_source": engine.get("source"),
        "health_engine_summary": engine.get("summary", ""),
        "health_engine_services": engine.get("services", {}),
        "health_engine_snapshot": engine,
        "identity": engine.get("identity", {}),
        "worker": engine.get("worker", {}),
        "live_status": LIVE_STATUS.status(),
        "nats": bus,
        "optional_capabilities": {
            "remote_access": (engine.get("components") or {}).get("remote_access", "unknown"),
            "secondary_device": (engine.get("nats") or {}).get("secondary_status", "not_configured"),
        },
        "observation": {
            "source": "prepared-lite-native",
            "updated_at": engine.get("updated_at"),
            "freshness": "prepared" if engine.get("prepared", True) else "missing",
        },
    }
    if ready_state:
        return payload
    return JSONResponse(payload, status_code=503)


@router.get("/api/health-engine.json")
async def health_engine(request: Request) -> dict:
    deps.require_auth(request)
    # This endpoint is a compatibility read of the prepared projection.  A
    # GET must not start a collector, probe retired services, or write state.
    return _prepared_health()


@router.post("/api/health/check", status_code=202)
async def health_check(request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.action_queue import submit_domain_command

    return await submit_domain_command(
        "pocketlab.commands.health.check",
        "health.check.requested",
        {},
    )
