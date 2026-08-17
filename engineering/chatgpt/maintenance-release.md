# Pocket Lab Lite Maintenance, PR and Release Playbook

This playbook uses Work for broad read-only review and Chat for synthesis, targeted fixes and explicitly authorized GitHub operations.

## Recurring maintenance audit

Run a structured audit periodically or before a major development phase.

Recommended Work reviewers:

- Test Reviewer — stale/skipped/flaky coverage and missing negative tests.
- Documentation/Knowledge Reviewer — freshness, broken mappings, generated drift and Codebase Map health.
- CI/Determinism Reviewer — fragile task ordering, environment assumptions and generator fixed-point risks.
- Security Reviewer — trust-boundary drift, identity/invite risks, secret handling and control gaps.
- Architecture Guardian — new coupling, desktop-only assumptions, runtime ownership drift.
- Device Runtime Reviewer — recovery/reconnect/runbook gaps when runtime code changed.

Output findings only. Rank them by severity/impact and convert selected findings into focused issues/branches/PRs. Avoid one giant cleanup PR.

## PR preparation

Before opening a PR:

1. verify branch is based on current intended base;
2. inspect `git status --short`;
3. remove unrelated/unwanted artifacts;
4. run focused tests and the relevant broad gates;
5. run `git diff --check`;
6. inspect staged files with `git diff --cached --stat`;
7. ensure generated outputs were produced from canonical sources;
8. ensure Codebase Map/docs projections are current when tracked files affect them.

PR description should separate:

- summary/objective;
- architecture impact;
- files/areas changed;
- validation evidence;
- known warnings/limitations;
- security/recovery implications;
- what remains unvalidated.

## Independent PR review

Use Work to review the pushed branch/PR read-only. Give it the objective and validation evidence but instruct it to challenge assumptions.

Required review dimensions:

- architecture/trust boundaries;
- security/identity/secrets;
- failure/recovery semantics;
- tests and negative cases;
- Android/Termux/ARM64 impact;
- generated contracts/docs;
- CI/determinism;
- operational/release impact.

Chat reconciles findings and supplies targeted fixes. The human controls local application and push.

## CI failure handling

When CI fails:

1. inspect the exact run/job/step/log;
2. identify the first meaningful failure;
3. use Work specialists if the failure crosses layers;
4. compare CI task/generator order with local order;
5. fix the invariant rather than generated symptoms;
6. add a regression test if the failure exposes an ordering, environment or ownership invariant;
7. rerun focused local reproduction;
8. push only after the focused failure is resolved;
9. inspect the replacement CI run.

Do not weaken a check just to make CI green unless the check itself is proven incorrect.

## Release-readiness review

Before release, run parallel Work reviews with non-overlapping scopes.

### Source delta reviewer

Inspect changes since the prior release and classify runtime/API/UI/docs/security impact.

### Validation reviewer

Confirm required local/CI gates and identify any missing or stale evidence.

### Security reviewer

Inspect threat/control/supply-chain/release-evidence implications. Missing security evidence is `UNVALIDATED`, not PASS.

### Runtime compatibility reviewer

Check Android/Termux, ARM64, PM2, NATS, Tailscale, node-agent/supervisor and recovery implications for changed runtime paths.

### Documentation/release reviewer

Check generated documentation, release delta, Knowledge/Codebase Map, architecture and release notes/evidence.

### Artifact reviewer

Check the repository's current release workflow and expected assets, including `dist.zip` where required. Ensure development-only artifacts, raw evidence and secrets are excluded.

## Release readiness table

The Chat coordinator reconciles reviewers into:

| Area | Status | Evidence | Blocker/next action |
| --- | --- | --- | --- |
| Source delta | READY/BLOCKED/UNVALIDATED | ... | ... |
| Tests/CI | READY/BLOCKED/UNVALIDATED | ... | ... |
| Security | READY/BLOCKED/UNVALIDATED | ... | ... |
| Termux/ARM64 runtime | READY/BLOCKED/UNVALIDATED | ... | ... |
| Documentation | READY/BLOCKED/UNVALIDATED | ... | ... |
| Release artifacts | READY/BLOCKED/UNVALIDATED | ... | ... |

Overall release is not ready while any required area is `BLOCKED` or `UNVALIDATED`.

## Human-controlled release actions

Tags, promotions, GitHub releases, live service actions and evidence promotion require explicit user intent. Work agents do not perform them. Chat should only perform GitHub writes when the user explicitly requests the concrete operation.

Preserve repository release hygiene:

- clean `main`;
- merged reviewed PRs;
- feature branches removed when appropriate;
- no `.orig`, `.rej`, `.pytest_cache`, accidental `dist` or unrelated artifacts;
- annotated date-based tag when required by current release process;
- verified GitHub release assets, including `dist.zip` where required.

## Maintenance signals worth reviewing

Use Codebase Map structural delta and Documentation Platform evidence to identify, not automatically modify:

- new/removed directories and ownership shifts;
- files with weak test relationships;
- architecture/trust-boundary changes;
- generated artifact growth/drift;
- documentation freshness gaps;
- new workflows/tasks;
- new runtime dependencies;
- TODO/FIXME accumulation;
- recovery paths with weak evidence;
- security-control mapping changes.

These signals are triage inputs, not automatic risk scores.

## Rollback discipline

For risky changes, define rollback before merge. Prefer reversible changes and explicit recovery steps. For runtime/release work, preserve last-known-good and the repository's existing rollback/evidence model; never invent a rollback path that current source does not implement.
