# Codex Subagent Routing and Prompt Examples

This guide is the canonical Pocket Lab Lite reference for delegating bounded
work from the primary Codex thread to repository-owned named subagents.

Root `AGENTS.md` remains authoritative. Subagents are selective specialists,
not an automatic swarm. Choose the narrowest specialist that matches the
problem, prefer 1–3 subagents per delegation wave, and keep write-heavy work
serialized unless file ownership is demonstrably independent.

## Engineering lifecycle

```text
Work Mode
  -> read-only investigation / design / architecture
  -> bounded engineering handoff

Chat Mode
  -> verifies current GitHub source
  -> reconciles Work findings
  -> defines execution contract
  -> manages branch / PR / CI / merge lifecycle when explicitly requested

Codex primary
  -> normally Terra / medium
  -> owns the local candidate state
  -> delegates bounded specialist work selectively
  -> reconciles subagent output

Codex subagents
  -> exploration / implementation / tests / debugging / review as routed

Independent final review
  -> pl_final_reviewer
  -> optional independent Work review for important changes

Chat Mode
  -> reconciles final evidence
  -> manages GitHub qualification and explicit merge/release lifecycle
```

Human authority remains required for commit policy where applicable, PR
readiness, merge authorization, release, live Server Phone/Termux mutation,
destructive cleanup/reset and credential/secret changes.

## Cost and access summary

| Agent | Model / effort | Access | Best use |
| --- | --- | --- | --- |
| `pl_docs_explorer` | Luna / low | read-only | documentation source/generator mapping |
| `pl_docs_builder` | Terra / medium | workspace-write | approved canonical docs/generator implementation |
| `pl_docs_reviewer` | Terra / medium | read-only | documentation semantics and generated ownership review |
| `pl_validation_reader` | Luna / low | read-only | CI/test/log/generated-diff reduction |
| `pl_final_reviewer` | Terra / high | read-only | independent final candidate review |
| `pl_security_architect` | GPT-5.6 / high | read-only | unresolved security/authorization/trust ambiguity |
| `pl_uiux_engineer` | Terra / medium | workspace-write | PWA and Documentation Platform UI/UX implementation |
| `pl_edge_runtime_debugger` | Terra / medium | read-only | edge/runtime outage diagnosis |
| `pl_test_engineer` | Terra / medium | workspace-write | focused regression/test implementation |
| `pl_api_contract_guardian` | Terra / medium | read-only | API/contract/parity review |
| `pl_maintenance_scout` | Luna / low | read-only | bounded repository hygiene scouting |

Do not delegate merely because an agent exists. The four-thread configuration
is a budget ceiling, not a utilization target.

---

## `pl_docs_explorer`

**Use when:** the primary thread needs a low-cost map from a documentation
question to canonical source, generator, generated projection and tests.

**Do not use when:** implementation is already approved and the owning files
are known; use `pl_docs_builder` instead.

**Cost / access:** Luna / low, read-only.

**Concise prompt:**

```text
Map the current source ownership for <documentation capability>.
Identify implementation proof, canonical metadata/source, generator,
generated outputs and tests. Do not edit. Return a concise evidence table.
```

**Pocket Lab Lite example:**

```text
Map how the Production Threat Model page is generated today.
Trace canonical threat/security inputs -> generator -> generated contracts/docs
-> validation. Verify whether any browser-time monitoring is involved.
Do not edit.
```

**Expected output:** compact evidence table with exact paths and
`VERIFIED`/`MISSING`/`UNVALIDATED` labels.

**Primary Codex responsibility:** decide whether the mapping is sufficient,
resolve conflicting evidence and authorize any later implementation scope.

---

## `pl_docs_builder`

**Use when:** an already-approved Documentation Platform increment requires
canonical metadata, generator, navigation-source or test changes.

**Do not use when:** the task is still discovery/design, or when the proposed
fix is a manual edit to `docs/generated/**` or `contracts/generated/**`.

**Cost / access:** Terra / medium, workspace-write.

**Concise prompt:**

```text
Implement the approved <documentation increment> through canonical owners.
Regenerate with repository tasks, add focused tests, inspect generated diff,
and report exact validation. Do not commit or touch live runtime.
```

**Pocket Lab Lite example:**

```text
Implement the approved new Codebase Map relationship label through its
canonical generator and tests. Do not hand-edit generated Markdown or JSON.
Run the focused docs generator/check and report the generated consequences.
```

**Expected output:** files changed, canonical owner, generated consequences,
focused validation, residual failures.

**Primary Codex responsibility:** keep scope bounded, reconcile generated
diffs, run broader gates when needed and own the final candidate.

---

## `pl_docs_reviewer`

**Use when:** documentation semantics, stale claims, cross-links, glossary,
journeys, traceability or generated ownership need independent review.

**Do not use when:** the task is purely source mapping (`pl_docs_explorer`) or
approved implementation (`pl_docs_builder`).

**Cost / access:** Terra / medium, read-only.

**Concise prompt:**

```text
Review <documentation surface> against current source/tests.
Find stale claims, ownership errors, broken semantic links and deterministic
generation risks. Do not edit. Rank findings by correctness impact.
```

