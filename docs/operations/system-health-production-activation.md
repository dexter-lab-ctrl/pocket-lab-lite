# Governed System Health production activation

Status: `VERIFIED` source contract for the `feat/system-health-production-activation`
candidate. This document describes eligibility and a future rollout; it is not
evidence that the active Server Phone has been activated.

## Scope and safety boundary

The candidate promotes only six Owner-assisted operations after their isolated
qualification evidence is accepted. One fixed Risk A automatic operation is
source-qualified, but it remains separately default-off and is limited to the
`system.activity_history` projection. Existing supervisors, the worker recovery
watchdog, the security-maintenance owner and the projection scheduler remain the
execution owners. No new supervisor, service restart engine, configuration
reconciler or arbitrary shell path is introduced.

The production flags remain disabled unless an authorized future rollout sets
them explicitly:

```text
POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED=0
POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC=0
POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE=0
```

The assisted and automatic runtime revision variables are separate activation
fences. They are not secrets. Each rollout must use a new bounded value and the
current Owner must save the corresponding preference after that value is
configured. An old preference therefore cannot become effective merely because
a later release or runtime flag changes:

```text
POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED_REVISION=<new-assisted-rollout-revision>
POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC_REVISION=<new-automatic-rollout-revision>
```

The source-owned qualification revision is
`system-health-a1-2026-11-26`. Changing the reviewed allowlist or its execution
contract requires a new source revision and new qualification evidence.

## Exact operation inventory

The catalog has 35 entries. Catalog presence is descriptive and does not imply
execution. `Source-qualified` means the reviewed source allowlist admits the
operation; `runtime-gated` means the operation still requires the matching
runtime flag, activation fence, current Owner preference, fresh target
evidence, current OPA authorization and the existing execution owner.

| Operation | Risk | Execution owner | Classification | Candidate production state | Automatic |
| --- | --- | --- | --- | --- | --- |
| `runtime.consumer.reconnect` | A | `nats_worker_watchdog` | Implemented assisted adapter; existing owner-managed watchdog | Source-qualified assisted, runtime-gated | No |
| `runtime.nats.recover` | B | `core_supervisor` | Existing production owner-managed behavior | Existing guardian only | Never new automatic |
| `runtime.gateway.recover` | B | `core_supervisor` | Existing production owner-managed behavior | Existing guardian only | Never new automatic |
| `runtime.worker.recover` | B | `core_supervisor` | Existing production owner-managed behavior | Existing guardian only | Never new automatic |
| `runtime.telemetry.recover` | B | `core_supervisor` | Implemented assisted adapter using existing supervisor | Disabled; no isolated promotion in this candidate | No |
| `runtime.server_agent.recover` | B | `core_supervisor` | Implemented assisted adapter using existing supervisor | Disabled; no isolated promotion in this candidate | No |
| `runtime.api.recover` | B | `runtime_guardian` | Existing production owner-managed behavior | Existing guardian only | Never new automatic |
| `runtime.gateway.validate` | A | `runtime_reconciler` | Unsupported candidate | Disabled | No |
| `runtime.policy.recover` | B | `existing_policy_supervisor` | Guided existing workflow | Rules controls only | No |
| `network.remote_access.restore` | B | `existing_remote_access_owner` | Guided existing workflow | Devices controls only | No |
| `device.agent.recover` | A | `node_supervisor` | Existing production owner-managed behavior | Existing guardian only | No |
| `app.repair` | B | `existing_app_action` | Guided existing workflow | Apps controls only | No |
| `storage.logs.preview` | A | `security_maintenance` | Implemented read-only assisted adapter | Source-qualified assisted, runtime-gated | No |
| `storage.logs.cleanup` | B | `existing_retention_owner` | Implemented reviewed-maintenance adapter | Disabled; disposable fixtures only | Never automatic |
| `storage.temp.preview` | A | `security_maintenance` | Implemented read-only assisted adapter | Source-qualified assisted, runtime-gated | No |
| `storage.temp.cleanup` | B | `existing_maintenance_owner` | Implemented reviewed-maintenance adapter | Disabled; disposable fixtures only | Never automatic |
| `storage.cache.cleanup` | B | `existing_app_action` | Guided existing workflow | Catalog guidance only | No |
| `storage.evidence.preview` | A | `security_maintenance` | Implemented read-only assisted adapter | Source-qualified assisted, runtime-gated | No |
| `storage.evidence.retention` | B | `security_maintenance` | Implemented reviewed-maintenance adapter | Disabled; disposable fixtures only | Never automatic |
| `sqlite.checkpoint.passive` | A | `security_maintenance` | Implemented passive assisted adapter | Source-qualified assisted, runtime-gated | No |
| `sqlite.health.review` | A | `existing_recovery_owner` | Guided existing workflow | Recovery controls only | No |
| `projection.reconcile` | A | `projection_scheduler` | Implemented assisted adapter and fixed automatic adapter | Source-qualified assisted, separately runtime-gated | Yes, fixed domain only |
| `maintenance.window` | B | `security_maintenance` | Unsupported candidate | Disabled | No |
| `workflow.retry` | B | `existing_command_owner` | Unsupported candidate | Disabled; no blind replay | No |
| `workflow.cancel` | B | `existing_command_owner` | Unsupported candidate | Disabled; owner contract remains authoritative | No |
| `resource.defer` | A | `projection_scheduler` | Unsupported candidate | Disabled | No |
| `resource.resume` | A | `projection_scheduler` | Unsupported candidate | Disabled | No |
| `runtime.configuration.restore` | B | `runtime_reconciler` | Implemented assisted adapter using existing reconciler | Disabled; no isolated promotion in this candidate | No |
| `policy.known_good.reconcile` | B | `policy_lifecycle` | Guided existing workflow | Rules controls only | No |
| `security.scanner.review` | A | `existing_security_owner` | Guided existing workflow | Security controls only | No |
| `recovery.backup.create` | B | `existing_recovery_owner` | Guided existing workflow | Recovery controls only | No |
| `recovery.backup.verify` | A | `existing_recovery_owner` | Guided existing workflow | Recovery controls only | No |
| `recovery.database.rehearse` | B | `existing_recovery_owner` | Implemented isolated-copy rehearsal adapter | Disabled; no isolated promotion in this candidate | No |
| `recovery.database.restore` | C | `recovery` | Protected manual recovery | Never automatic; not promoted | Never |
| `diagnostics.support.export` | B | `existing_evidence_owner` | Unsupported candidate | Disabled | No |

