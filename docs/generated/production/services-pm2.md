---
title: "Services and PM2"
description: "Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, supervisors, and the loopback `pocket-opa` policy engine; installed apps may add their own managed process."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 92df48d957c66c85adf49d3354cb49946a87e64f6253ebc61106c337da444f7e
schema_revision: 1
validation_status: generated
---

# Services and PM2

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, supervisors, and the loopback `pocket-opa` policy engine; installed apps may add their own managed process.

Use `pm2 status` and bounded process logs for diagnosis. Validate `pocket-opa` health on loopback before protected mutations. Do not restart healthy services casually; distinguish disconnected, stopped, repairing, policy-unavailable, and undeliverable-command states.
