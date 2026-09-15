# 10. Deep playbook

Deep is manual-only, explicit, and resource-heavy. It is appropriate for a
reviewed release candidate or a focused investigation, not for normal
production startup or every commit.

## Run

**[APPROVED CLIENT]** Use the explicit full workflow only with manual intent:

```bash
task lite:security:assurance:qualify:full
```

For an already-established session, the registered phone path is:

```bash
task lite:security:assurance:preflight SUITE=deep
task lite:security:assurance:deep
```

The profile target is 3,600 seconds and maximum durable run lease is 7,200
seconds. It is non-destructive and permits only `PASSIVE` and `SAFE_ACTIVE`
units. Deep does not include Recovery restore, password attacks, uncontrolled
DoS, or unrelated network targets.

## Sequence

The current orchestration schedules one heavy unit at a time and checkpoints
each completed unit:

1. preflight, readiness, policy revision, and source-boundary assertions;
2. existing worker-owned Full Security path with its cache/SBOM/exclusions;
3. fixed DEV-PC static tools in registry order;
4. fixed DEV-PC live-runtime probes through the approved local tunnel;
5. threat/OWASP/AP aggregation, delta comparison, and sanitized report.

Registered Deep tools are listed in the [tool matrix](../reference/tool-matrix.md).
The DEV-PC lane is not phone-native. The phone path remains FastAPI →
NATS/JetStream → `pocket-worker` → Security lifecycle.

## Resource controls

Before and during Deep, record available duration, CPU/RSS where supported,
disk delta, battery/charging, temperature/thermal state, load, tool duration,
and resource-guard decisions. Missing Android measurements are `UNAVAILABLE`,
not zero. A timeout, resource stop, or parser failure is truthful `PARTIAL`,
`FAIL`, or `BLOCKED`; it is never promoted to `PASS`.

Sessions renew automatically while the bounded principal and qualification
window remain valid. The durable run lease, not session TTL, controls the
execution deadline. A restarted client reattaches by continuity state. A
worker restart reconciles heartbeat/checkpoints and retries only a registry
unit marked retry-safe.

## Interpretation

Deep `PARTIAL` can mean that the harness correctly stopped at a resource or
tool boundary, or that only part of the registered coverage completed. It may
also coexist with normalized findings. Review the per-tool and per-scenario
statuses before deciding whether the harness failed or the security posture
needs remediation.
