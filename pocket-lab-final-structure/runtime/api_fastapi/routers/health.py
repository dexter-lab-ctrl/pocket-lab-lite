from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps
from ..services.live_status import LIVE_STATUS
from ..services.nats_bus import BUS

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/healthz")
def health() -> dict:
    engine = deps.core.build_health_engine_snapshot()
    summary = engine.get("summary", {})
    return {
        "status": engine.get("status", "unknown"),
        "service": deps.settings().server_name,
        "healthy": summary.get("healthy", 0),
        "warning": summary.get("warning", 0),
        "degraded": summary.get("degraded", 0),
        "unhealthy": summary.get("unhealthy", 0),
        "unavailable": summary.get("unavailable", 0),
        "maintenance": summary.get("maintenance", 0),
        "unknown": summary.get("unknown", 0),
        "total": summary.get("total", 0),
        "services": engine.get("services", {}),
        "health_engine": engine,
        "time": deps.now_utc_iso(),
    }


@router.get("/ready")
def ready() -> tuple[dict, int] | dict:
    engine = deps.core.build_health_engine_snapshot()
    bus = BUS.status()
    ready_state = (
        bool(deps.settings().iac_dir.exists())
        and engine.get("status") not in {"unhealthy"}
        and bool(bus.get("connected"))
        and bool(bus.get("jetstream_enabled"))
    )
    payload = {
        "status": "ready" if ready_state else "degraded",
        "vault": True,
        "gitops_repo": deps.settings().iac_dir.exists(),
        "health_engine": engine.get("status"),
        "health_engine_source": engine.get("source"),
        "health_engine_summary": engine.get("summary", {}),
        "health_engine_services": engine.get("services", {}),
        "live_status": LIVE_STATUS.status(),
        "nats": bus,
    }
    if ready_state:
        return payload
    from fastapi.responses import JSONResponse

    return JSONResponse(payload, status_code=503)


@router.get("/api/health-engine.json")
async def health_engine(request: Request) -> dict:
    deps.require_auth(request)
    return await LIVE_STATUS.sample_health(source="api-read")


@router.post("/api/health/check", status_code=202)
async def health_check(request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.action_queue import submit_domain_command

    return await submit_domain_command(
        "pocketlab.commands.health.check",
        "health.check.requested",
        {},
    )
