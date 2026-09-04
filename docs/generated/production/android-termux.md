---
title: "Android and Termux operations"
description: "The server-phone runtime is ARM64/Android/Termux and must avoid desktop-only assumptions."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: af565ccf20cd7261b44f75f6f59dd4f775f699a95ff7aff70b15c7f81e5ddad3
schema_revision: 1
validation_status: generated
---

# Android and Termux operations

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

The server-phone runtime is ARM64/Android/Termux and must avoid desktop-only assumptions.

Use Termux-compatible paths and commands, keep generated work bounded, and validate PM2, NATS, Caddy, Tailscale, FastAPI, worker, agent, and supervisor with server-phone evidence. Development browser, Storybook, MkDocs, Redocly, and Allure tooling is not required.
