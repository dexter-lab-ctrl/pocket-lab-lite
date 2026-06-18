# Pocket Lab Phase 3: Worker Process

Phase 3 moves typed operation execution behind a worker process while preserving
all existing frontend `/api/...` contracts.

## Runtime flow

```text
React PWA
  -> FastAPI /api/operations/execute
  -> OperationService.submit_queued() creates a queued run
  -> NATS subject pocketlab.commands.operation.execute
  -> runtime/workers/pocketlab_worker.py consumes the command
  -> OperationService.run_existing(job_id) executes existing operation logic
  -> worker publishes operation lifecycle events
  -> FastAPI/WebSocket/event endpoints expose status to the UI
```

## Compatibility behavior

`POCKETLAB_WORKER_EXECUTION=worker` is the default.

- If FastAPI is connected to NATS, `/api/operations/execute` queues work for the
  worker.
- If NATS/JetStream is unavailable, FastAPI rejects write actions with 503.
- `POCKETLAB_WORKER_EXECUTION=worker` is the production setting.
- Direct in-process execution is disabled for production.

## Worker process

Entry point:

```bash
python3 pocket-lab-final-structure/runtime/workers/pocketlab_worker.py
```

The worker subscribes to:

```text
pocketlab.commands.operation.execute
```

with queue group:

```text
pocketlab-operation-workers
```

and publishes:

```text
pocketlab.events.worker.started
pocketlab.events.worker.heartbeat
pocketlab.events.worker.stopped
pocketlab.events.worker.error
pocketlab.events.operation.worker_claimed
pocketlab.events.operation.succeeded
pocketlab.events.operation.failed
```

## Health/status endpoints

```text
GET /api/workers/status
GET /api/events/status
GET /api/events/recent?subject_prefix=pocketlab.events.worker.
```

## Bootstrap integration

`start-dashboard.sh` now starts the following PM2 processes when available:

```text
pocket-nats
pocket-worker
pocket-api
```

Disable the worker with:

```bash
export POCKETLAB_DISABLE_WORKER=1
```

## Safety rule

The worker reuses existing typed operations. It does not accept arbitrary shell
commands and it does not transport secret values through NATS events.
