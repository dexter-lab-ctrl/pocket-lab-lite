---
title: "Services and PM2"
description: "Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, and supervisors; installed apps may add their own managed process."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 76013955b51b3b6474f0e6773d2336affe52bd34915ca3d98f329e0e3c76a64a
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
