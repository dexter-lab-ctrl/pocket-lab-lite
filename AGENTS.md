# Pocket Lab Lite Agent Engineering Contract

`AGENTS.md` is the repository-level operating contract for AI-assisted engineering in Pocket Lab Lite. It applies to ChatGPT Chat, ChatGPT Work, Codex, and humans using AI-assisted engineering output.

## Source-of-truth order

Use sources in this order:

1. Current Git-tracked repository source and tests.
2. Canonical contracts, schemas, architecture metadata and generated evidence committed to the repository.
3. Generated Documentation Platform views such as Codebase Map, Knowledge Graph, Architecture, API-to-UI Trace and Change Impact Advisor.
4. `engineering/chatgpt/` operating guidance.
5. Project/session handovers and conversation context.
6. Assumptions only when unavoidable, and label them `UNVALIDATED`.

Never treat a handover, roadmap item, old chat or generated explanation as proof that implementation exists. Verify against current source.

## Status vocabulary

Use these labels when reporting engineering state:

- `VERIFIED` — directly confirmed from current source, tests, generated evidence or validation output.
- `INFERRED` — a reasoned conclusion from verified evidence; state the evidence.
- `PATCH-PROVIDED` — an edit or command has been supplied but not yet validated.
- `MISSING` — expected implementation/evidence is absent from current source.
- `PLANNED` — explicitly documented future work; never present it as implemented.
- `OPTIONAL` — not required for correctness or the default Lite experience.
- `UNVALIDATED` — not yet proven by commands, tests or runtime evidence.

Never claim completion without validation output.

## Architecture contract

Preserve the edge-first control flow:

```text
React/Vite PWA
    ↓
Caddy same-origin proxy
    ↓
FastAPI /api/lite/*
    ↓
NATS / JetStream
    ↓
worker / node agent / supervisor
    ↓
events, heartbeats, sanitized evidence
    ↓
FastAPI prepared reads
    ↓
UI
```

Hard boundaries:

- Frontend never connects directly to NATS.
- Frontend never executes shell commands.
- Frontend never stores backend secrets.
- FastAPI remains the control API.
- Workers, node agents and supervisors own execution and recovery.
- Bootstrap scripts are backend-generated and must not expose secrets.
- Read APIs must remain free of hidden runtime side effects.
- Lifecycle, recovery, approval and blocked-action outcomes remain observable and auditable.
- Preserve Android/Termux, ARM64, Ubuntu/WSL2 development and low-power/self-hosted operation.

Do not reintroduce frontend shell execution, direct browser NATS access, browser-held backend secrets, hardcoded deployment IPs/URLs/FQDNs, `BaseHTTPRequestHandler`, `/api/action/update`, or legacy sync/intent patterns.

See `engineering/chatgpt/architecture-contract.md` for the expanded contract.

## ChatGPT + Work + Codex operating model

Pocket Lab Lite uses ChatGPT **Chat**, ChatGPT **Work**, and **Codex** as complementary engineering surfaces. The repository remains the ultimate source of truth, and this root contract wins when guidance conflicts.

### ChatGPT Work — breadth, parallelism and independent review

Use Work for read-only repository investigation and parallel specialist analysis. Work agents may inspect GitHub/repository sources and produce findings, plans, test designs and reviews. They do not own repository mutation in this workflow.

Typical Work tasks:

- parallel architecture/backend/frontend/runtime/security investigations;
- change-impact analysis;
- root-cause exploration across competing hypotheses;
- test-plan and adversarial-test design;
- pull-request/diff review;
- CI-failure triage;
- documentation, security and maintenance audits;
- release-readiness review.

Work agents must report evidence, not merely conclusions.

### ChatGPT Chat — synthesis, design and coordination

Use Chat for:

- reconciling Work-agent findings;
- selecting the smallest architecture-safe implementation;
- implementation planning and exact targeted patches and Python/shell one-shots;
- rapid test-failure/debugging loops;
- validation interpretation;
- GitHub action coordination when the user explicitly requests it;
- final PR/release synthesis.

### Codex — local repository implementation and validation

Use Codex for local repository inspection, targeted source/test edits, generators, builds, focused and broad validation, diff inspection and local Git inspection. Codex is the preferred local repository execution surface when available; it is not a competing architecture authority or a replacement for Chat/Work reasoning and independent review. Codex may perform ordinary local non-destructive implementation and validation operations inside the explicitly opened repository.

### Human — explicit authority for sensitive actions

Human explicit intent is required before Codex performs commits, pushes, merges, tags, release publication, live Server Phone mutation, Termux production mutation, destructive cleanup/reset, or secret/credential changes. Chat and Work do not grant that authority implicitly.

Detailed usage is in `engineering/chatgpt/operating-workflow.md`.

