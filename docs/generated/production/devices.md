---
title: "Devices and onboarding"
description: "Device onboarding is backend-owned: invite creation \u2192 audit evidence \u2192 copyable bootstrap command \u2192 identity guard \u2192 safe acceptance \u2192 env write \u2192 node agent/supervisor start \u2192 heartbeats in Devices."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9f8a72eccd6819f89b97d0c2042b1e8fd19666bff325a7f4c4e5e0585788267c
schema_revision: 1
validation_status: generated
---

# Devices and onboarding

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Device onboarding is backend-owned: invite creation → audit evidence → copyable bootstrap command → identity guard → safe acceptance → env write → node agent/supervisor start → heartbeats in Devices.

Duplicate names and invites are blocked case-insensitively and separator-insensitively. Identity mismatches fail closed. A lost heartbeat changes a durable enrolled device to Offline/Stale; it does not implicitly delete enrollment.
