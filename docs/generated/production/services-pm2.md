---
title: "Services and PM2"
description: "Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, and supervisors; installed apps may add their own managed process."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1753ddb100cc5a6f530412ab9d1df05ef9e57bde0639fc426ae5b7bf6ecfbc11
schema_revision: 1
validation_status: generated
---

# Services and PM2

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, and supervisors; installed apps may add their own managed process.

Use `pm2 status` and bounded process logs for diagnosis. Do not restart healthy services casually; distinguish disconnected, stopped, repairing, and undeliverable-command states.