**Pocket Lab Lite example:**

```text
Review Identity & Access and Rules coverage across Knowledge Graph,
feature journeys, glossary, API-to-UI trace and limitations.
Verify every claim against current source/tests and identify canonical owners.
```

**Expected output:** ranked findings with canonical owner and expected
generated consequence.

**Primary Codex responsibility:** accept/reject findings with evidence and
delegate only approved fixes.

---

## `pl_validation_reader`

**Use when:** pytest, Vitest, Playwright, Taskfile, GitHub Actions, build,
docs, contract/parity, generated-drift or runtime diagnostic output is noisy.

**Do not use when:** the root cause is already proven and a code/test fix is
ready to implement.

**Cost / access:** Luna / low, read-only.

**Concise prompt:**

```text
Analyze this validation failure. Find the first failing invariant, exact
task/test/job, earliest causal error, likely owner, failure classification
and smallest next diagnostic. Do not edit or reproduce the whole log.
```

**Pocket Lab Lite example:**

```text
Analyze this task lite:check failure.
Classify it as implementation defect, generated drift, stale expectation,
fixed-point/order issue, environment/toolchain, transient infrastructure or
unrelated baseline. Return only the first proven failure and next diagnostic.
```

**Expected output:** concise failure reduction with proven vs hypothesized root
cause and one next diagnostic.

**Primary Codex responsibility:** run/interpret the next diagnostic, choose the
fixing specialist and avoid weakening valid gates.

---

## `pl_final_reviewer`

**Use when:** a final candidate needs an independent adversarial review before
PR/merge qualification.

**Do not use when:** implementation is still actively changing or when a
narrow domain reviewer can resolve an early question more cheaply.

**Cost / access:** Terra / high, read-only.

**Concise prompt:**

```text
Independently review the final candidate diff against current main.
Try to disprove correctness. Adapt checks to changed docs/UI/API/runtime/tests.
Lead with concrete findings ranked by severity. Do not edit.
```

**Pocket Lab Lite example:**

```text
Changed areas include React UI, backend API contract and Playwright tests.
Check architecture boundaries, mobile/accessibility, authorization,
compatibility, negative coverage, Android/Termux behavior, redaction and
validation evidence. Do not edit.
```

**Expected output:** severity-ranked findings, evidence paths, reviewed
surfaces and residual unvalidated risk.

**Primary Codex responsibility:** reconcile findings, fix accepted issues,
rerun validation and keep final candidate ownership.

---

## `pl_security_architect`

**Use when:** a question remains unresolved around Identity, sessions,
WebAuthn, authorization, OPA, approvals, exceptions, trust boundaries,
policy lifecycle or Threat Model architecture.

**Do not use when:** the work is ordinary repository search, log reduction,
mechanical implementation or a non-security UI concern.

**Cost / access:** GPT-5.6 / high, read-only.

**Concise prompt:**

```text
Resolve this security architecture ambiguity from current source/tests/contracts.
Do not implement code. Identify the controlling trust boundary, fail-closed
requirements, attack/control implications and safest architecture decision.
```

**Pocket Lab Lite example:**

```text
Review whether this OPA activation change preserves FastAPI authorization
ownership, loopback-only OPA decision support, exact revision binding,
readiness verification and rollback-to-known-good semantics.
Do not edit or reopen unrelated Identity/Rules scope.
```

**Expected output:** a small number of architecture/security decisions or
concrete findings requiring high judgement.

**Primary Codex responsibility:** translate accepted decisions into bounded
implementation/test work and preserve human authority for sensitive actions.

---

## `pl_uiux_engineer`

**Use when:** approved UI/UX work spans responsive layout, mobile/touch,
keyboard accessibility, dark mode, loading/error/degraded states, shared
presentation primitives or browser regression coverage.

**Do not use when:** the task requires backend security semantic redesign,
direct runtime execution, or API behavior changes that have not been approved.

**Cost / access:** Terra / medium, workspace-write.

**Concise prompt:**

```text
Implement the approved <UI surface> UX increment.
Keep existing FastAPI-driven state and architecture semantics.
Use shared primitives, add focused presentation regression coverage, and
report desktop/mobile/accessibility/validation results.
```

**Pocket Lab Lite example:**

```text
Review and implement the approved Devices-tab responsive UX increment.

Focus only on:
- mobile stacking;
- touch target sizing;
- stopped/repairing/offline visual distinction;
- dark-mode readability;
- existing FastAPI-driven state.

Do not modify API or runtime semantics.
Add focused browser regression coverage and report changed files,
responsive result, accessibility result and validation.
```

**Expected output:** files changed, UX invariant improved, desktop/mobile
result, accessibility result, validation and residual limitations.

**Primary Codex responsibility:** ensure UI changes remain within existing API
contracts, coordinate any separate test/API review and own final diff.

---

## `pl_edge_runtime_debugger`

**Use when:** a device/runtime outage crosses FastAPI, NATS/JetStream, PM2,
node agent, supervisor, Caddy, Tailscale, heartbeats or command delivery.

**Do not use when:** a live restart/mutation is being requested; this agent is
diagnostic only.

