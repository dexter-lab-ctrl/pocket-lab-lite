---
title: "Home"
description: "Home summarizes the self-hosted workspace, release/system information, and safe next actions. Refreshing asks for current prepared information; navigation cards only navigate and never execute backend work."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f123b0aaf69edce56c29e6a6996a7a306fdf54a239bca07b574491fe48229bde
schema_revision: 1
validation_status: generated
---

# Home

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Home summarizes the self-hosted workspace, release/system information, and safe next actions. Refreshing asks for current prepared information; navigation cards only navigate and never execute backend work.

## What this tab is for

Home summarizes the self-hosted workspace, release/system information, and safe next actions. Refreshing asks for current prepared information; navigation cards only navigate and never execute backend work.

## What you see at a glance

- `Workspace ready / Review recommended / Showing saved information`
- `Recommended next action and Apps, Devices, and Backups shortcuts`
- `Workspace device, capacity, processor, temperature, storage, memory, health, database, and activity where rendered`
- `Workspace readiness, ready count, Private by design, service cards, and current-versus-saved information`
- `System Update source and installed-files verification, last checked, and lifecycle status`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Workspace ready / Review recommended / Showing saved information</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Recommended next action and Apps, Devices, and Backups shortcuts</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Workspace device, capacity, processor, temperature, storage, memory, health, database, and activity where rendered</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Workspace readiness, ready count, Private by design, service cards, and current-versus-saved information</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>System Update source and installed-files verification, last checked, and lifecycle status</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Workspace summary</h3><span class="pl-control-card__purpose">Shows prepared workspace information</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a projection is available</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Hero and stat cards</dd></div><div><dt>What happens next</dt><dd>Opens the relevant tab when selected</dd></div><div><dt>Success looks like</dt><dd>A rendered current or saved label</dd></div><div><dt>May be blocked when</dt><dd>Projection may be unavailable or saved</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Refresh</h3><span class="pl-control-card__purpose">Requests current prepared information</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When the control is enabled</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Home</dd></div><div><dt>What happens next</dt><dd>Updates the displayed projection</dd></div><div><dt>Success looks like</dt><dd>Freshness/status message</dd></div><div><dt>May be blocked when</dt><dd>Read or service state may be unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Check now</h3><span class="pl-control-card__purpose">Requests update verification</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When update checks are supported</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>System Update</dd></div><div><dt>What happens next</dt><dd>Shows checking or a result</dd></div><div><dt>Success looks like</dt><dd>Source and installed-files verification status</dd></div><div><dt>May be blocked when</dt><dd>Connectivity or update service is unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Install Update</h3><span class="pl-control-card__purpose">Requests a supported update install</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">Only when an update is available</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>System Update</dd></div><div><dt>What happens next</dt><dd>Downloading → preparing → installing → validating or safely rolling back</dd></div><div><dt>Success looks like</dt><dd>Installed from source or completed state</dd></div><div><dt>May be blocked when</dt><dd>No update, maintenance guard, or failed verification</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Home states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Home status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Home cannot safely continue. Examples: Projection may be unavailable or saved; Read or service state may be unavailable; Connectivity or update service is unavailable.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Review Workspace ready or Review recommended before taking an action.`
- `Use Apps, Devices, or Backups shortcuts to continue in their dedicated tabs.`
- `Check now, then read update available, checking, downloading, preparing, installing, validating, rolling back safely, or update failed honestly.`

## When something is unavailable

Saved-status-only information is informative, not proof that an update action can run.

## Safety / trust boundaries

System Update status is backend-owned. Source and installed-files verification do not expose credentials, private paths, or raw runtime payloads.

## Related Feature Journey

[Feature Journeys](../enterprise/hubs/use.md#feature-journeys) describe the backend-owned flow for each shortcut.

## Related technical references

[Current Lite tabs](tabs.md) · [Release and upgrade](upgrade.md) · [Security boundaries](security-boundaries.md)
