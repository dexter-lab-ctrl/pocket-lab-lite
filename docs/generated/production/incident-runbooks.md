---
title: "Incident runbooks"
description: "Runbooks are user guidance, not browser shell execution."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9a3315bec7d9d8bab7eca1653eedcac05ea544ed0bb81a797678b6fd8ee790b8
schema_revision: 1
validation_status: generated
---

# Incident runbooks

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Runbooks are user guidance, not browser shell execution.

- NATS unavailable: verify listener, Tailnet reachability, credentials/config posture, and reconnect evidence.
- Worker consumer stalled: verify durable consumer health and watchdog recovery before restart.
- Agent stopped: verify supervisor, then use explicit recovery.
- Projection stale: preserve last valid state, rebuild prepared projection, and validate revision parity.
- Release verification failed: keep last-known-good PWA and investigate manifest/checksum/health.