**Cost / access:** Terra / medium, read-only.

**Concise prompt:**

```text
Diagnose <runtime symptom> from repository/runtime evidence only.
Separate Tailscale, NATS, agent, supervisor, heartbeat, command and identity
failure modes. Do not restart anything. Return first proven failure, next
diagnostic, safe fix and verification.
```

**Pocket Lab Lite example:**

```text
Diagnose why secondary device node-2 appears Offline.

Distinguish:
- tailscaled readiness;
- Tailnet IP;
- NATS listener/reachability;
- secondary POCKETLAB_NATS_URL;
- PM2 node agent;
- supervisor;
- last heartbeat.

Do not restart anything.
Return first proven failure, next diagnostic, safe fix and verification.
```

**Expected output:** `WHAT HAPPENED`, `WHY`, `FIRST PROVEN FAILURE`,
`EXACT NEXT DIAGNOSTIC`, `SAFE FIX`, `VERIFICATION`,
`RECOVERY IF FIX FAILS`.

**Primary Codex responsibility:** decide whether evidence justifies a code
change or human-authorized runtime recovery and keep mutation explicit.

---

## `pl_test_engineer`

**Use when:** a proven invariant/regression needs the smallest deterministic
test at the correct layer.

**Do not use when:** the expected behavior itself is still ambiguous or a test
would need to weaken an existing legitimate assertion.

**Cost / access:** Terra / medium, workspace-write.

**Concise prompt:**

```text
Add the smallest deterministic regression test for <invariant>.
Choose the correct pytest/Vitest/Playwright/contract/generator layer.
Do not weaken existing assertions. Run the focused test and report exact result.
```

**Pocket Lab Lite example:**

```text
Add the smallest regression test proving that a stale Rules continuation
cannot be consumed twice.

Use the existing P3 approval/continuation test layer.
Do not change production behavior unless required by an already-proven defect.
Run the focused test and report exact command/result.
```

**Expected output:** invariant, test files, selected test layer and rationale,
exact command, PASS/FAIL and remaining coverage gap.

**Primary Codex responsibility:** confirm the test reflects the approved
contract and coordinate any required production fix separately.

---

## `pl_api_contract_guardian`

**Use when:** FastAPI models, `/api/lite/*`, OpenAPI, AsyncAPI, frontend
consumers, generated contracts, reason codes or runtime parity may have drifted.

**Do not use when:** the task is to implement a known UI or backend change;
this agent reviews and traces only.

**Cost / access:** Terra / medium, read-only.

**Concise prompt:**

```text
Review <API surface> across FastAPI source, schema/contracts, frontend
consumer, generated projection and parity tests. Do not edit.
Return exact source -> contract -> frontend -> test drift and rank findings.
```

**Pocket Lab Lite example:**

```text
Review the current /api/lite/policy response contract against FastAPI source,
OpenAPI, generated parity contracts and frontend consumers.

Determine whether fields are stale, missing, incorrectly optional or
frontend-only expectations. Do not edit.
Return source -> contract -> frontend -> test traceability and ranked findings.
```

**Expected output:** traceability chain for each finding, exact drift,
compatibility impact and redaction concern if applicable.

**Primary Codex responsibility:** choose the authoritative layer to fix and do
not mutate correct backend semantics to satisfy stale projections.

---

## `pl_maintenance_scout`

**Use when:** a bounded low-cost inventory is needed for stale generated
artifacts, obsolete compatibility paths, duplicate config, accidental
artifacts, dependency drift, dead tasks or stale references.

**Do not use when:** the instruction is broad "clean everything" work or when
deletion is already authorized without reference verification.

**Cost / access:** Luna / low, read-only.

**Concise prompt:**

```text
Perform a targeted hygiene review for <scope>.
Verify references/tests/generator ownership before calling anything obsolete.
Do not delete or edit. Return verified candidates, owners, safe actions and
validation commands only.
```

**Pocket Lab Lite example:**

```text
Perform a targeted repository hygiene review for generated/test artifacts and
stale compatibility files introduced during the last documentation increments.

Verify references before calling anything obsolete.
Do not delete files.
Return only verified candidates, owners, safe cleanup actions and validation
commands.
```

**Expected output:** prioritized blocks of `VERIFIED ISSUE`, `IMPACT`, `OWNER`,
`SAFE ACTION`, `VALIDATION COMMAND`.

**Primary Codex responsibility:** select individual cleanup candidates, obtain
authorization where needed and keep cleanup branches focused.

---

## Delegation patterns

Prefer one specialist when the task has one clear owner. Use two or three in a
wave only when their work is genuinely independent, for example:

```text
pl_api_contract_guardian (read-only contract trace)
+ pl_test_engineer (focused regression)
```

or:

```text
pl_edge_runtime_debugger (read-only diagnosis)
+ pl_validation_reader (log reduction)
```

For implementation followed by independent review, serialize:

```text
pl_uiux_engineer or pl_docs_builder
-> focused validation
-> pl_final_reviewer
```

Do not send identical broad prompts to several agents unless independent
review is the explicit objective. Do not spawn an agent for every category.
