---
title: "Troubleshooting"
description: "Use truthful Lite states before restarting services."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: dfb263a6195e29ff1381aa1d08a5a5f2cf0ab435319029c6267b6e121c251839
schema_revision: 1
validation_status: generated
---

# Troubleshooting

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Use truthful Lite states before restarting services.

- Running but disconnected: check NATS/Tailscale and reconnect watchdog evidence.
- Agent stopped: verify supervisor and PM2 state.
- Stopped without supervisor: follow recovery guidance; do not fabricate command delivery.
- Security scan accepted but not starting: verify durable consumer health and stale-run recovery evidence.
- Recovery projection stale: inspect freshness/revision and refresh prepared reads; do not treat saved state as fresh.
