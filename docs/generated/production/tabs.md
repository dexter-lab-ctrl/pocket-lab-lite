---
title: "Current Lite tabs"
description: "The deployed PWA exposes seven Lite-friendly sections."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 5c0743c1c70ab3940fccd0437940bae199e1f8815785330eee332d56cc40eef2
schema_revision: 1
validation_status: generated
---

# Current Lite tabs

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

The deployed PWA exposes seven Lite-friendly sections.

## Choose a tab

<section class="pl-tab-grid" aria-label="Current Lite tabs"><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Home</span><h3>Workspace and update summary</h3><p>Refresh prepared information and review current-versus-saved state.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Devices</span><h3>Enrollment and device health</h3><p>Add, reconnect, recover, or retire devices with identity safeguards.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Apps</span><h3>Supported app lifecycle</h3><p>Open or manage a supported catalog app through FastAPI requests.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Security & Safety</span><h3>Bounded local checks</h3><p>Choose an enabled scan and review normalized, sanitized results.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Backup & Restore</span><h3>Guarded recovery workflow</h3><p>Back up, verify, preview, and explicitly confirm restore.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Identity & Access</span><h3>Local human access</h3><p>Manage sign-in, passkeys, recovery, sessions, and memberships.</p></article><article class="pl-card pl-tab-card"><span class="pl-card-kicker">Rules</span><h3>Protected-action governance</h3><p>Review policy state, simulation, approvals, exceptions, and decisions.</p></article></section>

Each tab renders prepared, backend-owned state and supported actions. The browser does not execute shell commands, connect directly to NATS or OPA, or hold backend secrets.
