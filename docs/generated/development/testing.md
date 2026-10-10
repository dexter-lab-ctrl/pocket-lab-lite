---
title: "Testing matrix"
description: "The Lite test matrix separates deterministic component/API checks from live read-only integration and explicit device qualification."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: af0be24c1205694cd1572d49c42088e35d8920b8558e84c339d57e4cd5a2815c
schema_revision: 1
validation_status: generated
---

# Testing matrix

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

The Lite test matrix separates deterministic component/API checks from live read-only integration and explicit device qualification.

- Unit: Vitest and focused backend Pytest.
- Contract: FastAPI OpenAPI export, frontend route usage, generated fixture metadata, Redocly.
- Component: Storybook render and interaction checks.
- Mock integration: Playwright desktop/mobile through MSW and TanStack Query.
- Live integration: read-only Playwright through Caddy/FastAPI when `LITE_E2E_LIVE=1`.
- Device qualification: explicit Android/Termux and long-duration gates only.