## Default change lifecycle

For medium or large work, use these phases:

1. **Read-only investigation** — Work agents inspect Codebase Map and relevant source.
2. **Coordinator synthesis** — Chat reconciles verified findings and rejects unsupported assumptions.
3. **Test contract** — define success, negative cases and regression coverage before implementation.
4. **Targeted implementation** — Codex applies the smallest architecture-safe local edits when available; Chat supplies synthesis and coordination.
5. **Independent review** — Work reviewer tries to disprove correctness and find architectural/security/test gaps.
6. **Validation** — run focused checks, then the appropriate broader gates.
7. **PR/CI** — inspect GitHub checks; fix root cause rather than generated symptoms.
8. **Merge/release** — only after evidence is complete and the user explicitly requests the action.

Small, low-risk edits may compress phases, but never skip source verification or required validation.

## Repository orientation

Start broad investigations with the generated Documentation Platform, then inspect source:

- `docs/generated/development/knowledge/codebase-map.md` — Git-tracked structure, ownership, symbols, Uses/Used-by and bounded impact.
- `docs/generated/development/knowledge/repository-map.md` — reverse source-to-Knowledge lookup.
- `docs/generated/enterprise/knowledgebase/knowledge-graph.md` — semantic relationships.
- `docs/generated/production/architecture/index.md` — runtime/system architecture.
- `docs/generated/enterprise/reference/api-ui-trace.md` — UI → API → execution → evidence traces.
- `docs/generated/enterprise/reference/change-advisor.md` — deterministic potential-impact guidance.

Generated views are orientation/evidence projections; source code and tests remain authoritative.

The Codebase Map inventories Git-known paths (`git ls-files`) and infers directories. A new file must be Git-visible before the map can include it. During development use `git add -N -- path/to/new-file` when you want visibility without staging its contents.

## Specialist roles

Use specialists defined in `engineering/chatgpt/agent-roles.md`:

- Architecture Guardian
- Backend/API Reviewer
- Device Runtime Reviewer
- Frontend State Reviewer
- Security Reviewer
- Test Reviewer
- Documentation/Knowledge Reviewer
- CI/Determinism Reviewer
- Release Readiness Reviewer

For substantial changes, separate builder and reviewer perspectives. The implementation author should not be the only reviewer.

## Change response format

For implementation changes, report:

- Objective
- Files affected
- Verified current behavior
- Implementation plan
- Targeted patch/commands
- Validation commands
- Expected output
- Risks
- Rollback guidance when useful
- Enterprise value
- What was and was not validated

For debugging, report:

- What happened
- Why
- Exact fix
- Verification
- Recovery steps

Use `engineering/chatgpt/handoff-template.md` when moving work between Work and Chat sessions.

## Validation policy

Prefer the smallest relevant checks first, then broader gates. Common commands include:

```bash
python3 -m py_compile <changed-python-files>
bash -n <changed-shell-files>
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q <focused-tests>
npm run build
task lite:api:check
task lite:docs:check
task lite:check
git diff --check
```

For documentation/codebase changes, remember that Git-tracked files can change Codebase Map fingerprints. Full docs generation must finish before the Codebase Map final projection:

```bash
task lite:docs:generate
task lite:docs:check
```

For browser behavior use the repo-owned Playwright tasks/configuration. For live device issues also validate, as relevant:

- `pm2 status` and bounded PM2 logs;
- Tailscale/tailscaled health;
- Tailnet IPv4 readiness;
- NATS listener/connectivity, including secondary-device connectivity;
- node-agent and supervisor states;
- fresh heartbeat after reconnect.

See `engineering/chatgpt/validation-matrix.md`.

## Device onboarding and identity safety

Preserve:

```text
invite creation
→ audit evidence
→ copyable backend-generated bootstrap command
→ identity guard
→ safe acceptance
→ env write
→ node agent start
→ supervisor start
→ heartbeats appear in Devices
```

Before issuing an invite, verify duplicate names/identities across active devices, stale records and pending/accepted invites; matching must be case-insensitive and separator-insensitive. Protect server host names. Block another device's invite on an already enrolled device. Identity mismatch fails closed: no env overwrite and no PM2 restart. Repair/rejoin must be explicit. Blocked consumption generates sanitized audit evidence.

Never print tokens, hashes, passwords, API keys, invite secrets or backend secrets.

## Device/recovery semantics

Keep user-visible states truthful and distinct, including Online, Joining, Waiting, Offline, Agent stopped, Repairing, Remote access not ready and Protected server host.

Recovery ownership:

- running but disconnected → reconnect/watchdog path;
- stopped agent → supervisor recovery;
- stopped without supervisor → UI recovery guidance, not pretend success.

Restart Agent progress must represent real multi-step state and distinguish repairing from undeliverable commands.

