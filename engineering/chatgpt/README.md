# ChatGPT Engineering Operating Model

This directory defines how Pocket Lab Lite uses ChatGPT **Chat** and **Work** inside the existing Pocket-Lab-App Project. When available, Codex provides the local repository implementation and validation surface described in `engineering/codex/`.

The model deliberately separates **parallel reasoning** from **repository/runtime mutation**:

```text
Work mode
read-only parallel specialists
        ↓
verified findings + test design
        ↓
Chat mode
coordinator + synthesis + design reasoning
        ↓
Codex local implementation/validation
        ↓
validation evidence
        ↓
Work independent review
        ↓
Chat final integration / GitHub operations
        ↓
PR → CI → explicit human merge/release decision
```

## Which mode to use

Use **Work** when breadth and independent perspectives matter:

- repository orientation;
- parallel subsystem investigations;
- architecture/change-impact analysis;
- competing root-cause hypotheses;
- security review;
- test strategy and negative-test design;
- CI triage;
- PR/diff review;
- maintenance audit;
- release-readiness assessment.

Use **Chat** when a single controlled integration thread is better:

- reconcile Work findings;
- choose one architecture-safe plan;
- produce exact Python/shell patches;
- iterate rapidly on failing tests/logs;
- interpret validation output;
- prepare exact Git commands;
- perform explicit GitHub actions when requested;
- synthesize final PR/release evidence.

Use **Chat + Work** for substantial changes. Add Codex when local repository execution is available.

## Two supported workflows

Without Codex:

~~~text
Work investigation/review
→ Chat synthesis and implementation guidance
→ human-controlled local execution
→ validation
~~~

With Codex:

~~~text
Work investigation/review
→ Chat synthesis and design decisions
→ Codex local implementation/validation
→ Work independent review
→ Chat/GitHub integration
→ explicit user merge/release decision
~~~

Work remains primarily read-only investigation and review. Chat remains the coordinator and synthesizer. Codex is the preferred local repository execution surface when available. Humans retain control of sensitive, remote, live and destructive actions. Chat + Work remain fully supported without Codex.

## Session startup

For a new Chat, Work or Codex session inside the Pocket-Lab-App Project:

1. Read root `AGENTS.md`.
2. Read `canonical-context.md`.
3. Start with current `main`/target branch, not an old handover.
4. Use Codebase Map / Knowledge / Architecture views for orientation.
5. Open the actual source and tests before concluding behavior exists.
6. Label anything not proven from the current repository.

## Standard engineering loop

### 1. Work investigation

Ask Work to spawn only the specialists relevant to the change. Do not ask every agent to solve everything.

Each specialist returns:

- verified files inspected;
- verified current behavior;
- evidence;
- likely root cause or impact;
- affected tests;
- risks;
- unvalidated assumptions;
- minimal recommendation.

### 2. Chat synthesis

Provide the Work report to a Chat session and ask it to:

- reconcile disagreements;
- remove unsupported assumptions;
- preserve architecture boundaries;
- define files affected;
- define a test contract;
- produce one minimal patch plan.

### 3. Controlled local implementation

When Codex is available, it performs targeted local edits and validation. Otherwise Chat supplies targeted edits for human-controlled execution. Prefer:

- Python one-shots;
- small patch hunks;
- exact commands;
- focused new tests.

Codex performs local implementation and validation when available; otherwise the human applies and executes the guidance locally. Do not replace this with unrestricted background mutation. The human remains the authority for remote, destructive, live-runtime and release actions.

### 4. Focused validation

Run the smallest checks that prove the edited behavior, then broaden according to `validation-matrix.md`.

### 5. Independent Work review

Give the resulting branch/diff and validation evidence to a Work reviewer. The review instruction should be adversarial: try to disprove correctness, find architectural violations, missing negative tests, security gaps, edge/Termux incompatibilities, generated drift and unsupported claims.

### 6. Chat debugging/integration

Bring review findings or failing output back to Chat for short targeted fix/retest loops.

### 7. PR/CI

Use Chat/GitHub deliberately for PR inspection, CI diagnosis and explicit write actions. Do not merge merely because local checks pass; CI and required evidence must agree.

## Useful starting prompts

### Work — parallel investigation

```text
Work against current repository state. Repo source is authoritative.
Read AGENTS.md and engineering/chatgpt/canonical-context.md first.

Investigate <problem> without modifying the repository.
Use the Codebase Map and relevant generated views for orientation, then inspect actual source/tests.
Spawn the smallest useful set of specialist agents.

Each specialist must report:
- VERIFIED files/evidence
- current behavior
- likely root cause/impact
- affected tests
- risks
- UNVALIDATED assumptions
- minimal recommendation

Do not produce a final implementation until the reports are reconciled.
```

### Chat — implementation coordinator

```text
Treat the attached Work report as investigation evidence, not source of truth.
Verify claims against current repository content when possible.
Reconcile contradictions and produce one minimal Pocket Lab Lite-safe implementation.

Return:
Objective
Files affected
Verified root cause/current behavior
Implementation plan
Exact targeted patch/commands
Validation commands and expected output
Risks
Rollback
What remains unvalidated
```

### Work — independent reviewer

```text
Review this change as an adversarial Pocket Lab Lite maintainer.
Do not assume the implementation or its author's explanation is correct.
Inspect the diff plus relevant source/tests and try to find:
- architecture/trust-boundary violations
- missing negative/regression tests
- incorrect state/evidence semantics
- secret exposure
- hidden side effects
- Android/Termux or ARM64 regressions
- generator nondeterminism/drift
- release/operations risks
Return evidence-backed findings ranked by severity.
```

### Chat — CI debugger

```text
Analyze this failing CI output against the current workflow/task/source ordering.
Separate symptom from root cause.
Prefer the smallest deterministic fix and add a regression test when the failure exposes an invariant.
Do not fix generated drift by excluding legitimate tracked inputs or hand-editing generated outputs.
```

## Documents

- `canonical-context.md` — compact context every session can load.
- `architecture-contract.md` — invariants that changes must preserve.
- `agent-roles.md` — specialist role definitions.
- `operating-workflow.md` — feature/debug/CI/maintenance workflows.
- `validation-matrix.md` — which validation gates apply.
- `handoff-template.md` — portable Work↔Chat/session handoff.
- `maintenance-release.md` — recurring maintenance and release readiness.

Root `AGENTS.md` is the controlling repository policy when anything here conflicts.
