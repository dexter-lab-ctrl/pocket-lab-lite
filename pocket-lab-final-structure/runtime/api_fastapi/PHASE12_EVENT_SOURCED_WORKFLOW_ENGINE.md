# Phase 12 — Event-sourced workflow engine

Phase 12 upgrades Phase 11's retry/dead-letter layer into an enterprise workflow engine that can reconstruct workflow state from events instead of relying only on local operation JSON records.

## What is persisted

Every Pocket Lab event recorded by the FastAPI/NATS event bus is appended to:

```text
$POCKETLAB_STATE_DIR/workflows/events/workflow_events.jsonl
```

A compact projection is maintained at:

```text
$POCKETLAB_STATE_DIR/workflows/projections/workflow_projections.json
```

Replayable command metadata is journaled at:

```text
$POCKETLAB_STATE_DIR/workflows/commands/command_journal.json
```

Sensitive values such as tokens, API keys, passwords, and secret values are redacted before being written to the workflow journal.

## New APIs

```text
GET  /api/workflows/status
GET  /api/workflows
GET  /api/workflows/events
GET  /api/workflows/{workflow_id}
GET  /api/workflows/{workflow_id}/command
POST /api/workflows/rebuild
GET  /api/workflows/recovery/plan
POST /api/workflows/recover
POST /api/workflows/{workflow_id}/replay
```

Existing Phase 11 reliability APIs remain compatible:

```text
GET  /api/reliability/status
GET  /api/reliability/dead-letters
POST /api/reliability/dead-letters/{dead_letter_id}/replay
POST /api/reliability/recover
```

but replay and recovery now delegate to the event-sourced workflow engine where possible.

## Recovery model

The engine classifies workflows as `queued`, `running`, `retrying`, `succeeded`, `failed`, or `dead_lettered` based on replayed events.

`/api/workflows/recovery/plan` identifies stale non-terminal workflows.

`/api/workflows/recover` replays stale workflows using the command journal and publishes fresh commands to NATS/JetStream.

`/api/workflows/{workflow_id}/replay?as_new=true` replays a failed/dead-lettered workflow as a new command identity while preserving `replay_of` and `replayed_from` correlation.

## Enterprise behavior

- Append-only event journal
- Deterministic state reconstruction
- Projection rebuild after restart or corruption
- Dead-letter correlation
- Replay-as-new-workflow
- Stale workflow recovery plan
- Sensitive-field redaction
- Termux-friendly file-backed persistence

## Important note

This remains lightweight and self-hostable. It does not require a database. Commands are durable in JetStream and workflow state is reconstructed from the local event journal; production write paths require real NATS/JetStream.
