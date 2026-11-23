---
title: "Services and PM2"
description: "Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, supervisors, and the loopback `pocket-opa` policy engine; installed apps may add their own managed process."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9b121648622db93ba5997d925bd47394d7d7648ee0c300c2e9548123866a5b37
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
