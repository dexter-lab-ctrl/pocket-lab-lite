---
title: "HAR capture and sanitization"
description: "Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 3c52bd7f04af7afe5eae663a31115b43f4e9ebaf1ec612aae935a5dc1aa17eab
schema_revision: 1
validation_status: generated
---

# HAR capture and sanitization

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence.

`task lite:har:sanitize INPUT=<raw.har> OUTPUT=<safe.har>` removes authorization, cookies, credentials, NATS user info, Restic/Tailscale secrets, private keys, and sensitive query/header fields. `task lite:har:inspect` reports failed or duplicate Lite requests and heavy first-paint responses.
