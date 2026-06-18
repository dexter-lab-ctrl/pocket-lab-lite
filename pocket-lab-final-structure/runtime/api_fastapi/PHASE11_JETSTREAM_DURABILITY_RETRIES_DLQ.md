# Phase 11 — JetStream durability, retries, and dead-letter queues

Phase 11 makes Pocket Lab command execution restart-safe by moving worker command
consumption onto a JetStream durable consumer when NATS/JetStream is available.
The FastAPI/NATS control API and frontend remain compatible with previous
phases, while operations gain explicit acknowledgement, retry, and dead-letter
semantics.

## Runtime model

```text
FastAPI route
  -> submit queued operation/domain command
  -> JetStream stream POCKETLAB_COMMANDS
  -> durable worker consumer pocketlab_command_worker_v1
  -> explicit ack on success
  -> nak with exponential backoff on transient failure
  -> dead-letter after max delivery attempts
```

## Streams

The event bus configures these streams:

- `POCKETLAB_COMMANDS` for `pocketlab.commands.>`
- `POCKETLAB_EVENTS` for `pocketlab.events.>`
- `POCKETLAB_AUDIT` for `pocketlab.audit.>`
- `POCKETLAB_TELEMETRY` for `pocketlab.events.telemetry.>`
- `POCKETLAB_DLQ` for `pocketlab.dlq.>`

## Worker durability

`runtime/workers/pocketlab_worker.py` now subscribes with
`BUS.subscribe_durable(...)`. With JetStream available, this creates a durable
consumer so queued commands survive API/worker restarts. If the local NATS client
or server cannot create a durable consumer, the worker falls back to the previous
live queue subscription rather than failing the edge device.

## Retry policy

Controlled by environment variables:

```bash
export POCKETLAB_COMMAND_MAX_DELIVER=5
export POCKETLAB_COMMAND_ACK_WAIT_SECONDS=60
export POCKETLAB_COMMAND_RETRY_BASE_SECONDS=5
export POCKETLAB_COMMAND_RETRY_MAX_SECONDS=300
export POCKETLAB_COMMAND_MAX_ACK_PENDING=64
```

On failure, the worker publishes:

- `pocketlab.events.command.retry_scheduled`

After the maximum delivery count, the worker publishes:

- `pocketlab.events.command.dead_lettered`
- `pocketlab.dlq.<original_subject>`

Operation runs are marked `retrying` during retry and `dead_lettered` when the
worker stops retrying.

## Reliability APIs

```text
GET  /api/reliability/status
GET  /api/reliability/dead-letters
POST /api/reliability/dead-letters/{dead_letter_id}/replay
POST /api/reliability/recover
```

`/api/reliability/recover` republishes queued/retrying worker-owned operation
runs after an API or worker restart.

## Frontend behavior

The live event translation layer now maps retry/dead-letter events:

- retry scheduled -> Simple Mode: **Action will retry**
- dead-lettered -> Simple Mode: **Action paused for review**

Professional Mode shows the subject, attempt count, error, and raw event payload
inside the existing advanced details panel.

## Termux/Android notes

`start-dashboard.sh` continues to launch `nats-server -js` with persistent state
under `$STATE_DIR/nats`. The worker and FastAPI process receive the retry-related
environment defaults through PM2 so reruns keep the same reliability policy.
