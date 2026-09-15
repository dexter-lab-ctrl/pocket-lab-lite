# 7. Smoke playbook

Smoke is the fast, low-power assurance gate. It is the first authenticated
run and should be used after every candidate deployment.

## Run

**[APPROVED CLIENT]** The recommended workflow performs bootstrap, renewal,
polling, report assembly, and cleanup:

```bash
task lite:security:assurance:qualify
```

For an already-authenticated client, the registered suite command is:

```bash
task lite:security:assurance:preflight SUITE=smoke
task lite:security:assurance:smoke
```

The exact session remains in the approved client process. Never paste a raw
session value into a shell history, report, or chat.

## Scope and checkpoints

The current `smoke` profile is non-destructive and permits `PASSIVE` and
`SAFE_ACTIVE` units. Its target is 180 seconds and its maximum run lease is
1,200 seconds. It uses the existing `quick` Security profile and the current
Smoke scenario set:

| Scenario | Question |
| --- | --- |
| `harness-default-off` | Does normal startup remain fail-closed? |
| `harness-auth-boundary` | Does the signed synthetic session stay bounded? |
| `caddy-proof-strip` | Can proxy traffic activate harness authority? |
| `runtime-readiness` | Are health/readiness and PM2 process posture distinguished? |
| `control-plane-ownership` | Does FastAPI → NATS → worker remain authoritative? |
| `evidence-redaction` | Is durable evidence sanitized? |
| `security-projection` | Is existing Security lifecycle evidence available? |
| `threat-model-integrity` | Does the canonical STRIDE model load and cover AP paths? |

The worker persists suite, scenario, and tool checkpoints. A typical run moves
through `QUEUED` → `RUNNING` → `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or
`CANCELLED`. The operation and worker correlation fields in the run response
prove this was not a local CLI shortcut.

## Fast reviewer checklist

- candidate and phone SHAs match;
- phone worktree is clean;
- qualification is explicit and dangerous flags are off;
- `/health` and `/ready` are healthy;
- NATS/JetStream and worker are available;
- run has a fixed assurance subject and worker execution evidence;
- no raw secret or user-media evidence is present;
- finding severities and coverage are reviewed before declaring the suite;
- session/principal cleanup and default-off proof are captured.

## Interpretation

`PASS` is an invariant result, not “all tools found zero issues.” A normalized
finding may exist in a passing execution when the finding is below the policy
threshold or informational. A missing dependency, resource stop, or lost
worker is not a pass; it is reported as `PARTIAL`, `BLOCKED`, or `FAIL` with a
reason. Continue to [evidence/reporting](15-evidence-reporting.md) and
[findings/remediation](14-findings-remediation.md).
