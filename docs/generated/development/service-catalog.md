---
title: "Service catalog"
description: "Approved Lite PM2 process patterns, owners, recovery, health and secret restrictions."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 30ad2a87493117a1fa2324d15275b33b0f3baacb55733bc4f8f731d28aa0a7c1
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Service catalog

| Process | Owner / purpose | Platform | Restart policy | Health | NATS | Recovery |
| --- | --- | --- | --- | --- | --- | --- |
| `pocket-api` | FastAPI control API: Serve /api/lite/* and safe prepared reads | Android/Termux, Ubuntu/WSL2 | PM2 exponential backoff and bounded memory restart | /health, /ready | required for write paths | verify NATS and SQLite before restarting |
| `pocket-nats` | NATS/JetStream service: Command and event backbone | Android/Termux, Ubuntu/WSL2 | PM2 | NATS monitor and JetStream status | self | verify listener, storage, and credentials before restart |
| `pocket-node-agent` | server-host node agent: Publish heartbeat/telemetry and execute device commands | Android/Termux | PM2 and core supervisor | fleet agent status | required | reconnect watchdog then supervisor recovery |
| `pocket-opa` | Rules policy service: Evaluate registered protected actions on loopback before FastAPI dispatch | Android/Termux, Ubuntu/WSL2 | PM2 core supervisor after validated policy activation | loopback OPA /health, GET /api/lite/policy | none | fail closed, preserve last-known-good policy, validate before restart |
| `pocket-worker` | worker execution plane: Consume durable commands and own backend execution | Android/Termux, Ubuntu/WSL2 | PM2 plus durable-consumer watchdog | durable consumer health | required | consumer re-enrollment before process restart |
| `pocketlab-agent-<node_id>` | joined-device node agent: Publish heartbeat/telemetry and execute device commands | Android/Termux, Linux ARM64 | PM2 supervised | fleet connection and PM2 status | required | explicit repair/rejoin on identity mismatch |
| `pocketlab-agent-supervisor-<node_id>` | joined-device supervisor: Watch and recover the node agent as a separate process | Android/Termux, Linux ARM64 | PM2 supervised | supervisor status | optional for local recovery; required for evidence publish | starts/restarts failed agent without overwriting identity |
