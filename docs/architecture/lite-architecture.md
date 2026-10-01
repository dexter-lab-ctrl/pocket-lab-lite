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


## Phase 1 photo backup data plane

Photo Backup preserves the Lite control-plane boundary while adding a direct media data plane:

```text
Devices UI
  -> FastAPI /api/lite/*
  -> NATS / JetStream
  -> worker
  -> targeted node command
  -> node agent
  -> rclone WebDAV COPY over Caddy / Tailscale HTTPS
  -> PhotoPrism originals
```

Photo/video bytes do not traverse FastAPI or NATS. The destination is backend-derived, credentials are short-lived and server-created, the node receives only an opaque credential reference over NATS, and source deletion is never propagated to PhotoPrism. See [Photo Backup to PhotoPrism WebDAV](../operations/photo-backup-photoprism-webdav.md).
