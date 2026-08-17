# Chat + Work Operating Workflow

This playbook turns ChatGPT Project sessions into a controlled engineering system for Pocket Lab Lite without requiring a local coding agent.

## Core principle

```text
Work = breadth, parallel read-only investigation, independent review
Chat = synthesis, exact implementation guidance, rapid debugging, explicit GitHub integration
Human = local execution, runtime mutation, merge/release authority
```

## Workflow A — Feature development

### A1. Work: impact discovery

Start from current target branch. Read `AGENTS.md` and `canonical-context.md`.

Ask Work to spawn only relevant specialists. Each uses Codebase Map / Knowledge / Architecture for orientation, then source/tests.

Deliverables:

- current behavior;
- affected components/files;
- architecture/trust implications;
- existing test ownership;
- security implications;
- docs/generated-output implications;
- unvalidated assumptions.

### A2. Work: test contract

Have a Test Reviewer define expected behavior before implementation:

```text
scenario
expected result/state
required evidence
existing test
new regression test
negative/failure case
```

### A3. Chat: synthesis

Chat reconciles reports and produces:

- Objective
- verified current behavior
- minimal files affected
- implementation sequence
- exact targeted patches/commands
- focused tests
- broader validation gates
- risks/rollback

Avoid broad rewrites when a narrow fix satisfies the contract.

### A4. Human: local application

Apply the patch in WSL2/Termux. Keep mutations explicit and inspect `git diff`.

### A5. Chat: rapid debug loop

For focused failures:

```text
run one command
→ paste exact output
→ diagnose one layer
→ apply smallest correction
→ rerun focused check
```

Do not jump to full-suite reruns until the focused failure is understood.

### A6. Work: adversarial review

Provide branch/diff plus validation output. Reviewer tries to disprove correctness and checks architecture, secrets, failure states, tests, edge compatibility and generated drift.

### A7. Chat: final integration

Resolve accepted findings, rerun relevant gates and prepare staging/commit/PR commands or explicit GitHub actions.

## Workflow B — Debugging a runtime/UI issue

### B1. Establish observed state

Record exact user-visible behavior and available evidence. Avoid assuming the layer at fault.

### B2. Parallel Work hypotheses

Split by ownership boundary. Example for device recovery:

- backend/fleet projection;
- NATS/command/evidence flow;
- node agent reconnect;
- supervisor/PM2 recovery;
- frontend state precedence;
- tests.

Each agent must say what evidence would falsify its hypothesis.

### B3. Chat root-cause synthesis

Chat ranks hypotheses by evidence and identifies the narrowest diagnostic or patch.

### B4. Validate recovery semantics

For device issues distinguish:

- running but disconnected;
- stopped and being repaired;
- stopped without supervisor;
- command undeliverable;
- stale evidence;
- remote access not ready.

UI must not collapse these states into generic Offline if current source supports a more truthful state.

### B5. Recovery guidance

If local/runtime recovery commands are needed, provide exact bounded commands and what output proves recovery. Never print secrets.

## Workflow C — CI failure

### C1. Chat/GitHub: locate first failed invariant

Inspect workflow/run/job/step and exact logs. Do not assume the final error message is the root cause.

### C2. Work: parallel analysis

Useful roles:

- CI/Determinism Reviewer;
- subsystem owner for the failed task;
- Documentation/Knowledge Reviewer for generated drift;
- Test Reviewer for flaky or environment-sensitive assertions.

### C3. Reconstruct ordering

For generated artifacts, explicitly map:

```text
canonical inputs
→ generator A
→ generator B
→ final projection
→ check
```

If a generator snapshots Git-tracked state, it must run after tracked-output generators that it models.

### C4. Chat: fix invariant, not symptom

Prefer:

- task-order/dependency fix;
- deterministic source/input fix;
- targeted regression test;
- environment parity fix.

Avoid:

- hand-editing generated outputs;
- excluding legitimate tracked inputs simply to make drift disappear;
- weakening assertions without proving the assertion was wrong.

### C5. Reproduce CI sequence locally

Run the same generate/check order when feasible, then push and inspect the new CI run.

## Workflow D — PR review

Use Work as an independent read-only reviewer even when Chat authored the patch.

Review dimensions:

1. architecture ownership;
2. security/trust changes;
3. correctness/failure states;
4. tests/negative cases;
5. Android/Termux/ARM64 impact;
6. generated docs/contracts;
7. operational/recovery impact;
8. release impact.

Rank findings by severity and cite exact paths/lines where possible.

Chat then accepts/rejects each finding with evidence and supplies targeted fixes.

## Workflow E — Maintenance audit

Run periodically or before a large development phase. Spawn independent Work reviewers for:

- stale/failing/skipped tests;
- unused/deprecated tasks;
- documentation freshness/drift;
- generated-output ownership;
- dependency/security changes;
- architecture deviations;
- TODO/FIXME inventory;
- recovery/runbook gaps;
- Codebase Map structural delta.

Output findings only. Convert selected findings into separate focused branches/PRs rather than one giant cleanup.

## Workflow F — Release readiness

Use `maintenance-release.md`. Work reviewers independently inspect source delta, CI/validation, security, runtime compatibility, docs/release evidence and artifacts. Chat reconciles evidence. Human authorizes promotion/tag/release.

## Efficient context handling

### Inside the existing Pocket-Lab-App Project

Do not repeat the whole project history in every session. Start with:

1. `AGENTS.md`;
2. `canonical-context.md`;
3. current branch/PR/issue;
4. relevant generated orientation views;
5. only the handover needed for the specific continuation.

### Between Work and Chat

Use `handoff-template.md`. A handoff should contain verified evidence and unresolved questions, not a transcript.

### Between long sessions

Create a fresh handoff when the current session accumulates too much historical context. The new session still verifies the repo first.

## Mutation control

Work mode in this Pocket Lab Lite workflow is deliberately read-only.

Chat may perform GitHub write operations only when the user explicitly asks for the concrete action. Local filesystem/runtime commands remain human-executed. Never assume authorization to:

- commit/push/merge;
- tag/release;
- promote evidence;
- remove devices;
- restart production services;
- rotate credentials;
- alter live Termux state.

## Completion rule

A task is not `VERIFIED complete` because a patch was written or a Work agent approved it. Completion requires the applicable validation evidence and, for PR/release work, required CI/integration state.
