---
title: "HAR capture and sanitization"
description: "Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 412f31ab2d7232d94e8e1c885b19c4b1bd4f6a75ef4524c47ff5b65507754e26
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
