# Pocket Lab Lite Canonical Engineering Context

This file is the compact context to load at the start of a Chat or Work session. It is intentionally shorter than historical handovers and must not replace repository verification.

## Product

Pocket Lab Lite is an edge-first, self-hostable local control plane for Android/Termux, ARM64, low-power devices, Ubuntu/WSL2 development and private self-hosting.

Default Lite language favors Devices, Apps, Rules, Security/Safety and Recovery rather than enterprise jargon. Enterprise behavior may exist underneath but remains opt-in.

## Architecture

```text
React/Vite PWA
→ Caddy same-origin proxy
→ FastAPI /api/lite/*
→ NATS / JetStream
→ worker / node agent / supervisor
→ events + heartbeats + sanitized evidence
→ FastAPI prepared reads
→ UI
```

Core constraints:

- no frontend direct NATS;
- no frontend shell execution;
- no browser-held backend secrets;
- FastAPI owns control-plane APIs;
- agents/supervisors/workers own execution/recovery;
- backend generates bootstrap scripts;
- lifecycle/recovery evidence remains observable;
- Android/Termux and ARM64 remain first-class targets.

## Device onboarding

Expected conceptual flow:

```text
invite creation
→ audit evidence
→ copyable bootstrap command
→ identity guard
→ safe acceptance
→ env write
→ node agent start
→ supervisor start
→ heartbeats appear in Devices
```

Safety invariants:

- duplicate names/identities are blocked across active, stale and invite state;
- matching is case-insensitive and separator-insensitive;
- server host names are protected;
- another device's invite cannot be consumed on an enrolled device;
- identity mismatch fails closed;
- mismatch does not overwrite env or restart PM2;
- repair/rejoin is explicit;
- blocked consumption emits sanitized audit evidence;
- no tokens/hashes/passwords/API keys/secrets in output.

## Agent and supervisor

Preserve the node agent and separate supervisor model.

Node agent responsibilities include NATS connection, heartbeat/telemetry/health, command handling, reconnect and fresh heartbeat after reconnect.

Supervisor responsibilities include reading the Lite agent env, watching PM2 node-agent state, recovering stopped agents and publishing sanitized evidence when NATS is reachable.

Recovery semantics:

- running but disconnected → reconnect/watchdog;
- stopped → supervisor recovery;
- stopped without supervisor → UI recovery guidance.

## Devices UX

Keep truthful distinctions such as Online, Joining, Waiting, Offline, Agent stopped, Repairing, Remote access not ready and Protected server host.

Restart Agent must show real progress and distinguish repairing from an undeliverable command.

## Remote access

Tailscale remains part of supported remote-access behavior. When diagnosing offline devices, inspect the source/current runtime evidence for:

- tailscaled state;
- Tailnet IPv4 readiness;
- NATS listener/reachability;
- secondary NATS URL/connectivity;
- PM2 node-agent state;
- PM2 supervisor state.

Read APIs should not acquire hidden startup side effects; startup/bootstrap paths own safe side effects.

## Approval model

Lite Personal Mode is default. Safe actions may auto-approve only when current implementation explicitly supports it and must produce evidence. Removing stale/offline devices requires confirmation; healthy online devices should not be casually removed.

Enterprise Mode is opt-in with explicit approvals, roles and reasons; it must not become the default Lite UX.

## Documentation Platform orientation

Use these generated views to orient investigations, then verify source:

- Codebase Map: `docs/generated/development/knowledge/codebase-map.md`
- Repository Map: `docs/generated/development/knowledge/repository-map.md`
- Knowledge Graph: `docs/generated/enterprise/knowledgebase/knowledge-graph.md`
- Production Architecture: `docs/generated/production/architecture/index.md`
- API-to-UI Trace: `docs/generated/enterprise/reference/api-ui-trace.md`
- Change Impact Advisor: `docs/generated/enterprise/reference/change-advisor.md`

The Codebase Map models Git-known paths and infers directories. Generated views are static/source-derived aids, not a replacement for source inspection.

## Source hierarchy

When evidence conflicts, prefer:

1. current source/tests on the target branch;
2. canonical contracts/schemas/architecture metadata;
3. current generated evidence/docs;
4. repo-owned `engineering/chatgpt/` guidance;
5. handovers/conversation history.

## Chat + Work + Codex contract

**Work:** read-only investigation, independent review, test design, CI/maintenance/release analysis.

**Chat:** coordination, evidence reconciliation, architecture/design decisions, debugging reasoning and explicit GitHub integration when requested.

**Codex:** local source implementation and validation when available. Use `engineering/codex/README.md` for detailed local execution guidance.

**Human:** explicitly authorizes remote, destructive, live-runtime, credential and release actions.

## Validation baseline

Use focused checks first, then the relevant broader gate. Common commands:

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

For generated documentation changes, regenerate from canonical source; never hand-edit generated output as the source fix.

## Reporting

Always separate `VERIFIED`, `INFERRED`, `PATCH-PROVIDED`, `MISSING`, `PLANNED`, `OPTIONAL` and `UNVALIDATED` state. Never claim completion without validation output.
