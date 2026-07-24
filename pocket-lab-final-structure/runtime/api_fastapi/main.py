from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging
import os
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .services.runtime_diagnostics import RuntimeTimingMiddleware
from .services.request_limits import LiteRequestSizeLimitMiddleware
from .services.lite_security_maintenance import LiteMaintenanceModeMiddleware
from .services.lite_safe_read_headers import LiteSafeReadNonceMiddleware
from .services.workload_admission import WorkloadAdmissionError

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
    from .services.nats_bus import BUS
    from .services.operation_events import install_operation_event_publisher
    from .services.live_status import LIVE_STATUS
    from .services import lite_security
    from .services import lite_database_recovery
    from .services.lite_control_plane_store import CONTROL_PLANE
    from .services.runtime_diagnostics import RUNTIME_DIAGNOSTICS
    from .services.workload_admission import WORKLOAD_ADMISSION

    diagnostics_started = False
    admission_started = False
    security_retention_task: asyncio.Task[None] | None = None
    device_health_sweep_task: asyncio.Task[None] | None = None
    try:
        try:
            diagnostics_started = await RUNTIME_DIAGNOSTICS.start()
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "pocketlab.runtime.diagnostics_start_degraded error_type=%s",
                type(exc).__name__,
            )
        deps.settings().ensure_dirs()
        await asyncio.to_thread(lite_database_recovery.startup_recovery_guard, "api")
        await asyncio.to_thread(CONTROL_PLANE.initialize)
        admission_started = await WORKLOAD_ADMISSION.start()
        await WORKLOAD_ADMISSION.run(
            "security.runtime.initialize",
            lite_security.initialize_security_sqlite_runtime,
        )
        lite_security.start_security_projection_runtime()
        security_retention_task = asyncio.create_task(
            lite_security.security_progress_retention_loop(),
            name="pocketlab-security-progress-retention",
        )
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
        try:
            warmup = lite.schedule_control_plane_projection_warmup()
            logging.getLogger(__name__).info(
                "pocketlab.control_projection.warmup_scheduled apps=%s recovery_summary=%s recovery_details=%s",
                warmup.get("apps"),
                warmup.get("recovery_summary"),
                warmup.get("recovery_details"),
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "pocketlab.control_projection.warmup_degraded error_type=%s",
                type(exc).__name__,
            )
        device_health_sweep_task = asyncio.create_task(
            lite.device_health_projection_sweep_loop(),
            name="pocketlab-device-health-projection-sweep",
        )
        if os.environ.get("POCKETLAB_DISABLE_RELEASE_UPDATER", "").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            deps.ensure_release_updater()
        yield
    finally:
        await LIVE_STATUS.stop()
        if device_health_sweep_task is not None:
            device_health_sweep_task.cancel()
            try:
                await device_health_sweep_task
            except asyncio.CancelledError:
                pass
        if security_retention_task is not None:
            security_retention_task.cancel()
            try:
                await security_retention_task
            except asyncio.CancelledError:
                pass
        try:
            await WORKLOAD_ADMISSION.run(
                "security.projection.stop",
                lite_security.stop_security_projection_runtime,
                admission_timeout_seconds=1.0,
                deadline_seconds=5.0,
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "pocketlab.runtime.projection_stop_degraded error_type=%s",
                type(exc).__name__,
            )
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
        await asyncio.to_thread(CONTROL_PLANE.shutdown)
        if admission_started or WORKLOAD_ADMISSION.snapshot().get("status") == "running":
            await WORKLOAD_ADMISSION.shutdown()
        if diagnostics_started:
            await RUNTIME_DIAGNOSTICS.stop()


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
    expose_headers=["ETag", "X-PocketLab-Read-Nonce"],
)
app.add_middleware(LiteRequestSizeLimitMiddleware)
app.add_middleware(LiteMaintenanceModeMiddleware)
app.add_middleware(RuntimeTimingMiddleware)
app.add_middleware(LiteSafeReadNonceMiddleware)

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


@app.exception_handler(WorkloadAdmissionError)
async def workload_admission_exception_handler(
    request: Request, exc: WorkloadAdmissionError
):
    try:
        from .services.nats_bus import BUS

        await asyncio.wait_for(
            BUS.publish_json(
                "pocketlab.audit.control.rejected",
                "control.rejected",
                {
                    "operation": exc.operation_id[:80],
                    "outcome": "rejected",
                    "reason": exc.reason[:64],
                    "retryable": bool(exc.retryable),
                    "capacity_class": exc.admission_class.value[:48],
                    "captured_at": deps.now_utc_iso(),
                    "sanitized": True,
                },
            ),
            timeout=0.5,
        )
    except Exception as audit_exc:
        logging.getLogger(__name__).warning(
            "pocketlab.admission.audit_degraded operation=%s error_type=%s",
            exc.operation_id[:80],
            type(audit_exc).__name__,
        )
    return JSONResponse(
        {
            "status": "busy",
            "accepted": False,
            "reason": exc.reason,
            "retryable": exc.retryable,
            "operation": exc.operation_id,
            "admission_class": exc.admission_class.value,
            "message": exc.safe_message,
            "sanitized": True,
        },
        status_code=503,
        headers={"Retry-After": "2"},
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
