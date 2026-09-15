# 8. Standard playbook

Standard is the normal assurance qualification. It expands Smoke with the
policy, source, dependency, API, and attack-path coverage that is safe to run
under the current resource guard.

## Run

**[APPROVED CLIENT]** Run the unified workflow after Smoke is healthy:

```bash
task lite:security:assurance:qualify
```

Or use the already-authenticated registered operation:

```bash
task lite:security:assurance:preflight SUITE=standard
task lite:security:assurance:standard
```

The Standard profile target is 900 seconds and its maximum durable run lease
is 1,800 seconds. It permits only `PASSIVE` and `SAFE_ACTIVE` units.

## Additional coverage

Standard includes all Smoke scenarios plus:

- `policy-readiness` — current OPA status and revision consistency;
- `source-boundaries` — browser, shell, NATS, and user-media source guards;
- `attack-path-inventory` — every current `AP-*` has a bounded classification.

The phone run uses the existing `quick` Security path. The fixed DEV-PC lane
is invoked only through the tool manager and includes the registered Standard
tools shown in the [tool matrix](../reference/tool-matrix.md). This keeps
phone-native Security execution separate from DEV-PC static and DEV-PC live
runtime evidence.

## OPA requirement

Standard is blocked when OPA is not ready or its policy source/revision is not
current. Use only the supported source synchronization request:

```bash
task lite:security:assurance:policy-sync WAIT_SECONDS=120
task lite:security:assurance:preflight SUITE=standard
```

Never force allow, use the Qualification Owner profile, or bypass policy. An
OPA outage test is a separate fixed fault control; see [11 — fault recovery](11-fault-recovery-playbook.md).

## Resource and session behavior

Heavy tools are serialized by the registry/resource governor. Trivy cache,
shared SBOM, revision-bound fingerprints, and existing Security optimization
remain authoritative. The client renews its short session before expiry. If
the process disconnects, it reauthenticates and reattaches the existing run;
it does not create a second scanner operation.

## Review standard

Review the normalized findings, corroboration keys, scenario invariants, OPA
revision, worker correlation, checkpoint state, resource measurements, and
coverage statuses together. A tool result of `PASS` only means that tool
completed its contract; the suite verdict also considers security thresholds,
scenario results, and preflight.
