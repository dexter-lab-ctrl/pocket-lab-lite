---
title: "Security and Safety"
description: "Security checks run through FastAPI, NATS/JetStream, and the worker. Lynis/Trivy output is normalized and sanitized before summary display."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 49505939a3847c1d0a060ef758da897797c4061eaacf6dd23d00aeaf8da6cd53
schema_revision: 1
validation_status: generated
---

# Security and Safety

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Security checks run through FastAPI, NATS/JetStream, and the worker. Lynis/Trivy output is normalized and sanitized before summary display.

Quick Safety Check is the default low-power profile. Full Local Check and PhotoPrism App Check are explicit deeper checks where enabled. Photos/media, secrets, raw logs, private paths, and raw scanner payloads are excluded from normal UI and generated docs.