Cleanup, service recovery, configuration restoration and database rehearsal are
intentionally left disabled here. A source adapter and unit contract are not
the required actual disposable-fixture execution evidence. No Risk B or Risk C
operation is automatic, and no cleanup operation is automatic.

## Activation state exposed to Lite

The operation catalog now separates:

- implementation status from source qualification;
- source-qualified from runtime-enabled;
- Owner preference from the current activation fence;
- assisted requestability from automatic admission;
- catalog metadata from request-scoped authorization, target eligibility,
  execution and independent verification.

Catalog-level authorization, eligibility, execution and verification are
reported as request/target scoped rather than being guessed. Sanitized reason
codes identify source qualification, runtime opt-in, Owner confirmation,
emergency disable, current preference and automatic-gate restrictions. The
System Health Owner controls reuse the existing Manage surface and show built-in
protection, current Rules authority, the reviewed assisted set, effective
activation, the fixed automatic candidate and recorded outcomes. They do not
expose policy source, credentials or an execution command.

The automatic lifecycle uses a durable attempt ID in the existing automation
table and passes `reconcile_system_health_automatic:<attempt-id>` through the
existing projection scheduler. Completion is verified only when the same
domain's prepared state reports that exact trigger, a fresh completion, no
error and the worker execution owner. An ordinary scheduled refresh cannot
complete an automatic attempt. Emergency disable blocks newly admitted or
newly claimed work; it does not promise cancellation of work already executing.

## Current production prerequisite disposition

The installed release is `lite-2026.11.26.1` at the verified main SHA
`58219b2aa92364447a65b9aa55276250b3bdfbbc`. Read-only production evidence
confirmed native health/readiness, SQLite integrity, one PM2-owned runtime tree,
loopback NATS health and a current active/known-good OPA revision. The staged
repository policy revision differs from the active revision and is therefore
`policy_source_update_pending`; no System Health production action is admitted
until the policy is legitimately confirmed.

The current supported Owner action is:

1. Sign in as the real human Owner.
2. Open Lite **Rules / Safety Rules**.
3. Select **Update Safety Rules** when the repository update is shown.
4. Complete the recent passkey step-up for `policy.rules.activate`.
5. Wait for the server-reported source-sync operation to reach verified active
   and known-good state. An accepted request is not completion evidence.

This action must be performed by the human Owner through the supported Rules
flow. A synthetic qualification principal must not approve the production
policy, and this candidate does not perform that action.

## Candidate qualification evidence

