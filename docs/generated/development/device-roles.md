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
source_fingerprint: a9429baa726ac2215f72e277e773747b7622d32273f54e094b0ac32d8fe73e5d
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
