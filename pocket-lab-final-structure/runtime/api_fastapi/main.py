from __future__ import annotations

from contextlib import asynccontextmanager
import contextlib
import asyncio
import logging
import os
from typing import AsyncIterator

# The API owns prepared reads and durable dirty admission. The worker is the
# normal projection executor unless an operator explicitly selects otherwise.
os.environ.setdefault("POCKETLAB_PROCESS_ROLE", "api")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from .services.runtime_diagnostics import RuntimeTimingMiddleware
from .services.request_limits import LiteRequestSizeLimitMiddleware
from .services.lite_security_maintenance import LiteMaintenanceModeMiddleware
from .services.lite_safe_read_headers import LiteSafeReadNonceMiddleware
from .services.workload_admission import WorkloadAdmissionError
from .openapi_contracts import harden_openapi_schema

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
    from .services import fleet_registry
    from .services.lite_control_plane_store import CONTROL_PLANE
    from .services.runtime_diagnostics import RUNTIME_DIAGNOSTICS
    from .services.workload_admission import WORKLOAD_ADMISSION
    from .services.projection_scheduler import PROJECTION_SCHEDULER
    from .services.idle_efficiency import IDLE_EFFICIENCY

    diagnostics_started = False
    idle_governor_started = False
    admission_started = False
    security_retention_task: asyncio.Task[None] | None = None
    startup_workloads_task: asyncio.Task[None] | None = None
    gc_compaction_task: asyncio.Task[None] | None = None
    try:
        IDLE_EFFICIENCY.configure_process()
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
        idle_governor_started = await IDLE_EFFICIENCY.start()
        admission_started = await WORKLOAD_ADMISSION.start()
        await asyncio.to_thread(PROJECTION_SCHEDULER.start)
        await asyncio.to_thread(fleet_registry.resume_pending_lifecycle_exports)
        await WORKLOAD_ADMISSION.run(
            "security.runtime.initialize",
            lite_security.initialize_security_sqlite_runtime,
        )
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
        startup_workloads_task = asyncio.create_task(
            lite.run_staged_startup_workloads(lite_security),
            name="pocketlab-staged-startup-workloads",
        )

        async def _compact_gc_after_startup() -> None:
            try:
                delay = max(
                    15.0,
                    min(
                        300.0,
                        float(
                            os.environ.get(
                                "POCKETLAB_GC_COMPACTION_DELAY_SECONDS", "60"
                            )
                        ),
                    ),
                )
            except (TypeError, ValueError):
                delay = 60.0
            await asyncio.sleep(delay)
            result = await asyncio.to_thread(
                RUNTIME_DIAGNOSTICS.compact_and_tune_gc
            )
            logging.getLogger(__name__).info(
                "pocketlab.runtime.gc_compaction changed=%s frozen_objects=%s",
                bool(result.get("changed")),
                int(result.get("frozen_objects") or 0),
            )

        gc_compaction_task = asyncio.create_task(
            _compact_gc_after_startup(),
            name="pocketlab-gc-compaction",
        )
        yield
    finally:
        await LIVE_STATUS.stop()
        if gc_compaction_task is not None:
            gc_compaction_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await gc_compaction_task
        if startup_workloads_task is not None:
            startup_workloads_task.cancel()
            try:
                await startup_workloads_task
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
        await asyncio.to_thread(PROJECTION_SCHEDULER.shutdown)
        await asyncio.to_thread(CONTROL_PLANE.shutdown)
        if admission_started or WORKLOAD_ADMISSION.snapshot().get("status") == "running":
            await WORKLOAD_ADMISSION.shutdown()
        if idle_governor_started or IDLE_EFFICIENCY.snapshot().get("running"):
            await IDLE_EFFICIENCY.stop()
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


def _pocketlab_openapi() -> dict:
    if app.openapi_schema is not None:
        return app.openapi_schema
    generated = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = harden_openapi_schema(generated)
    return app.openapi_schema


app.openapi = _pocketlab_openapi


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
