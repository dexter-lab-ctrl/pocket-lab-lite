# Phase 7: Live Operation Runner Logs

Phase 7 publishes every `OperationService` runner event as a live Pocket Lab event so the UI can show real progress instead of only queued/running/succeeded snapshots.

## Event contract

Runner events are emitted on:

- `pocketlab.events.operation.log`
- `pocketlab.events.operation.log.warning`
- `pocketlab.events.operation.log.error`

Each event has type:

```text
operation.log
```

Typical payload:

```json
{
  "job_id": "...",
  "operation": "deploy_blueprint",
  "task_id": "deploy_blueprint",
  "status": "running",
  "level": "info",
  "message": "Running Ansible playbook site.yml",
  "stream": "stdout|stderr|ansible",
  "step": "source|artifact|ansible",
  "timestamp": "2026-05-31T...Z"
}
```

Sensitive keys such as `api_key`, `token`, `password`, `secret`, and `value` are redacted before event publication.

## Backend changes

- `OperationService.set_event_publisher(...)` attaches a framework-neutral sync publisher callback.
- `_emit(...)` still appends to local operation state, then best-effort publishes a live event.
- FastAPI installs the publisher during application startup.
- The worker installs the publisher before handling commands.
- Worker operation execution now runs in a background thread with the asyncio event loop free to publish logs while operations are running.
- `AnsibleRunnerService.run_playbook(...)` accepts an optional event handler so Ansible Runner events are relayed through the same operation log stream.

## Frontend changes

`friendlyEvent(...)` now understands `operation.log` events.

Simple Mode shows plain progress updates such as:

- Preparing blueprint source
- Running Ansible playbook
- Backup snapshot created
- Operation completed

Professional Mode includes job id, step, stream, subject, and raw payload through advanced details.

## Compatibility

The legacy operation state remains the source of truth. If NATS or WebSocket streaming is unavailable, the app still stores runner events on the job record and the frontend falls back to `/api/events/recent` or normal operation polling.
