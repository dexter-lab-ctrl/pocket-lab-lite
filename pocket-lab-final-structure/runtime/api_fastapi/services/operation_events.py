from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from .nats_bus import BUS

SENSITIVE_KEYS = {
    "api_key",
    "token",
    "password",
    "secret",
    "value",
    "authorization",
    "x-pocket-lab-token",
}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): ("***" if str(k).lower() in SENSITIVE_KEYS else _sanitize(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def operation_log_subject(level: str | None = None) -> str:
    normalized = str(level or "info").lower()
    if normalized in {"error", "failed", "fatal"}:
        return "pocketlab.events.operation.log.error"
    if normalized in {"warning", "warn"}:
        return "pocketlab.events.operation.log.warning"
    return "pocketlab.events.operation.log"


def make_operation_event_publisher(
    loop: Optional[asyncio.AbstractEventLoop] = None, *, source: str = "runtime"
):
    """Return a sync callback that republishes runner events to the event bus.

    OperationService is intentionally synchronous and compatibility-preserving. This
    bridge lets FastAPI and worker processes attach a callback that can be called
    safely from either the main event loop or a worker thread. The actual bus
    publish is scheduled back onto the supplied asyncio loop.
    """
    target_loop = loop

    def publish(payload: Dict[str, Any]) -> None:
        data = _sanitize(dict(payload or {}))
        data.setdefault("source", source)
        subject = operation_log_subject(str(data.get("level") or "info"))
        trace_id = str(data.get("job_id") or data.get("trace_id") or "") or None

        async def _publish() -> None:
            await BUS.publish_json(subject, "operation.log", data, trace_id=trace_id)

        nonlocal target_loop
        try:
            running_loop = asyncio.get_running_loop()
            if target_loop is None:
                target_loop = running_loop
            running_loop.create_task(_publish())
            return
        except RuntimeError:
            pass

        if target_loop and target_loop.is_running():
            asyncio.run_coroutine_threadsafe(_publish(), target_loop)

    return publish


def install_operation_event_publisher(
    operation_service: Any,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    *,
    source: str = "runtime",
) -> None:
    if hasattr(operation_service, "set_event_publisher"):
        operation_service.set_event_publisher(
            make_operation_event_publisher(loop, source=source)
        )
