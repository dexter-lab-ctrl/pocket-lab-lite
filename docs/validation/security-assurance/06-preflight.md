# 6. Preflight and admission

Preflight is a deterministic admission decision. Run it before every suite;
the assurance API performs it again before creating a run. A blocked check is
infrastructure or qualification state, not an automatically generated
vulnerability.

**[APPROVED CLIENT / DEV PC]** Use the current fixed task:

```bash
task lite:security:assurance:preflight SUITE=smoke
task lite:security:assurance:preflight SUITE=standard
task lite:security:assurance:preflight SUITE=deep
task lite:security:assurance:preflight SUITE=adversarial
```

The CLI routes to `GET /api/lite/harness/security-assurance/preflight` and
returns `status=ready` or `status=blocked`, bounded check objects, failure
codes, and registry hashes.

## Admission checklist

| Check | Why it matters | Required value | `BLOCKED` remediation |
| --- | --- | --- | --- |
| Candidate revision | binds evidence to reviewed code | verified 40-hex revision | deploy the exact published revision |
| Phone worktree | prevents unreviewed source drift | clean | stop and restore through approved deployment; never patch in place |
| Environment | prevents production qualification authority | `qualification` | stop; do not enable harness in production |
| Harness | explicit opt-in | enabled for the window | use key-bound operator startup |
| Test-auth bypass | prevents alternate authority | off | stop and restore safe defaults |
| Qualification Owner | prevents synthetic privilege escalation | off | stop; Owner is not a machine profile |
| Destructive gate | keeps normal suites non-destructive | off | stop; use no destructive Recovery |
| `/health` | process/application health | HTTP 200 | inspect supported runtime health |
| `/ready` | dependency readiness | HTTP 200 and ready status | wait/recover; PM2 online is insufficient |
| Caddy | boundary probe target | healthy where required | restore supported proxy/runtime |
| NATS | control-plane transport | connected/reachable | restore service; do not publish manual messages |
| JetStream | durable delivery | available | restore/inspect supported NATS state |
| Worker | execution owner | online and recognized | use supported worker recovery only |
| OPA | current policy | ready for Standard/Deep | run the fixed policy-sync task; never bypass policy |
| Scanner capability | real execution path | existing Security or fixed tool receipts | install/check the registered tool only |
| Resource guard | protects phone and DEV PC | admitted | cool down/free space; do not override |
| Conflicting Security run | prevents duplicate heavyweight work | none for the selected profile | wait for terminal/reconciled state |
| Registry integrity | prevents drift | tools/suites/scenarios/fault hashes match | use the exact candidate source |

## Policy synchronization

If the preflight reports the supported policy-source synchronization condition,
use the fixed supervisor lifecycle:

```bash
task lite:security:assurance:policy-sync WAIT_SECONDS=120
```

Then rerun Standard preflight. Do not rewrite OPA files, force an allow, use
`qualification-owner`, or use test-auth bypass. If policy remains pending,
record the reason as `BLOCKED` and follow [troubleshooting](17-troubleshooting.md).

## Readiness interpretation

`ready` is an admission result, not a suite result. A run can still `FAIL` on a
security invariant or `PARTIAL` after an interruption. Conversely, a
preflight `BLOCKED` must not be reported as a security finding. Preserve the
preflight response in the run manifest and evidence report.
