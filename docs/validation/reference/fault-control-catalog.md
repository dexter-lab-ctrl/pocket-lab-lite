# Fault-control catalog

Fault controls are server-owned, qualification-only identifiers from the source
file `security/assurance/faults.yaml`.
They are not a service selector or a generic process-control API.

| Fault ID | Service role | Operation | Safety | Pause/recovery bound | Probe | Uses |
| --- | --- | --- | --- | --- | --- | --- |
| `worker_restart_once` | worker / `pocket-worker` | restart | SAFE_ACTIVE | recovery 90s | `worker_online_and_api_nats` | one |
| `nats_restart_once` | NATS / `pocket-nats` | restart | SAFE_ACTIVE | recovery 90s | `nats_tcp_jetstream_worker` | one |
| `opa_restart_once` | policy / `pocket-opa` | restart | SAFE_ACTIVE | recovery 90s | `opa_health_and_revision` | one |
| `opa_pause_probe_restore` | policy / `pocket-opa` | pause, fixed governed probe, restore | SAFE_ACTIVE | pause 5s; recovery 90s | `opa_unavailable_fail_closed` | one |
| `nats_pause_probe_restore` | NATS / `pocket-nats` | pause, fixed assurance observation, restore | SAFE_ACTIVE | pause 5s; recovery 90s | `nats_unavailable_recovery` | one |

## Invocation

Run only in explicit qualification mode with the required fault-control
capability and operator approval. On `[DEV PC]`/approved client:

```bash
task lite:security:assurance:fault FAULT_ID=<registered-fault-id>
```

The request body is fixed (`{"confirm": true}`) and the API chooses the
registered action. The caller cannot provide a service name, command, signal,
pause duration, NATS subject, or probe target.

## Safety and evidence

The fault-invariant result and the injected assurance operation result are
separate. For example, the probe during an OPA outage may be denied while the
OPA fail-closed/recovery invariant passes. An interrupted run must not become
PASS merely because the service later recovered. Preserve run ID, operation
correlation, heartbeat/checkpoint state, restored health, JetStream/consumer
state, and sanitized audit/evidence.

Do not delete streams or consumers, modify JetStream storage, stop unrelated
services, scan unrelated hosts, or use destructive Recovery controls. If the
fixed control is unavailable, report `UNSUPPORTED` or `BLOCKED` with the
reason rather than improvising an outage procedure.
