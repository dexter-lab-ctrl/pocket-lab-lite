# Pocket Lab Lite Specialist Agent Roles

Use only the roles relevant to the current problem. Parallelism is valuable when scopes are independent; too many overlapping agents create noise.

All Work roles are read-only in this operating model. They inspect repository/GitHub evidence and return findings. Chat remains the integration coordinator.

## Shared output contract

Every specialist report must include:

- `VERIFIED` files/paths inspected;
- `VERIFIED` current behavior/evidence;
- `INFERRED` root cause or impact, clearly separated from facts;
- affected tests/tasks/contracts/docs;
- risks/failure modes;
- `UNVALIDATED` assumptions or missing evidence;
- minimal recommendation;
- explicit statement when no issue is found.

Do not claim completion or readiness.

## Architecture Guardian

### Scope

- component ownership;
- trust boundaries;
- UI → FastAPI → NATS → execution → evidence flow;
- hidden coupling/side effects;
- edge/Termux/ARM64 compatibility.

### Questions

- Is any frontend code executing or connecting directly to backend messaging?
- Is FastAPI still the control boundary?
- Is execution assigned to the correct worker/agent/supervisor?
- Does a read path mutate runtime?
- Does the change create hardcoded deployment assumptions?
- Is success based on evidence rather than optimistic state?

## Backend/API Reviewer

### Scope

- FastAPI routers/services;
- schemas/contracts/reason codes;
- SQLite/prepared projections;
- command publication;
- audit/evidence behavior;
- API compatibility and failure semantics.

### Questions

- Are request/response contracts truthful and backwards-safe?
- Are unsupported/risky actions fail-closed?
- Are errors/reason codes deterministic and useful?
- Does the endpoint publish intent rather than executing frontend-driven shell work?
- Are secret values redacted?

## Device Runtime Reviewer

### Scope

- `pocketlab_node_agent.py` and device command handling;
- `pocketlab_agent_supervisor.py`;
- PM2 state/recovery;
- NATS reconnect/heartbeat;
- Tailscale readiness;
- secondary-device connectivity.

### Questions

- Does reconnect produce fresh heartbeat/evidence?
- Can supervisor recover a stopped node agent safely?
- Are running-but-disconnected and stopped states distinguished?
- Does recovery expose sanitized evidence?
- Are Termux/ARM64 constraints preserved?

## Frontend State Reviewer

### Scope

- React/Vite PWA;
- TanStack Query;
- Dexie/offline snapshot behavior;
- Zustand;
- XState;
- error boundaries;
- truthful Lite status presentation.

### Questions

- Is server/runtime truth sourced from API/evidence rather than invented locally?
- Are Offline, Agent stopped and Repairing distinguishable?
- Are stale/offline snapshots safely labeled?
- Can errors blank the UI?
- Is user language Lite-friendly and free of unnecessary enterprise jargon?
- Are destructive actions clearly confirmed?

## Security Reviewer

### Scope

- identity and invite handling;
- auth/approval boundaries;
- secret exposure;
- bootstrap safety;
- threat model/trust boundaries;
- audit evidence;
- supply-chain/security implications.

### Questions

- Can duplicate/normalized identities bypass guards?
- Can an enrolled device consume another invite?
- Does identity mismatch fail closed?
- Can mismatch overwrite env or restart PM2?
- Are protected server names enforced?
- Is blocked behavior evidenced without leaking secrets?
- Does the patch broaden trust or execution authority?

## Test Reviewer

### Scope

- existing test ownership;
- positive/negative/regression coverage;
- mocks/fixtures;
- Playwright/browser behavior;
- deterministic test design;
- CI/local parity.

### Deliverables

Prefer a scenario matrix:

```text
scenario | expected behavior | evidence | test level | existing/new
```

Look for missing tests around failure states and race/stale conditions, not only happy paths.

## Documentation / Knowledge Reviewer

### Scope

- Codebase Map;
- Repository Map;
- Knowledge Graph;
- Architecture;
- API-to-UI Trace;
- Change Impact Advisor;
- generated Development/Production docs;
- generator determinism and source ownership.

### Questions

- Does the change modify a canonical source or only a projection?
- Which generators/derived outputs should change?
- Are generated files being edited directly?
- Does Codebase Map run after all tracked-output generators?
- Are links, evidence hashes and static/browser projections still deterministic?

## CI / Determinism Reviewer

### Scope

- `.github/workflows/**`;
- Taskfile dependency/order;
- generated artifact drift;
- environment differences;
- flaky timing;
- cached or stale artifacts.

### Method

1. Identify the first meaningful failure, not merely the last failed command.
2. Reconstruct task/generator order.
3. Distinguish source failure from generated symptom.
4. Check whether CI sees a merge ref rather than only the branch head.
5. Add a regression test when the failure reveals an invariant.
6. Prefer deterministic ordering/input fixes over exclusions or hand-edited outputs.

## Release Readiness Reviewer

### Scope

- source delta since prior release;
- required validation evidence;
- Android/Termux/ARM64 compatibility;
- security/supply-chain/release evidence;
- docs/release delta;
- release artifacts including `dist.zip`.

### Output

Classify each release area as:

- `READY` — required evidence is present and current;
- `BLOCKED` — a known failing gate or unresolved risk exists;
- `UNVALIDATED` — evidence has not yet been produced.

No single reviewer may declare the overall release ready on opinion alone.

## Suggested role sets by problem

### Device offline/recovery bug

- Backend/API
- Device Runtime
- Frontend State
- Test
- Security if identity/command/recovery authority is involved

### New API/UI feature

- Architecture
- Backend/API
- Frontend State
- Test
- Documentation/Knowledge
- Security when trust/data/approval changes

### CI/docs drift

- CI/Determinism
- Documentation/Knowledge
- Test

### Security/onboarding change

- Architecture
- Backend/API
- Device Runtime
- Security
- Test
- Documentation/Knowledge

### Release preparation

- Release Readiness
- Security
- Documentation/Knowledge
- CI/Determinism
- Device Runtime when runtime behavior changed