## Generated documentation rules

- Do not manually edit `docs/generated/**` or `contracts/generated/**` as the implementation source.
- Change canonical source/generators, then regenerate.
- Keep generated outputs deterministic and sanitized.
- Do not introduce network/runtime polling into static generated docs unless the architecture explicitly requires it.
- Codebase Map generation must remain after all generators that mutate tracked repository outputs.

## Git and release hygiene

- Keep `main` clean.
- Use focused branches and small reviewable PRs.
- Remove `.orig`, `.rej`, `.pytest_cache`, accidental `dist`, and unwanted artifacts.
- Do not stage unrelated changes.
- Run `git diff --check` before commit.
- Merge only after required checks pass.
- Delete feature branches after merge when appropriate.
- Release through the repository's validated release workflow; verify expected release assets including `dist.zip`.

Never claim a release is ready based only on one agent's opinion. Use independent evidence and the release-readiness process in `engineering/chatgpt/maintenance-release.md`.

## Canonical supporting documents

Read these as needed:

- `engineering/chatgpt/README.md` — entrypoint and mode-selection guide.
- `engineering/chatgpt/canonical-context.md` — compact persistent engineering context and source hierarchy.
- `engineering/codex/README.md` — Codex-specific local execution and validation guide.
- `engineering/codex/canonical-context.md` — compact Codex startup context.
- `engineering/chatgpt/architecture-contract.md` — architecture/trust/recovery invariants.
- `engineering/chatgpt/agent-roles.md` — specialist scopes and output contracts.
- `engineering/chatgpt/operating-workflow.md` — Chat + Work end-to-end workflows.
- `engineering/chatgpt/validation-matrix.md` — validation by change category.
- `engineering/chatgpt/handoff-template.md` — Work↔Chat/session handoff format.
- `engineering/chatgpt/maintenance-release.md` — maintenance, CI, PR and release reviews.

Keep this file concise enough to be read at session start; put detailed procedures in the supporting documents above.

## Codex subagent model and budget policy

Use Codex subagents only when delegation isolates meaningful
independent work. Subagent capacity is a budget ceiling, not a target.

### Default routing

For Pocket Lab Lite Codex work:

- exploration, inventory, source mapping, generated-output scanning,
  and log reduction → `pl_docs_explorer` or Luna / low;
- validation-output and generated-diff analysis →
  `pl_validation_reader` or Luna / low;
- documentation semantics, knowledge relationships, glossary,
  vocabulary, journeys, and traceability →
  `pl_docs_reviewer` or Terra / medium;
- approved canonical metadata/generator/test implementation →
  `pl_docs_builder` or Terra / medium;
- final independent candidate review →
  `pl_final_reviewer` or Terra / high;
- unresolved security, authorization, trust-boundary, policy-lifecycle,
  or Threat Model ambiguity only →
  `pl_security_architect` or GPT-5.6 / high.

### Budget rules

- Prefer 1–3 subagents per delegation wave.
- Never spawn the configured maximum merely because capacity is
  available.
- Keep write-heavy implementation serialized unless ownership and
  files are demonstrably independent.
- Do not send the same broad task to several agents unless independent
  review is explicitly required.
- Prefer distilled findings with exact source references over raw
  search output, logs, stack traces, or generated-file dumps.
- Do not use GPT-5.6/Sol for repository inventory, grep/search,
  generated-file comparison, routine validation, mechanical edits,
  formatting, or ordinary generator implementation.
- Escalate to GPT-5.6/Sol only for unresolved architecture, security,
  authorization, trust-model, or difficult cross-system ambiguity.
- Use Luna for clear high-volume read work, Terra for normal reasoning
  and implementation, and GPT-5.6/Sol for exceptional judgement.
- The primary Codex session should normally remain Terra / medium for
  medium or large Pocket Lab Lite implementation work.
- A subagent must not commit, push, merge, tag, publish a release,
  mutate the live Server Phone, perform destructive cleanup/reset, or
  change secrets/credentials without explicit human authorization.
- Generated documentation remains a projection: do not manually fix
  `docs/generated/**` or `contracts/generated/**` when a canonical
  source or generator owns the result.

### Documentation Platform workflow

For substantial Documentation Platform changes, prefer:

```text
Work read-only investigation
→ Chat synthesis and implementation contract
→ Codex Terra/medium primary
→ Luna exploration/validation subagents
→ Terra documentation/build subagents
→ GPT-5.6/Sol security escalation only when required
→ Terra/high independent Codex review
→ Work independent review
→ Chat reconciliation and GitHub lifecycle
```

Separate builders from reviewers and keep the main Codex thread focused
on requirements, decisions, accepted findings, validation state, and
the final diff rather than noisy exploration output.