The following evidence is `VERIFIED` for this exact candidate and is bounded to
disposable fixtures, the isolated Android/Termux candidate lane, or
repository-owned mocked surfaces:

- `tests/backend/test_lite_system_health.py`: 50 passed, including the
  source-qualified maintenance adapters through the existing worker command
  handler, activation-fence revision rotation, exact automatic-attempt
  correlation, durable single-flight completion and emergency-disable gate.
- `tests/backend/test_lite_system_health_semantic_revision.py` and
  `tests/backend/test_lite_system_health_android_qualification.py` plus the
  UI-candidate contracts: 33 qualification-contract tests passed.
- The exact-SHA Android/Termux backend lane passed with the candidate API and
  worker owned in a run-owned Termux root, disposable NATS/JetStream, exact
  candidate OPA, and a qualification-owner recovery lifecycle of
  `executing` → `verified` for `runtime.consumer.reconnect`. It also proved
  idempotent replay, stale-generation rejection, unauthorized-write rejection,
  SQLite schema 42 → 55 integrity/concurrency checks, and run-root cleanup;
  the active Server Phone remained at `main` SHA
  `58219b2aa92364447a65b9aa55276250b3bdfbbc`.
- The focused API slice passed 171 tests with Node 24 available; targeted
  frontend unit tests passed 22 tests; the mocked System Health desktop/mobile
  browser lane passed 52 tests; and `npm run build` passed.
- `task lite:docs:generate` and the strict `task lite:docs:check` passed,
  including contracts, source-derived platform catalogs, Codebase Map,
  SchemaSpy, architecture, MkDocs and runtime-network checks.

This evidence does not claim a live production action, physical Android UI
qualification, or a production NATS/SQLite execution. The backend Android
lane used only a temporary run-owned Termux root and disposable broker/database
state; its production-activation result remained `BLOCKED` by design. The
physical Android UI runner was not invoked because no device serial was
selected and physical UI qualification is not mandatory for this initiative.
The required full
`task lite:check` passed with the repository-compatible JDK
`/home/dj/.cache/pocketlab-java/jdk-exact-17.0.20.1`; the exact Java guard was
not weakened.

## Future authorized rollout procedure

The following is a reviewed procedure for a separately authorized deployment;
it was not run against the active Server Phone in this initiative.

1. Deploy the exact qualified source with both production activation flags
   disabled and emergency disable set to its normal non-disabled value. Keep
   the assisted and automatic runtime revision fences unset or rotated to the
   new rollout values. Confirm the release SHA, API/worker source SHA, native
   readiness, SQLite path/integrity, NATS/JetStream consumers, supervisor
   ownership, backup readiness and active/known-good OPA identity.
2. Have the real Owner complete the Rules source confirmation above. Verify
   active and known-good policy revisions converge and no source update is
   pending.
3. Set a new assisted runtime revision on the API, worker and every relevant
   execution owner while `POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED=0`.
   The Owner saves **Prefer assisted recovery** in System Health. Verify the
   durable activation fence, Owner authority versions and sanitized policy
   status from the API and worker configuration; do not enable automatic
   recovery at this stage.
4. Set `POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED=1` consistently on the
   API, worker and relevant execution owners. Observe only the six source-
   qualified operations. Verify each request's current Owner, OPA decision,
   target/generation, fresh observations, durable command, existing execution
   owner, isolated result and independent audit evidence. Leave an operation
   disabled if any item is missing.
5. For the fixed automatic operation only, set a separate automatic runtime
   revision while `POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC=0`. The Owner
   saves **Prefer automatic history reconciliation**, then verify the durable
   automatic policy, current Owner/membership/configuration versions, active
   known-good OPA revision and resource/maintenance gates.
6. Set `POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC=1` consistently on the
   worker and projection execution owner. Observe the exact attempt ID, trigger
   reason, worker scheduler execution, completion, timeout/escalation and
   persisted evidence. Ordinary refreshes must not satisfy the attempt.
7. Test the documented emergency disable in the authorized environment. Confirm
   new assisted and automatic admissions/claims are blocked, existing guardians
   remain operational, and in-flight work is reported according to its actual
   uncertain/outcome contract rather than being claimed cancelled.
8. Roll back safely by enabling emergency disable, stopping new production
   activation flags, and saving Owner monitor-only preferences. Reconcile and
   preserve uncertain outcomes without blind replay. Restore the previously
   verified source/release only through the normal governed rollback process;
   do not reset a database or delete evidence.

At every stage, verify effective settings at the API, worker and actual
execution-owner boundaries. Installation and startup must never activate all
qualified operations automatically.
