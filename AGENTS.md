# Pocket Lab Lite Agent Engineering Contract

`AGENTS.md` is the repository-level operating contract for AI-assisted engineering in Pocket Lab Lite. It applies to ChatGPT Chat sessions, ChatGPT Work sessions and any human using their output.

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

## ChatGPT operating model

Pocket Lab Lite intentionally uses ChatGPT **Chat** and **Work** as complementary modes.

### Work mode — breadth, parallelism and independent review

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

### Chat mode — synthesis, integration and controlled mutation guidance

Use Chat for:

- reconciling Work-agent findings;
- selecting the smallest architecture-safe implementation;
- exact targeted patches and Python/shell one-shots;
- rapid test-failure/debugging loops;
- validation interpretation;
- explicit Git/GitHub operations when the user requests them;
- final PR/release synthesis.

Actual local commands run under human control in WSL2/Termux. Repository writes, commits, pushes, merges, tags, releases and live-runtime actions require explicit user intent.

Detailed usage is in `engineering/chatgpt/operating-workflow.md`.

## Default change lifecycle

For medium or large work, use these phases:

1. **Read-only investigation** — Work agents inspect Codebase Map and relevant source.
2. **Coordinator synthesis** — Chat reconciles verified findings and rejects unsupported assumptions.
3. **Test contract** — define success, negative cases and regression coverage before implementation.
4. **Targeted implementation** — Chat supplies minimal edits/commands; user applies locally.
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
- `engineering/chatgpt/architecture-contract.md` — architecture/trust/recovery invariants.
- `engineering/chatgpt/agent-roles.md` — specialist scopes and output contracts.
- `engineering/chatgpt/operating-workflow.md` — Chat + Work end-to-end workflows.
- `engineering/chatgpt/validation-matrix.md` — validation by change category.
- `engineering/chatgpt/handoff-template.md` — Work↔Chat/session handoff format.
- `engineering/chatgpt/maintenance-release.md` — maintenance, CI, PR and release reviews.

Keep this file concise enough to be read at session start; put detailed procedures in the supporting documents above.
