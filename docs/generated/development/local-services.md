---
title: "Local services and URLs"
description: "Development URLs are independent so direct FastAPI, same-origin Caddy/PWA, Vite, Storybook, MkDocs, NATS, state, and validation paths cannot be confused."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 28df171b72ff9344d9df00174a5d4f81aa4721fec284b226bb68c5c2c1d12a39
schema_revision: 1
validation_status: generated
---

# Local services and URLs

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Development URLs are independent so direct FastAPI, same-origin Caddy/PWA, Vite, Storybook, MkDocs, NATS, state, and validation paths cannot be confused.

- FastAPI direct: `LITE_API_DIRECT_URL` (default `http://127.0.0.1:8000`)
- Caddy/PWA: `LITE_BASE_URL` (default `http://127.0.0.1:8443`)
- Vite: `LITE_FRONTEND_URL` (default `http://127.0.0.1:5173`)
- Storybook: `LITE_STORYBOOK_URL` (default `http://127.0.0.1:6006`)
- MkDocs: `LITE_DOCS_URL` (default `http://127.0.0.1:8001`)
- NATS: `NATS_URL` (default `nats://127.0.0.1:4222`)
