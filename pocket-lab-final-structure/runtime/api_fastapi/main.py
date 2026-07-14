from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import deps
from .routers import (
    catalog,
    drift,
    events,
    fleet,
    gitops,
    health,
    lite,
    observability,
    operations,
    release,
    runbooks,
    security,
    settings,
    telemetry,
    websocket,
    workflows,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    deps.settings().ensure_dirs()
    from .services.nats_bus import BUS
    from .services.operation_events import install_operation_event_publisher
    from .services.live_status import LIVE_STATUS
    from .services import lite_security

    await asyncio.to_thread(lite_security.initialize_security_sqlite_runtime)
    lite_security.start_security_projection_runtime()
    await BUS.start()
    await BUS.start_watchdog()
    install_operation_event_publisher(
        deps.operation_service(), asyncio.get_running_loop(), source="fastapi"
    )
    await BUS.publish_json(
        "pocketlab.events.api.started",
        "api.started",
        {"service": deps.settings().server_name},
    )
    await LIVE_STATUS.start()
    if os.environ.get("POCKETLAB_DISABLE_RELEASE_UPDATER", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        deps.ensure_release_updater()
    try:
        yield
    finally:
        await LIVE_STATUS.stop()
        await asyncio.to_thread(lite_security.stop_security_projection_runtime)
        try:
            await BUS.publish_json(
                "pocketlab.events.api.stopped",
                "api.stopped",
                {"service": deps.settings().server_name},
            )
        except Exception:
            # Shutdown evidence is best effort. A transient NATS disconnect must
            # not turn graceful FastAPI shutdown into a crash/restart loop.
            pass
        await BUS.stop()


app = FastAPI(
    title="Pocket Lab FastAPI/NATS Control API",
    version="2.4.0-tier13",
    description=(
        "Authoritative FastAPI/NATS control plane for the Pocket Lab React PWA. "
        "Tier 13 serves existing /api contracts, publishes command/event traffic over NATS/JetStream, keeps event-sourced workflows, and adds bounded runtime observability health status through FastAPI."
    ),
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "POCKETLAB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router,
    lite.router,
    observability.router,
    telemetry.router,
    catalog.router,
    fleet.router,
    gitops.router,
    release.router,
    drift.router,
    security.router,
    settings.router,
    operations.router,
    runbooks.router,
    events.router,
    websocket.router,
    workflows.router,
):
    app.include_router(router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    payload = detail if isinstance(detail, dict) else {"error": str(detail)}
    return JSONResponse(
        payload, status_code=exc.status_code, headers=getattr(exc, "headers", None)
    )


@app.get("/api")
def api_index() -> dict:
    return {
        "service": "Pocket Lab FastAPI/NATS Control API",
        "version": "2.4.0-tier13",
        "mode": "fastapi+nats-event-bus+domain-worker-actions+live-operation-logs+release-orchestration+event-native-health-telemetry+nats-fleet-agents+jetstream-durability+event-sourced-workflows",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "events": "/api/events/status",
        "workers": "/api/workers/status",
        "reliability": "/api/reliability/status",
        "workflows": "/api/workflows/status",
        "observability_status": "/api/observability/status",
        "lite_status": "/api/lite/status",
    }
