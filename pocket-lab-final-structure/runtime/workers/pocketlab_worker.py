#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Keep the worker runnable directly from Termux/PM2 without installing Pocket Lab
# as a package.
RUNTIME_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = RUNTIME_DIR.parent
for path in (
    str(RUNTIME_DIR),
    str(RUNTIME_DIR / "core"),
    str(RUNTIME_DIR / "api_fastapi"),
):
    if path not in sys.path:
        sys.path.insert(0, path)

# The worker is the normal prepared-projection executor. API processes only
# admit durable dirty signals unless an operator explicitly changes ownership.
os.environ.setdefault("POCKETLAB_PROCESS_ROLE", "worker")

# The worker uses JetStream durable command consumption and publishes lifecycle
# events. It does not need FastAPI's read-side event fanout subscription; leaving
# it enabled requires broader subscribe permissions and can destabilize command
# recovery when NATS permissions are intentionally tight.
os.environ.setdefault("POCKETLAB_NATS_EVENT_FANOUT", "0")

from api_fastapi import deps  # type: ignore  # noqa: E402
from api_fastapi.services.nats_bus import BUS  # type: ignore  # noqa: E402
from api_fastapi.services.operation_events import install_operation_event_publisher  # type: ignore  # noqa: E402

WORKER_NAME = os.environ.get("POCKETLAB_WORKER_NAME", f"pocketlab-worker-{os.getpid()}")
COMMAND_SUBJECT = os.environ.get(
    "POCKETLAB_WORKER_COMMAND_SUBJECT", "pocketlab.commands.>"
)
COMMAND_QUEUE = os.environ.get("POCKETLAB_WORKER_QUEUE", "pocketlab_command_worker_v1")
HEARTBEAT_SECONDS = int(os.environ.get("POCKETLAB_WORKER_HEARTBEAT_SECONDS", "30"))
DURABLE_NAME = os.environ.get("POCKETLAB_WORKER_DURABLE", "pocketlab_command_worker_v1")


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _worker_log(event: str, **data: Any) -> None:
    safe = {
        key: value
        for key, value in data.items()
        if key not in {"api_key", "token", "password", "secret"}
    }
    print(
        json.dumps(
            {"event": event, "worker": WORKER_NAME, **safe},
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )


def _decode_message(data: bytes) -> Dict[str, Any]:
    payload = json.loads(data.decode("utf-8"))
    # BUS.publish_json wraps command data in an event envelope. Allow raw command
    # JSON too so tests and future CLI tools can publish direct command payloads.
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        data_obj = dict(payload["data"])
        data_obj.setdefault(
            "_envelope", {k: v for k, v in payload.items() if k != "data"}
        )
        return data_obj
    if isinstance(payload, dict):
        return payload
    raise ValueError("NATS command payload must be a JSON object")


def _subject_from(command: Dict[str, Any], msg: Any | None = None) -> str:
    msg_subject = str(getattr(msg, "subject", "") or "")
    if msg_subject:
        return msg_subject
    env = command.get("_envelope") or {}
    return str(env.get("subject") or command.get("subject") or "")


async def publish(
    subject: str, event_type: str, data: Dict[str, Any], *, trace_id: str | None = None
) -> None:
    safe = {
        k: v
        for k, v in data.items()
        if k not in {"api_key", "token", "password", "secret"}
    }
    await BUS.publish_json(
        subject, event_type, {"worker": WORKER_NAME, **safe}, trace_id=trace_id
    )


async def connect_worker_bus(stop_event: asyncio.Event) -> None:
    """Keep the worker process alive while NATS is temporarily unavailable.

    PM2 should not need to restart the worker just because the Android device
    slept, NATS restarted, or 127.0.0.1:4222 refused a connection during boot.
    The worker remains idle and retries until JetStream is reachable again.
    """
    delay = int(os.environ.get("POCKETLAB_WORKER_NATS_RETRY_SECONDS", "3"))
    while not stop_event.is_set():
        try:
            await BUS.start()
            await BUS.start_watchdog()
            install_operation_event_publisher(
                deps.operation_service(), asyncio.get_running_loop(), source=WORKER_NAME
            )
            await BUS.subscribe_durable(
                COMMAND_SUBJECT,
                command_callback,
                durable=DURABLE_NAME,
            )
            _worker_log(
                "worker.consumer_ready",
                durable=DURABLE_NAME,
                subject=COMMAND_SUBJECT,
                generation=(
                    BUS.durable_consumer_status(DURABLE_NAME).get("generation")
                    or 0
                ),
            )
            await publish(
                "pocketlab.events.worker.started",
                "worker.started",
                {
                    "command_subject": COMMAND_SUBJECT,
                    "queue": COMMAND_QUEUE,
                    "durable": DURABLE_NAME,
                    "pid": os.getpid(),
                    "restart_safe": True,
                },
            )
            return
        except Exception as exc:
            print(f"Pocket Lab worker waiting for NATS: {exc}", file=sys.stderr)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue


async def worker_recovery_watchdog(stop_event: asyncio.Event) -> None:
    interval = _env_int(
        "POCKETLAB_WORKER_RECOVERY_SECONDS", 10, minimum=2, maximum=300
    )
    stale_seconds = _env_int(
        "POCKETLAB_LITE_SECURITY_ACCEPTED_STALE_SECONDS",
        120,
        minimum=30,
        maximum=3600,
    )
    grace_seconds = _env_int(
        "POCKETLAB_WORKER_ACCEPTED_RECOVERY_GRACE_SECONDS",
        15,
        minimum=2,
        maximum=60,
    )
    while not stop_event.is_set():
        try:
            recovered = await BUS.recover_durable_consumers()
            for durable in recovered:
                status = BUS.durable_consumer_status(durable)
                _worker_log(
                    "worker.consumer_recovered",
                    durable=durable,
                    generation=status.get("generation"),
                    recoveries=status.get("recoveries"),
                )
                with contextlib.suppress(Exception):
                    await publish(
                        "pocketlab.audit.worker.consumer_recovered",
                        "worker.consumer_recovered",
                        {
                            "durable": durable,
                            "generation": status.get("generation"),
                            "recoveries": status.get("recoveries"),
                            "sanitized": True,
                        },
                    )

            status = BUS.durable_consumer_status(DURABLE_NAME)
            if status.get("healthy") and not status.get("callback_inflight"):
                from api_fastapi.services import lite_security  # type: ignore

                stale = await asyncio.to_thread(
                    lite_security.stale_accepted_runs,
                    stale_seconds=stale_seconds,
                )
                if stale:
                    await BUS.ensure_durable_consumer(
                        DURABLE_NAME, force=True
                    )
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=grace_seconds
                        )
                    except asyncio.TimeoutError:
                        pass
                    if stop_event.is_set():
                        break
                    recovered_status = BUS.durable_consumer_status(DURABLE_NAME)
                    released = await asyncio.to_thread(
                        lite_security.recover_stale_accepted_runs,
                        stale_seconds=stale_seconds,
                        callback_inflight=bool(
                            recovered_status.get("callback_inflight")
                        ),
                        recovery_attempted=True,
                        expected_candidates=stale,
                        consumer_generation=int(
                            recovered_status.get("generation") or 0
                        ),
                        recovery_count=int(
                            recovered_status.get("recoveries") or 0
                        ),
                    )
                    for item in released:
                        _worker_log(
                            "worker.accepted_run_released",
                            run_id=item.get("run_id"),
                            failure_code=item.get("failure_code"),
                        )
                        with contextlib.suppress(Exception):
                            await publish(
                                "pocketlab.audit.lite.security.scan.recovered",
                                "lite.security.scan.recovered",
                                {
                                    "run_id": item.get("run_id"),
                                    "status": "failed",
                                    "failure_code": item.get("failure_code"),
                                    "summary": "A safety check that could not start was released for retry.",
                                    "sanitized": True,
                                },
                                trace_id=str(item.get("run_id") or "") or None,
                            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _worker_log(
                "worker.recovery_check_failed", error_type=type(exc).__name__
            )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def execute_operation_command(command: Dict[str, Any]) -> None:
    job_id = str(command.get("job_id") or "").strip()
    operation = str(command.get("operation") or "").strip()
    trace_id = str(command.get("trace_id") or command.get("job_id") or "") or None

    if not job_id:
        # Support externally published operation commands by creating the queued
        # run in the worker before executing it.
        request = deps.normalize_operation_request(
            {
                "operation": operation,
                "target": command.get("target") or {},
                "params": command.get("params") or {},
                "dry_run": bool(command.get("dry_run", False)),
            }
        )
        submitted = deps.operation_service().submit_queued(request)
        job_id = submitted["job_id"]
        operation = submitted.get("operation") or operation

    await publish(
        "pocketlab.events.operation.worker_claimed",
        "operation.worker_claimed",
        {"job_id": job_id, "operation": operation},
        trace_id=trace_id,
    )
    try:
        install_operation_event_publisher(
            deps.operation_service(), asyncio.get_running_loop(), source=WORKER_NAME
        )
        result = await asyncio.to_thread(deps.operation_service().run_existing, job_id)
        status = str(result.get("status") or "unknown")
        subject = (
            "pocketlab.events.operation.succeeded"
            if status == "succeeded"
            else "pocketlab.events.operation.failed"
        )
        event_type = (
            "operation.succeeded" if status == "succeeded" else "operation.failed"
        )
        await publish(
            subject,
            event_type,
            {
                "job_id": job_id,
                "operation": result.get("operation") or operation,
                "status": status,
                "exit_code": result.get("exit_code"),
                "error": result.get("error"),
                "artifacts": result.get("artifacts") or {},
            },
            trace_id=trace_id,
        )
    except Exception as exc:
        await publish(
            "pocketlab.events.operation.failed",
            "operation.failed",
            {
                "job_id": job_id,
                "operation": operation,
                "status": "failed",
                "error": str(exc),
            },
            trace_id=trace_id,
        )
        raise


async def execute_domain_command(subject: str, command: Dict[str, Any]) -> None:
    from api_fastapi.services.domain_commands import (
        execute_domain_command as run_domain_command,
    )  # type: ignore

    trace_id = str(command.get("trace_id") or command.get("command_id") or "") or None
    command_id = str(command.get("command_id") or trace_id or "")
    await publish(
        "pocketlab.events.command.worker_claimed",
        "command.worker_claimed",
        {"command_id": command_id, "command_subject": subject},
        trace_id=trace_id,
    )
    await publish(
        "pocketlab.events.command.running",
        "command.running",
        {"command_id": command_id, "command_subject": subject},
        trace_id=trace_id,
    )
    try:
        result = await run_domain_command(subject, command)
        result_status = str(result.get("status") or "success").strip().lower()
        if result_status in {"failed", "error", "degraded"}:
            await publish(
                "pocketlab.events.command.failed",
                "command.failed",
                {
                    "command_id": command_id,
                    "command_subject": subject,
                    "status": result_status,
                    "error_type": str(
                        result.get("failure_code")
                        or result.get("last_failure_code")
                        or "DomainCommandFailed"
                    )[:80],
                    "last_known_good": bool(result.get("last_known_good")),
                    "terminal": True,
                    "sanitized": True,
                },
                trace_id=trace_id,
            )
        elif result_status in {"deferred", "waiting"}:
            await publish(
                "pocketlab.events.command.deferred",
                "command.deferred",
                {
                    "command_id": command_id,
                    "command_subject": subject,
                    "status": result_status,
                    "retry_after_seconds": max(
                        0, int(result.get("retry_after_seconds") or 0)
                    ),
                    "terminal": True,
                    "sanitized": True,
                },
                trace_id=trace_id,
            )
        else:
            await publish(
                "pocketlab.events.command.succeeded",
                "command.succeeded",
                {
                    "command_id": command_id,
                    "command_subject": subject,
                    "status": result_status,
                    "terminal": True,
                },
                trace_id=trace_id,
            )
    except Exception as exc:
        await publish(
            "pocketlab.events.command.failed",
            "command.failed",
            {
                "command_id": command_id,
                "command_subject": subject,
                "error_type": type(exc).__name__,
                "terminal": False,
            },
            trace_id=trace_id,
        )
        raise


def _command_lifecycle_payload(
    command: Dict[str, Any], subject: str, command_id: str, attempt: int
) -> Dict[str, Any]:
    return {
        "command_id": command_id,
        "command_subject": subject,
        "attempt": max(1, int(attempt or 1)),
        "run_id": str(command.get("run_id") or "")[:120],
        "app_id": str(command.get("app_id") or "")[:120],
        "node_id": str(command.get("node_id") or command.get("device_id") or "")[:120],
        "sanitized": True,
    }


async def command_callback(msg: Any) -> None:
    subject = str(getattr(msg, "subject", "") or "")
    attempt = BUS.delivery_attempt(msg)
    command: Dict[str, Any] = {}
    generic_lifecycle = False
    try:
        command = _decode_message(msg.data)
        subject = subject or _subject_from(command, msg)
        command_id = str(
            command.get("command_id")
            or command.get("job_id")
            or command.get("run_id")
            or ""
        )
        _worker_log(
            "worker.command_received",
            subject=subject,
            command_id=command_id,
            attempt=attempt,
        )
        from api_fastapi.services import lite_security_maintenance  # type: ignore

        if not lite_security_maintenance.worker_command_allowed(subject):
            await publish(
                "pocketlab.events.worker.maintenance_deferred",
                "worker.maintenance_deferred",
                {
                    "command_subject": subject,
                    "command_id": command_id,
                    "retry_delay_seconds": 5,
                    "sanitized": True,
                },
                trace_id=command_id or None,
            )
            await BUS.nak_message(msg, delay=5)
            _worker_log(
                "worker.command_maintenance_deferred",
                subject=subject,
                command_id=command_id,
                attempt=attempt,
            )
            return
        if subject == "pocketlab.commands.lite.security.scan":
            from api_fastapi.services import lite_security  # type: ignore

            run_id = str(command.get("run_id") or command_id)
            if run_id:
                await asyncio.to_thread(
                    lite_security.mark_command_received,
                    run_id,
                    delivery_attempt=attempt,
                    published_at=str(command.get("command_published_at") or "") or None,
                )
            if run_id and await asyncio.to_thread(
                lite_security.security_run_is_terminal, run_id
            ):
                await publish(
                    "pocketlab.events.worker.ignored",
                    "worker.ignored",
                    {
                        "command_subject": subject,
                        "command_id": command_id,
                        "run_id": run_id,
                        "reason": "security run is already terminal",
                        "attempt": attempt,
                    },
                    trace_id=command_id or None,
                )
                await BUS.ack_message(msg)
                _worker_log(
                    "worker.command_ignored",
                    subject=subject,
                    command_id=command_id,
                    reason="terminal_security_run",
                )
                return
        if subject.startswith("pocketlab.commands.node."):
            # Node-scoped fleet commands are consumed by NATS-backed device agents.
            # A JetStream worker durable consumer may still see them because it uses
            # the broad command stream; ack this consumer copy so it does not redeliver.
            await publish(
                "pocketlab.events.worker.ignored",
                "worker.ignored",
                {
                    "command_subject": subject,
                    "reason": "node-scoped commands are handled by fleet agents",
                    "attempt": attempt,
                },
            )
            await BUS.ack_message(msg)
            return
        lifecycle_payload = _command_lifecycle_payload(
            command, subject, command_id, attempt
        )
        await publish(
            "pocketlab.events.command.received",
            "command.received",
            lifecycle_payload,
            trace_id=command_id or None,
        )
        generic_lifecycle = subject in {
            "pocketlab.commands.runbook.execute",
            "pocketlab.commands.runbook.approve",
            "pocketlab.commands.runbook.reject",
            "pocketlab.commands.operation.execute",
        }
        if generic_lifecycle:
            await publish(
                "pocketlab.events.command.worker_claimed",
                "command.worker_claimed",
                lifecycle_payload,
                trace_id=command_id or None,
            )
            await publish(
                "pocketlab.events.command.running",
                "command.running",
                lifecycle_payload,
                trace_id=command_id or None,
            )
        if subject == "pocketlab.commands.runbook.execute":
            from api_fastapi.services.runbook_commands import execute_runbook_command  # type: ignore

            await execute_runbook_command(command, publish)
        elif subject == "pocketlab.commands.runbook.approve":
            from api_fastapi.services.runbook_commands import approve_runbook_command  # type: ignore

            await approve_runbook_command(command, publish)
        elif subject == "pocketlab.commands.runbook.reject":
            from api_fastapi.services.runbook_commands import reject_runbook_command  # type: ignore

            await reject_runbook_command(command, publish)
        elif subject == "pocketlab.commands.operation.execute":
            await execute_operation_command(command)
        elif subject.startswith("pocketlab.commands."):
            # Domain commands may carry an ``operation`` field for lifecycle context.
            # Route by subject first so Lite app/media commands are handled by their
            # domain handlers instead of the generic operation runner.
            await execute_domain_command(subject, command)
        elif str(command.get("operation") or ""):
            await execute_operation_command(command)
        else:
            await execute_domain_command(subject, command)
        if generic_lifecycle:
            await publish(
                "pocketlab.events.command.succeeded",
                "command.succeeded",
                {**lifecycle_payload, "terminal": True},
                trace_id=command_id or None,
            )
        await BUS.ack_message(msg)
        _worker_log(
            "worker.command_acked",
            subject=subject,
            command_id=str(
                command.get("command_id")
                or command.get("job_id")
                or command.get("run_id")
                or ""
            ),
            attempt=attempt,
        )
    except Exception as exc:
        error = str(exc)
        from api_fastapi.services import reliability  # type: ignore

        job_id = str(command.get("job_id") or "") if isinstance(command, dict) else ""
        terminal_failure = attempt >= reliability.max_deliver()
        if generic_lifecycle:
            await publish(
                "pocketlab.events.command.failed",
                "command.failed",
                {
                    **_command_lifecycle_payload(command, subject, str(
                        command.get("command_id")
                        or command.get("job_id")
                        or command.get("run_id")
                        or ""
                    ), attempt),
                    "terminal": terminal_failure,
                    "error_type": type(exc).__name__,
                },
                trace_id=str(
                    command.get("command_id")
                    or command.get("job_id")
                    or command.get("run_id")
                    or ""
                ) or None,
            )
        if terminal_failure:
            if job_id:
                reliability.mark_operation_dead_letter(
                    job_id, attempt=attempt, error=error
                )
            await BUS.dead_letter(
                original_subject=subject or getattr(msg, "subject", COMMAND_SUBJECT),
                command=command,
                error=error,
                attempt=attempt,
            )
            await BUS.term_message(msg)
            await publish(
                "pocketlab.events.worker.error",
                "worker.error",
                {
                    "subject": subject or getattr(msg, "subject", COMMAND_SUBJECT),
                    "error": error,
                    "attempt": attempt,
                    "dead_lettered": True,
                },
            )
            return
        if job_id:
            reliability.mark_operation_retrying(job_id, attempt=attempt, error=error)
        delay = reliability.retry_delay_seconds(attempt)
        await publish(
            "pocketlab.events.command.retry_scheduled",
            "command.retry_scheduled",
            {
                "subject": subject or getattr(msg, "subject", COMMAND_SUBJECT),
                "error": error,
                "attempt": attempt,
                "retry_delay_seconds": delay,
                "job_id": job_id,
            },
        )
        await BUS.nak_message(msg, delay=delay)
        _worker_log(
            "worker.command_retry_scheduled",
            subject=subject,
            command_id=str(
                command.get("command_id")
                or command.get("job_id")
                or command.get("run_id")
                or ""
            ),
            attempt=attempt,
            retry_delay_seconds=delay,
            error_type=type(exc).__name__,
        )


async def release_scheduler_loop(stop_event: asyncio.Event) -> None:
    """Worker-owned automatic release checks with bounded backoff and jitter."""
    from api_fastapi.services import release_runtime  # type: ignore

    await asyncio.to_thread(release_runtime.initialize_release_runtime)
    if str(os.environ.get("POCKETLAB_DISABLE_RELEASE_UPDATER", "")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        _worker_log(
            "worker.release_scheduler_disabled",
            execution_owner="pocket-worker/release-subprocess",
        )
        await stop_event.wait()
        return

    poll_seconds = _env_int(
        "POCKETLAB_RELEASE_POLL_SECONDS", 180, minimum=30, maximum=86400
    )
    initial_delay = _env_int(
        "POCKETLAB_RELEASE_INITIAL_DELAY_SECONDS", 45, minimum=5, maximum=3600
    )
    maximum_backoff = _env_int(
        "POCKETLAB_RELEASE_MAX_BACKOFF_SECONDS", 3600, minimum=60, maximum=86400
    )
    jitter_max = _env_int(
        "POCKETLAB_RELEASE_JITTER_SECONDS", 17, minimum=0, maximum=300
    )
    jitter = (
        int(__import__("hashlib").sha256(WORKER_NAME.encode("utf-8")).hexdigest()[:8], 16)
        % (jitter_max + 1)
        if jitter_max
        else 0
    )
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay + jitter)
        return
    except asyncio.TimeoutError:
        pass

    failure_count = 0
    while not stop_event.is_set():
        command_id = f"release-auto-{int(time.time())}-{os.getpid()}"
        delay = poll_seconds + jitter
        try:
            result = await release_runtime.run_release_check(
                command_id,
                source="automatic",
            )
            if result.get("status") == "degraded":
                failure_count += 1
                delay = min(maximum_backoff, poll_seconds * (2 ** min(failure_count, 5)))
                _worker_log(
                    "worker.release_check_degraded",
                    failure_code=result.get("last_failure_code"),
                    retry_seconds=delay,
                    last_known_good=bool(result.get("last_known_good")),
                )
                with contextlib.suppress(Exception):
                    await publish(
                        "pocketlab.events.release.check_degraded",
                        "release.check_degraded",
                        {
                            "failure_code": result.get("last_failure_code"),
                            "retry_after_seconds": delay,
                            "last_known_good": bool(result.get("last_known_good")),
                            "sanitized": True,
                        },
                        trace_id=command_id,
                    )
            elif result.get("coalesced"):
                delay = max(5, int(result.get("retry_after_seconds") or 5))
            else:
                failure_count = 0
                if result.get("changed") or result.get("update_available"):
                    with contextlib.suppress(Exception):
                        await publish(
                            "pocketlab.events.release.available"
                            if result.get("update_available")
                            else "pocketlab.events.release.current",
                            "release.available"
                            if result.get("update_available")
                            else "release.current",
                            {
                                "current_tag": result.get("current_tag"),
                                "latest_tag": result.get("latest_tag"),
                                "update_available": bool(result.get("update_available")),
                                "projection_revision": result.get("projection_revision"),
                                "automatic": True,
                                "sanitized": True,
                            },
                            trace_id=command_id,
                        )
                if result.get("update_available") and result.get("auto_apply"):
                    from api_fastapi.services.release_orchestrator import apply_release  # type: ignore

                    apply_result = await apply_release(
                        {
                            "command_id": f"{command_id}-apply",
                            "trace_id": command_id,
                            "force": False,
                            "source": "automatic",
                        }
                    )
                    if apply_result.get("status") != "success":
                        failure_count += 1
                        delay = min(
                            maximum_backoff,
                            poll_seconds * (2 ** min(failure_count, 5)),
                        )
            _worker_log(
                "worker.release_check_completed",
                status=result.get("status"),
                update_available=bool(result.get("update_available")),
                changed=bool(result.get("changed")),
                next_check_seconds=delay,
                execution_owner="pocket-worker/release-subprocess",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failure_count += 1
            delay = min(maximum_backoff, poll_seconds * (2 ** min(failure_count, 5)))
            _worker_log(
                "worker.release_scheduler_degraded",
                error_type=type(exc).__name__,
                retry_seconds=delay,
            )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            continue


async def heartbeat(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await publish(
                "pocketlab.events.worker.heartbeat",
                "worker.heartbeat",
                {
                    "command_subject": COMMAND_SUBJECT,
                    "queue": COMMAND_QUEUE,
                    "bus": BUS.status(),
                },
            )
        except Exception as exc:
            BUS.connected = False
            BUS.fallback_reason = str(exc)
            print(f"Pocket Lab worker heartbeat skipped: {exc}", file=sys.stderr)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_SECONDS)
        except asyncio.TimeoutError:
            continue


def _compact_distribution(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value.get(key)
        for key in ("count", "p50", "p95", "p99", "max")
        if value.get(key) is not None
    }


def _compact_adaptive_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    domains: dict[str, Any] = {}
    raw_domains = payload.get("domains") if isinstance(payload.get("domains"), dict) else {}
    for domain, row in raw_domains.items():
        if not isinstance(row, dict):
            continue
        domains[str(domain)[:96]] = {
            "cadence_state": row.get("cadence_state"),
            "load_state": row.get("load_state"),
            "next_reconciliation_seconds": row.get("next_reconciliation_seconds"),
            "cpu_budget_remaining_ms": row.get("cpu_budget_remaining_ms"),
            "cpu_budget_exhausted": bool(row.get("cpu_budget_exhausted")),
            "admitted": int(row.get("admitted") or 0),
            "deferred": int(row.get("deferred") or 0),
            "last_reason": str(row.get("last_reason") or "")[:80],
            "cpu_ms": _compact_distribution(row.get("cpu_ms")),
            "wall_ms": _compact_distribution(row.get("wall_ms")),
            "queue_wait_ms": _compact_distribution(row.get("queue_wait_ms")),
            "payload_bytes": _compact_distribution(row.get("payload_bytes")),
            "serialization_ms": _compact_distribution(row.get("serialization_ms")),
            "allocation_bytes": _compact_distribution(row.get("allocation_bytes")),
            "payload_budget_bytes": int(row.get("payload_budget_bytes") or 0),
            "allocation_budget_bytes": int(row.get("allocation_budget_bytes") or 0),
            "serialization_budget_ms": float(row.get("serialization_budget_ms") or 0.0),
        }
    return {
        "profile": payload.get("profile"),
        "admitted": int(payload.get("admitted") or 0),
        "deferred": int(payload.get("deferred") or 0),
        "rejected": int(payload.get("rejected") or 0),
        "event_payloads": payload.get("event_payloads") if isinstance(payload.get("event_payloads"), dict) else {},
        "domains": domains,
        "sanitized": True,
    }


def _compact_process_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    workloads: dict[str, Any] = {}
    raw = payload.get("workloads") if isinstance(payload.get("workloads"), dict) else {}
    for name, row in raw.items():
        if not isinstance(row, dict):
            continue
        workloads[str(name)[:80]] = {
            key: int(row.get(key) or 0)
            for key in ("runs", "failed", "timed_out", "capacity_deferred",
                        "cleanup_degraded", "output_truncated", "active")
        }
    return {
        key: payload.get(key)
        for key in ("max_concurrent", "security_max_concurrent", "subprocess_count",
                    "subprocess_limit", "memory_rss_bytes", "memory_peak_rss_bytes",
                    "memory_metric_source")
    } | {"workloads": workloads, "sanitized": True}


def _compact_workflow_projection(payload: dict[str, Any]) -> dict[str, Any]:
    writer = payload.get("projection_writer") if isinstance(payload.get("projection_writer"), dict) else {}
    keys = (
        "process_alive", "process_pid", "process_generation", "started_at", "execution_owner",
        "process_restart_count", "restart_count", "recycle_count", "last_restart_reason",
        "queue_depth", "queue_capacity", "mailbox_capacity", "oldest_queue_age_ms",
        "accepted_events", "coalesced_events", "rejected_events", "dropped_events",
        "processed_events", "batch_count", "last_batch_size", "last_batch_wall_ms",
        "last_batch_cpu_ms", "last_batch_serialized_bytes", "last_batch_allocation_bytes",
        "serialization_ms", "serialized_bytes", "allocation_bytes",
        "canonical_noop_count", "canonical_change_count", "memory_pressure_deferred_count",
        "cpu_budget_deferred_count", "pressure_deferred_count", "last_error_type", "last_error_at", "last_success_at",
        "last_known_good_revision", "next_batch_due_ms", "stagger_ms", "degraded",
        "degraded_reason", "refresh_pending", "retry_after_ms", "dispatcher_alive",
        "dispatcher_restart_count", "dispatch_count", "last_dispatch_at",
        "last_dispatch_error_type",
    )
    return {key: writer.get(key) for key in keys} | {"sanitized": True}


def _compact_hot_path(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_count": int(payload.get("job_count") or 0),
        "top_cpu_jobs": (payload.get("top_cpu_jobs") or [])[:10]
        if isinstance(payload.get("top_cpu_jobs"), list) else [],
        "sanitized": True,
    }


def _compact_security_progress(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "refresher_running",
        "prepared_snapshot",
        "prepared_static_bytes",
        "projection_epoch",
        "domain_revision",
        "active_scan",
        "projection_age_ms",
        "read_failure_count",
        "refreshes",
        "refresh_failures",
        "prepared_hits",
        "prepared_misses",
    )
    return {
        **{key: payload.get(key) for key in keys if key in payload},
        "sanitized": True,
    }


def _compact_scheduler_snapshot(
    scheduler: dict[str, Any],
    *,
    mailbox: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the sanitized worker-owned scheduler snapshot."""

    queue = scheduler.get("queue") if isinstance(scheduler.get("queue"), dict) else {}
    queue_fields = (
        "executor_depth",
        "ready_executor_depth",
        "scheduled_future_depth",
        "followup_domains",
        "active_domains",
        "clean_entries_removed",
        "active_entries_removed",
        "stale_generation_entries_removed",
        "duplicate_entries_removed",
        "unregistered_entries_removed",
        "stale_entries_removed",
        "stale_flags_cleared",
        "orphaned_dirty_requeued",
    )
    compact_queue = {key: int(queue.get(key) or 0) for key in queue_fields}
    compact_queue["durable_pending"] = int(mailbox.get("pending") or 0)
    compact_queue["unregistered"] = int(mailbox.get("unregistered") or 0)

    compact_scheduler = {
        key: scheduler.get(key)
        for key in (
            "status",
            "registered_domains",
            "projection_execution_owner",
            "is_execution_owner",
            "process_role",
            "loaded_build_version",
            "process_start_generation",
        )
    }
    compact_scheduler.update(
        {
            "queued_domains": int(compact_queue["ready_executor_depth"]),
            "active_domains": int(compact_queue["active_domains"]),
            "queue": compact_queue,
            "mailbox": {
                "claimed": int(mailbox.get("claimed") or 0),
                "pending": int(mailbox.get("pending") or 0),
                "unregistered": int(mailbox.get("unregistered") or 0),
            },
            "sanitized": True,
        }
    )
    worker_health = {
        "registry_ready": int(scheduler.get("registered_domains") or 0) > 0,
        "queue": compact_queue,
        "mailbox": dict(compact_scheduler["mailbox"]),
        "loaded_build_version": scheduler.get("loaded_build_version"),
        "process_start_generation": scheduler.get("process_start_generation"),
        "sanitized": True,
    }
    return compact_scheduler, worker_health


async def projection_signal_loop(stop_event: asyncio.Event) -> None:
    """Execute prepared projections from the durable SQLite dirty mailbox.

    Registration is retried in-process so transient SQLite pressure or a bad
    projection contract cannot silently disable worker-owned projections while
    leaving the command consumer apparently healthy.
    """

    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE  # type: ignore
    from api_fastapi.services import lite_core_projections  # type: ignore
    from api_fastapi.services import lite_phase3b_projections  # type: ignore
    from api_fastapi.services import lite_phase3c_projections  # type: ignore
    from api_fastapi.services import lite_security  # type: ignore
    from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER  # type: ignore
    from api_fastapi.services.adaptive_runtime import ADAPTIVE_RUNTIME  # type: ignore
    from api_fastapi.services.hot_path_profiler import HOT_PATH_PROFILER  # type: ignore
    from api_fastapi.services.process_runtime import PROCESS_RUNTIME  # type: ignore
    from api_fastapi.services.runtime_snapshot_store import publish_worker_snapshot  # type: ignore
    from api_fastapi.services.workflow_engine import WORKFLOW_ENGINE  # type: ignore
    from api_fastapi.services import release_runtime  # type: ignore

    retry_seconds = _env_int(
        "POCKETLAB_WORKER_PROJECTION_RETRY_SECONDS",
        5,
        minimum=2,
        maximum=60,
    )
    attempt = 0

    while not stop_event.is_set():
        attempt += 1
        try:
            await asyncio.to_thread(CONTROL_PLANE.initialize)
            await asyncio.to_thread(lite_core_projections.register_jobs)
            await asyncio.to_thread(lite_phase3c_projections.register_jobs)
            await asyncio.to_thread(lite_phase3b_projections.schedule_startup_warmup)
            await asyncio.to_thread(PROJECTION_SCHEDULER.start)
            await asyncio.to_thread(lite_core_projections.schedule_startup_warmup)
            await asyncio.to_thread(lite_phase3c_projections.schedule_startup_warmup)

            registry = PROJECTION_SCHEDULER.diagnostics()
            registered = set((registry.get("domains") or {}).keys())
            required = set(lite_core_projections.CORE_PROJECTION_DOMAINS) | {
                "security.progress",
                "security.summary",
                "system.status",
                "system.health",
            }
            missing = sorted(required - registered)
            if missing:
                _worker_log(
                    "worker.projection_registry_incomplete",
                    attempt=attempt,
                    registered_count=len(registered),
                    missing_domains=missing,
                    retry_seconds=retry_seconds,
                )
                raise RuntimeError("projection_registry_incomplete")

            _worker_log(
                "worker.projection_registry_ready",
                attempt=attempt,
                registered_count=len(registered),
                missing_domains=[],
            )
            break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _worker_log(
                "worker.projection_initialization_degraded",
                attempt=attempt,
                error_type=type(exc).__name__,
                retry_seconds=retry_seconds,
            )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=retry_seconds)
            except asyncio.TimeoutError:
                continue

    last_signal_log: tuple[int, int, int] | None = None
    last_signal_log_at = 0.0
    last_error_type = ""
    last_error_log_at = 0.0
    consecutive_signal_failures = 0
    last_snapshot_at = 0.0
    snapshot_interval_seconds = _env_int(
        "POCKETLAB_WORKER_RUNTIME_SNAPSHOT_SECONDS", 5, minimum=2, maximum=60
    )
    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(
                PROJECTION_SCHEDULER.consume_dirty_signals, limit=32
            )
            claimed = int(result.get("claimed") or 0)
            pending = int(result.get("pending") or 0)
            unregistered = int(result.get("unregistered") or 0)
            signal_state = (claimed, pending, unregistered)
            now = time.monotonic()
            if (claimed > 0 or unregistered > 0) and (
                signal_state != last_signal_log or now - last_signal_log_at >= 30.0
            ):
                _worker_log(
                    "worker.projection_signals_claimed",
                    claimed=claimed,
                    pending=pending,
                    unregistered=unregistered,
                )
                last_signal_log = signal_state
                last_signal_log_at = now
            consecutive_signal_failures = 0
            if now - last_snapshot_at >= snapshot_interval_seconds:
                scheduler = PROJECTION_SCHEDULER.diagnostics()
                compact_scheduler, worker_health = _compact_scheduler_snapshot(
                    scheduler,
                    mailbox={
                        "claimed": claimed,
                        "pending": pending,
                        "unregistered": unregistered,
                    },
                )
                await asyncio.to_thread(
                    publish_worker_snapshot,
                    {
                        "captured_at": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ).isoformat().replace("+00:00", "Z"),
                        "worker": {
                            "registry_ready": True,
                            "registered_domain_count": int(scheduler.get("registered_domains") or 0),
                        },
                        "projection_scheduler": compact_scheduler,
                        "worker_health": worker_health,
                        "adaptive_runtime": _compact_adaptive_runtime(ADAPTIVE_RUNTIME.diagnostics()),
                        "process_runtime": _compact_process_runtime(PROCESS_RUNTIME.snapshot()),
                        "hot_path": _compact_hot_path(HOT_PATH_PROFILER.snapshot()),
                        "security_progress": _compact_security_progress(
                            lite_security.security_progress_runtime_diagnostics()
                        ),
                        "workflow_projection": _compact_workflow_projection(WORKFLOW_ENGINE.status()),
                        "release_runtime": release_runtime.release_runtime_diagnostics(),
                    },
                )
                last_snapshot_at = now
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            consecutive_signal_failures += 1
            error_type = type(exc).__name__
            now = time.monotonic()
            if error_type != last_error_type or now - last_error_log_at >= 30.0:
                _worker_log(
                    "worker.projection_signal_degraded",
                    error_type=error_type,
                    consecutive_failures=consecutive_signal_failures,
                    retry_seconds=1,
                )
                last_error_type = error_type
                last_error_log_at = now
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue


async def main_async() -> int:
    stop_event = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except Exception:
            pass

    from api_fastapi.services import lite_database_recovery  # type: ignore

    # Recover or block on any durable restore journal before this process can
    # execute a normal or one-shot writer command.
    await asyncio.to_thread(lite_database_recovery.startup_recovery_guard, "worker")

    # Workers require real NATS/JetStream for durable production execution.
    # POCKETLAB_WORKER_RUN_ONCE_JSON remains available only as an explicit
    # one-shot harness hook.
    if os.environ.get("POCKETLAB_WORKER_RUN_ONCE_JSON"):
        command = json.loads(os.environ["POCKETLAB_WORKER_RUN_ONCE_JSON"])
        await BUS.start()
        install_operation_event_publisher(
            deps.operation_service(), asyncio.get_running_loop(), source=WORKER_NAME
        )
        subject = str(command.get("subject") or "pocketlab.commands.operation.execute")
        if subject.startswith("pocketlab.commands.node."):
            await publish(
                "pocketlab.events.worker.ignored",
                "worker.ignored",
                {
                    "command_subject": subject,
                    "reason": "node-scoped commands are handled by fleet agents",
                },
            )
        elif subject == "pocketlab.commands.runbook.execute":
            from api_fastapi.services.runbook_commands import execute_runbook_command  # type: ignore

            await execute_runbook_command(command, publish)
        elif subject == "pocketlab.commands.runbook.approve":
            from api_fastapi.services.runbook_commands import approve_runbook_command  # type: ignore

            await approve_runbook_command(command, publish)
        elif subject == "pocketlab.commands.runbook.reject":
            from api_fastapi.services.runbook_commands import reject_runbook_command  # type: ignore

            await reject_runbook_command(command, publish)
        elif subject == "pocketlab.commands.operation.execute":
            await execute_operation_command(command)
        elif subject.startswith("pocketlab.commands."):
            await execute_domain_command(subject, command)
        elif command.get("operation"):
            await execute_operation_command(command)
        else:
            await execute_domain_command(subject, command)
        await BUS.stop()
        return 0

    projection_task = asyncio.create_task(
        projection_signal_loop(stop_event),
        name="pocketlab-worker-projection-signals",
    )

    def _projection_task_done(task: asyncio.Task[Any]) -> None:
        if task.cancelled() or stop_event.is_set():
            return
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        _worker_log(
            "worker.projection_task_stopped",
            error_type=type(exc).__name__ if exc is not None else "UnexpectedExit",
        )
        stop_event.set()

    projection_task.add_done_callback(_projection_task_done)
    os.environ.setdefault("POCKETLAB_NATS_REQUIRED", "1")
    BUS.required = True
    await connect_worker_bus(stop_event)
    if stop_event.is_set():
        projection_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await projection_task
        from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER  # type: ignore
        await asyncio.to_thread(PROJECTION_SCHEDULER.shutdown)
        return 0
    hb_task = asyncio.create_task(
        heartbeat(stop_event), name="pocketlab-worker-heartbeat"
    )
    recovery_task = asyncio.create_task(
        worker_recovery_watchdog(stop_event),
        name="pocketlab-worker-recovery-watchdog",
    )
    release_task = asyncio.create_task(
        release_scheduler_loop(stop_event),
        name="pocketlab-worker-release-scheduler",
    )
    await stop_event.wait()
    for task in (hb_task, recovery_task, release_task, projection_task):
        task.cancel()
    for task in (hb_task, recovery_task, release_task, projection_task):
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER  # type: ignore
    await asyncio.to_thread(PROJECTION_SCHEDULER.shutdown)
    try:
        await publish(
            "pocketlab.events.worker.stopped", "worker.stopped", {"pid": os.getpid()}
        )
    except Exception:
        pass
    await BUS.stop()
    return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Pocket Lab worker failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
