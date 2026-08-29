---
title: "Lite architecture as code"
description: "This page is generated from the active Lite source layout and architectural constraints."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 469ea6d43377d3911f1d69c40ef4718b8c1dc749316dc9bd0ad006cff217e80b
schema_revision: 1
validation_status: generated
---

# Lite architecture as code

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

This page is generated from the active Lite source layout and architectural constraints.

```mermaid
flowchart LR
  UI[React/Vite PWA] --> Caddy[Caddy same-origin proxy]
  Caddy --> API[FastAPI /api/lite/*]
  API --> DB[(SQLite prepared state)]
  API --> NATS[NATS / JetStream]
  NATS --> Exec[Worker / agent / supervisor]
  Exec --> Evidence[Events, heartbeats, sanitized evidence]
  Evidence --> API
  API --> UI
```

Mandatory boundaries: the frontend never talks directly to NATS, never executes shell commands, and never stores backend secrets. Bootstrap commands remain backend-generated; agents and supervisors own execution and recovery.

## Active screen modules

- `src/lite/LiteHome.jsx`
- `src/lite/LiteDevices.jsx`
- `src/lite/LiteCatalog.jsx`
- `src/lite/LiteRecovery.jsx`
- `src/lite/LiteSecurity.jsx`
- `src/lite/LiteIdentity.jsx`
- `src/lite/LiteRules.jsx`