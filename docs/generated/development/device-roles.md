---
title: "Device roles"
description: "Canonical Lite device role readiness and capability requirements."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: e3c315c145ce81cd685f2a30680a32d3183e678e7910115c738f22833683decc
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Device roles

| Role | Required capabilities | Optional capabilities | Readiness requirements | Dependencies |
| --- | --- | --- | --- | --- |
| `server_host` | app_host, compute, security_scanner | backup_target | FastAPI ready, NATS reachable, node agent heartbeat, supervisor status | Caddy, FastAPI, NATS, worker, node agent, core supervisor |
| `compute` | app_host, compute |  | accepted enrollment identity, NATS connection, fresh heartbeat | node agent, agent supervisor, NATS |
| `storage` | media_storage, backup_target |  | accepted enrollment identity, fresh heartbeat, sanitized storage readiness | node agent, agent supervisor, NATS, storage availability |
