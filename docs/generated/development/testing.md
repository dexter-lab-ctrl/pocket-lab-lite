---
title: "Testing matrix"
description: "The Lite test matrix separates deterministic component/API checks from live read-only integration and explicit device qualification."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f32c8d2c7ea94dc87d1e2bd55927f82bb7b38a4010bb650a36354c0122392e3d
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
