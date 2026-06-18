# Lite Architecture

Pocket Lab Lite preserves the core Pocket Lab architecture:

```text
React / Vite PWA
→ FastAPI
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

## Preserved boundaries

- The frontend never talks directly to NATS.
- The frontend never executes shell commands.
- FastAPI remains the control API.
- Workers own execution and resume.
- Typed Operations remain the execution contract.
- Lifecycle events and audit evidence remain available internally.

## Lite simplification

Pocket Lab Lite should expose simple appliance-style summaries instead of backend implementation details.

The UI should show:

- clean status cards;
- human-readable summaries;
- plain-language actions;
- clear progress states;
- user-friendly success and failure messages;
- safe confirmations for risky actions.

The UI should not expose by default:

- shell commands;
- raw logs;
- raw JSON;
- NATS or JetStream internals;
- worker internals;
- backend file paths;
- raw event or audit payloads.
