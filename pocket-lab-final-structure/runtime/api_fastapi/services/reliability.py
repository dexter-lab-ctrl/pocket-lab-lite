from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .. import deps


def max_deliver() -> int:
    return max(1, int(os.environ.get("POCKETLAB_COMMAND_MAX_DELIVER", "5")))


def ack_wait_seconds() -> int:
    return max(5, int(os.environ.get("POCKETLAB_COMMAND_ACK_WAIT_SECONDS", "60")))


def retry_delay_seconds(attempt: int) -> int:
    base = max(1, int(os.environ.get("POCKETLAB_COMMAND_RETRY_BASE_SECONDS", "5")))
    cap = max(base, int(os.environ.get("POCKETLAB_COMMAND_RETRY_MAX_SECONDS", "300")))
    return min(cap, base * (2 ** max(0, attempt - 1)))


def _state_path(name: str) -> Path:
    path = deps.settings().state_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_dead_letter(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _state_path("dead_letters.json")
    payload = _read_json(path, {"items": []})
    items = list(payload.get("items") or [])
    record = dict(record)
    record.setdefault(
        "dead_letter_id",
        record.get("command_id")
        or record.get("job_id")
        or record.get("event_id")
        or "unknown",
    )
    record.setdefault("created_at", deps.now_utc_iso())
    items.append(record)
    limit = max(100, int(os.environ.get("POCKETLAB_DLQ_HISTORY_LIMIT", "1000")))
    payload["items"] = items[-limit:]
    payload["updated_at"] = deps.now_utc_iso()
    _write_json(path, payload)
    return record


def recent_dead_letters(limit: int = 100) -> List[Dict[str, Any]]:
    payload = _read_json(_state_path("dead_letters.json"), {"items": []})
    items = list(payload.get("items") or [])
    return items[-max(1, min(limit, 1000)) :]


def reliability_status() -> Dict[str, Any]:
    from .workflow_engine import WORKFLOW_ENGINE

    return {
        "status": "ok",
        "phase": "phase12-event-sourced-workflows",
        "max_deliver": max_deliver(),
        "ack_wait_seconds": ack_wait_seconds(),
        "retry_base_seconds": int(
            os.environ.get("POCKETLAB_COMMAND_RETRY_BASE_SECONDS", "5")
        ),
        "retry_max_seconds": int(
            os.environ.get("POCKETLAB_COMMAND_RETRY_MAX_SECONDS", "300")
        ),
        "dead_letters": len(recent_dead_letters(limit=1000)),
        "workflow_engine": WORKFLOW_ENGINE.status(),
    }


def mark_operation_retrying(job_id: str, *, attempt: int, error: str) -> None:
    if not job_id:
        return
    try:
        deps.operation_service().state.update_run(
            job_id,
            lambda run: {
                **run,
                "status": "retrying",
                "retry_attempt": attempt,
                "last_retry_error": error,
                "updated_at": deps.now_utc_iso(),
            },
        )
    except Exception:
        pass


def mark_operation_dead_letter(job_id: str, *, attempt: int, error: str) -> None:
    if not job_id:
        return
    try:
        deps.operation_service().state.update_run(
            job_id,
            lambda run: {
                **run,
                "status": "dead_lettered",
                "retry_attempt": attempt,
                "error": error,
                "dead_lettered_at": deps.now_utc_iso(),
                "updated_at": deps.now_utc_iso(),
            },
        )
    except Exception:
        pass


async def replay_dead_letter(dead_letter_id: str) -> Dict[str, Any]:
    """Replay a dead letter as a new event-sourced workflow.

    Phase 12 keeps the Phase 11 DLQ endpoint but delegates replay to the
    workflow engine when possible, so replay creates a fresh command identity
    while preserving correlation to the failed workflow/dead-letter record.
    """
    from .nats_bus import BUS
    from .workflow_engine import WORKFLOW_ENGINE

    items = recent_dead_letters(limit=1000)
    match = None
    for item in reversed(items):
        if str(
            item.get("dead_letter_id") or item.get("command_id") or item.get("job_id")
        ) == str(dead_letter_id):
            match = item
            break
    if not match:
        raise KeyError(f"Dead letter not found: {dead_letter_id}")

    workflow_id = str(
        match.get("job_id")
        or match.get("command_id")
        or match.get("dead_letter_id")
        or dead_letter_id
    )
    try:
        replay = await WORKFLOW_ENGINE.replay_workflow(workflow_id, as_new=True)
    except Exception:
        subject = str(
            match.get("original_subject")
            or match.get("subject")
            or "pocketlab.commands.operation.execute"
        )
        command = dict(match.get("command") or {})
        new_id = uuid.uuid4().hex
        command["replayed_from_dead_letter"] = str(dead_letter_id)
        command["replay_of"] = workflow_id
        command["command_id"] = command.get("command_id") or new_id
        command["trace_id"] = (
            command.get("command_id") or command.get("job_id") or str(dead_letter_id)
        )
        event = await BUS.publish_json(
            subject,
            "workflow.replay_requested",
            command,
            trace_id=command.get("trace_id"),
        )
        replay = {
            "status": "replay_requested",
            "subject": subject,
            "event": event,
            "dead_letter_id": dead_letter_id,
            "workflow_id": workflow_id,
        }

    await BUS.publish_json(
        "pocketlab.events.workflow.dead_letter_replayed",
        "workflow.dead_letter_replayed",
        {
            "dead_letter_id": dead_letter_id,
            "workflow_id": workflow_id,
            **{k: v for k, v in replay.items() if k != "event"},
        },
        trace_id=str(replay.get("replayed_as") or workflow_id),
    )
    return {
        "status": "replayed",
        "dead_letter_id": dead_letter_id,
        "workflow_id": workflow_id,
        "replay": replay,
    }


async def recover_queued_operations(limit: int = 25) -> Dict[str, Any]:
    """Recover queued/retrying operations and stale event-sourced workflows.

    This keeps backwards compatibility with Phase 11 operation recovery while
    also using the Phase 12 workflow engine to reconstruct and replay stale
    non-terminal workflows after an API/worker restart.
    """
    from .nats_bus import BUS
    from .workflow_engine import WORKFLOW_ENGINE

    recovered: list[Dict[str, Any]] = []
    for run in deps.operation_service().list(limit=max(1, min(limit, 200))):
        if run.get("status") not in {"queued", "retrying"}:
            continue
        if not run.get("worker_execution"):
            continue
        command = {
            "job_id": run.get("job_id"),
            "operation": run.get("operation"),
            "task_id": run.get("task_id"),
            "target": run.get("target") or {},
            "params": run.get("params") or {},
            "dry_run": bool(run.get("dry_run", False)),
            "trace_id": run.get("job_id"),
            "recovered_at": deps.now_utc_iso(),
        }
        await BUS.publish_json(
            "pocketlab.commands.operation.execute",
            "operation.recovered",
            command,
            trace_id=str(run.get("job_id") or ""),
        )
        recovered.append(
            {
                "job_id": run.get("job_id"),
                "operation": run.get("operation"),
                "status": run.get("status"),
                "source": "operation_state",
            }
        )

    workflow_recovery = await WORKFLOW_ENGINE.recover(limit=limit, dry_run=False)
    await BUS.publish_json(
        "pocketlab.events.workflow.recovery_completed",
        "workflow.recovery_completed",
        {
            "operation_recovered_count": len(recovered),
            "workflow_recovered_count": workflow_recovery.get("recovered_count", 0),
        },
    )
    return {
        "status": "recovered",
        "count": len(recovered),
        "runs": recovered,
        "workflow_recovery": workflow_recovery,
    }
