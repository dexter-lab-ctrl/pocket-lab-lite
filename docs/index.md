---
title: Pocket Lab Lite Documentation
description: Development and Production guidance for the edge-first Pocket Lab Lite control plane.
status: verified
audience: all
generated: false
---

<div class="pl-hero" markdown>

# Pocket Lab Lite Documentation

Operate, develop, validate, and recover your private edge-first workspace through repository-owned guidance.

[Production guide](generated/production/index.md){ .md-button .md-button--primary }
[Development guide](generated/development/index.md){ .md-button }

</div>

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Repository generated</span>
</div>

--8<-- "generated/home-dashboard.md"

## Architecture

```mermaid
flowchart LR
    UI[React / Vite PWA]
    Caddy[Caddy]
    API[FastAPI /api/lite/*]
    NATS[NATS / JetStream]
    Runtime[Worker / Agent / Supervisor]
    Evidence[Events and evidence]

    UI --> Caddy --> API --> NATS --> Runtime --> Evidence --> API
```

!!! info "Repository-owned documentation"
    Generated pages include source fingerprints and validation metadata. Development and Production tracks are checked independently.

## Validate before merging

```bash title="Development-PC validation"
task lite:contracts:check
task lite:docs:check
task lite:check:quick
```
