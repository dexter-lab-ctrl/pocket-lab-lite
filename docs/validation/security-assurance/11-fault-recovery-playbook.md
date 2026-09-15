# 11. Fault and recovery playbook

Fault controls are fixed, one-use, non-destructive qualification operations.
They are selected by ID, never by service name or arbitrary process command.
The fault-invariant result is distinct from the result of the assurance
operation running during the fault.

## List and execute

**[APPROVED CLIENT]** Inspect the fixed catalog and invoke one reviewed fault:

```bash
task lite:security:assurance:fault FAULT_ID=worker_restart_once
task lite:security:assurance:fault FAULT_ID=nats_restart_once
task lite:security:assurance:fault FAULT_ID=opa_restart_once
task lite:security:assurance:fault FAULT_ID=nats_pause_probe_restore
task lite:security:assurance:fault FAULT_ID=opa_pause_probe_restore
```

The phone must have been started through the explicit key-bound `:faults`
qualification task. The registry owns the service role/name, operation,
pause/recovery window, probe, timeout, and maximum uses.

## Fixed controls

| Fault ID | Controlled action | Proof required |
| --- | --- | --- |
| `worker_restart_once` | restart `pocket-worker` once | heartbeat interruption/reconciliation, same run identity, safe resume, truthful terminal state |
| `nats_restart_once` | restart Pocket Lab NATS once | TCP/JetStream/worker recovery and durable state |
| `opa_restart_once` | restart OPA once | health and exact policy revision recover |
| `nats_pause_probe_restore` | bounded NATS unavailable window, automatic restore | no false PASS, no duplicate execution, reconnect, JetStream and worker recovery |
| `opa_pause_probe_restore` | bounded OPA unavailable window, governed probe, automatic restore | deny while unavailable, no fallback/Owner allow, current policy succeeds after restore |

## Worker restart/resume

Start a safe run, observe a durable completed unit, then use only the fixed
worker fault. Verify `run_id`, worker operation correlation, heartbeat/stale
state, checkpoint generation, and terminal outcome. Completed units must not be
re-executed merely because the worker restarted. If the interrupted unit is
not marked retry-safe, the truthful result is `PARTIAL` or review-required.

## Client disconnect and reattach

The client continuity file is outside Git and contains only principal/fingerprint,
key path, run ID, suite/scenario, event sequence, runtime, and revision. To
exercise a client crash, terminate only the client monitor process after the
run is admitted, wait for the backend to continue, then start the approved
client again. It must obtain a fresh session and GET the same `run_id`; no
duplicate submission is allowed. The client CLI `qualify` path implements this
reattachment state machine.

## OPA unavailable-window

Use `opa_pause_probe_restore` only when no protected mutation is active. The
fixed supervisor pauses OPA, issues one governed probe, records the denial,
restores OPA in a bounded `finally` path, verifies health/current revision,
and reruns the same probe. OPA unavailable must not become allow, Owner
fallback, stale-policy allow, or test-auth bypass.

## NATS unavailable-window

Use `nats_pause_probe_restore` only with an isolated safe assurance run. The
control pauses only Pocket Lab NATS, restores it promptly, and verifies
JetStream and worker reconnect. Never delete streams/consumers, modify
JetStream storage, or publish an arbitrary subject. The run must retain
truthful state and correlation; a command interrupted by the outage may fail
while the recovery invariant passes.

## Recovery evidence

Capture before/after health, readiness, policy revision, worker heartbeat,
checkpoint/event sequence, operation/run IDs, delivery/reconnect state, and
sanitized audit evidence. Do not treat a process list alone as recovery proof.
