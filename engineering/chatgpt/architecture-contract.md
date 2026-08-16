# Pocket Lab Lite Architecture Contract

This document defines architecture invariants that Chat and Work agents must preserve unless the user explicitly approves an architectural change and the repository evidence is updated accordingly.

## Control-plane flow

```text
UI
→ Caddy
→ FastAPI /api/lite/*
→ NATS / JetStream
→ worker / node agent / supervisor
→ events + heartbeats + audit evidence
→ FastAPI prepared reads
→ UI
```

## Ownership boundaries

### Frontend

The React/Vite PWA owns presentation, local UI state, safe cached/snapshot reads and user interaction. It must not:

- talk directly to NATS;
- execute shell commands;
- hold backend secrets;
- bypass FastAPI for control actions;
- invent runtime success that has not been evidenced.

### Caddy

Caddy remains the same-origin proxy/HTTPS boundary. Avoid hardcoded deployment addresses in frontend or generated docs.

### FastAPI

FastAPI owns `/api/lite/*` control-plane APIs and safe read projections. It should:

- validate request/identity/approval constraints;
- publish bounded control intent rather than performing browser-driven shell work;
- expose sanitized evidence and truthful status;
- keep read endpoints free of hidden service-start/recovery side effects.

### NATS / JetStream

NATS/JetStream is backend messaging/evidence transport. Browser code does not connect to it. Subjects/contracts must remain auditable and sanitized.

### Workers

Workers own queued backend execution where the current architecture assigns it. Changes must preserve command/result evidence and failure reason visibility.

### Node agent

The node agent owns device-side command handling, connectivity, heartbeat, telemetry/health publication and reconnect behavior. A reconnect should be followed by fresh evidence/heartbeat rather than stale projection reuse.

### Supervisor

The supervisor is a separate recovery process. It watches the PM2 node agent, starts/restarts it when the defined safety conditions allow, reads the Lite agent env and publishes sanitized recovery evidence when messaging is reachable.

## Recovery state model

Do not collapse these cases:

```text
agent running + disconnected
→ reconnect/watchdog path

agent stopped + supervisor healthy
→ supervisor recovery path

agent stopped + supervisor absent/unhealthy
→ recovery guidance / explicit operator action
```

UI must distinguish Offline, Agent stopped and Repairing where source evidence supports those states.

## Device onboarding and identity

Backend owns invite creation and bootstrap material. The onboarding path must fail closed on identity mismatch.

Required safety checks include, where implemented by current source:

- active devices;
- stale records;
- pending and accepted invites;
- device identities;
- protected server host names;
- duplicate normalized names/identities.

Normalization must remain case-insensitive and separator-insensitive. Do not allow an enrolled device to consume another device's invite. Identity mismatch must not overwrite env or restart PM2. Repair/rejoin paths are explicit, not implicit fallback.

## Secrets and evidence

Never expose:

- invite tokens;
- hashes;
- passwords;
- API keys;
- private environment values;
- backend secrets.

Audit/evidence payloads should carry enough sanitized context to explain lifecycle and blocked actions without leaking secret material.

## Tailscale / remote access

Remote access remains Tailscale-aware. Safe startup/bootstrap paths may detect/start `tailscaled` according to current implementation. Read/status APIs should remain observational.

When diagnosing remote access, reason across:

```text
tailscaled
→ Tailnet IPv4
→ NATS listener/reachability
→ secondary NATS connectivity
→ node agent PM2 state
→ supervisor PM2 state
→ fresh heartbeat/evidence
```

Only show Tailscale IP as ready when current source/evidence establishes readiness. Otherwise use `Remote access not ready`.

## Lite approval model

### Personal Mode

Default Lite behavior favors simple safe operation. Safe actions may auto-approve only when supported by current source and must generate evidence. Destructive/stale cleanup requires confirmation; healthy online resources should not be casually removed.

### Enterprise Mode

Enterprise governance is opt-in. Preserve explicit approvals, role awareness and approval/rejection reasons where implemented. Do not force enterprise ceremony into default Lite UX.

## Generated documentation boundary

Generated documentation is a projection of canonical source/evidence. Agents must not solve source problems by directly editing `docs/generated/**` or `contracts/generated/**` unless the user explicitly requests emergency artifact correction and accepts that it will be overwritten.

Change canonical input/generator, then regenerate and validate determinism.

## Compatibility boundary

Every change should consider:

- Android/Termux runtime;
- ARM64 dependencies/binaries;
- Ubuntu/WSL2 development;
- low-memory/low-power operation;
- offline/private self-hosting;
- `dist.zip` release packaging.

Do not introduce a desktop-only correctness dependency into production runtime.

## Architectural review questions

Before implementation, ask:

1. Which component owns the action?
2. Does the UI remain presentation/control intent only?
3. Does FastAPI remain the control API?
4. Is execution still owned by worker/agent/supervisor?
5. Is status derived from evidence rather than optimistic UI state?
6. Are failures and recovery auditable?
7. Is secret material excluded?
8. Does the change preserve Termux/ARM64 and edge-first operation?
9. Does it create hidden side effects in a read path?
10. Does it require new tests/contracts/docs/evidence projections?
