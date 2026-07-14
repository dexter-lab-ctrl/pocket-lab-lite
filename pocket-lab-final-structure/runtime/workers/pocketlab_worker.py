#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
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
    try:
        result = await run_domain_command(subject, command)
        await publish(
            "pocketlab.events.command.succeeded",
            "command.succeeded",
            {
                "command_id": command_id,
                "command_subject": subject,
                "status": result.get("status", "success"),
            },
            trace_id=trace_id,
        )
    except Exception as exc:
        await publish(
            "pocketlab.events.command.failed",
            "command.failed",
            {"command_id": command_id, "command_subject": subject, "error": str(exc)},
            trace_id=trace_id,
        )
        raise


async def command_callback(msg: Any) -> None:
    subject = str(getattr(msg, "subject", "") or "")
    attempt = BUS.delivery_attempt(msg)
    command: Dict[str, Any] = {}
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
        if subject == "pocketlab.commands.lite.security.scan":
            from api_fastapi.services import lite_security  # type: ignore

            run_id = str(command.get("run_id") or command_id)
            if run_id:
                await asyncio.to_thread(
                    lite_security.mark_command_received,
                    run_id,
                    delivery_attempt=attempt,
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
        if attempt >= reliability.max_deliver():
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


async def main_async() -> int:
    stop_event = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except Exception:
            pass

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

    os.environ.setdefault("POCKETLAB_NATS_REQUIRED", "1")
    BUS.required = True
    await connect_worker_bus(stop_event)
    if stop_event.is_set():
        return 0
    hb_task = asyncio.create_task(
        heartbeat(stop_event), name="pocketlab-worker-heartbeat"
    )
    recovery_task = asyncio.create_task(
        worker_recovery_watchdog(stop_event),
        name="pocketlab-worker-recovery-watchdog",
    )
    await stop_event.wait()
    for task in (hb_task, recovery_task):
        task.cancel()
    for task in (hb_task, recovery_task):
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
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
