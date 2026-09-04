---
title: "Apps"
description: "Apps is the supported App Catalog and PhotoPrism lifecycle surface. Each action is a FastAPI request; browser UI never runs PM2, Caddy, storage, backup, repair, or scanner commands."
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

# Apps

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Apps is the supported App Catalog and PhotoPrism lifecycle surface. Each action is a FastAPI request; browser UI never runs PM2, Caddy, storage, backup, repair, or scanner commands.

## What this tab is for

Apps is the supported App Catalog and PhotoPrism lifecycle surface. Each action is a FastAPI request; browser UI never runs PM2, Caddy, storage, backup, repair, or scanner commands.

## What you see at a glance

- `Open and Manage`
- `PhotoPrism actions and Manage sections: Photos, Safety, Recovery, App setup, Remove`
- `Phone-photo and storage-device sources`
- `Ready, Connected, Imported, Getting ready, Working, Done, Needs attention, Paused for safety, Not available, Waiting, Not ready, and Installed`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Open and Manage</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>PhotoPrism actions and Manage sections: Photos, Safety, Recovery, App setup, Remove</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Phone-photo and storage-device sources</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Ready, Connected, Imported, Getting ready, Working, Done, Needs attention, Paused for safety, Not available, Waiting, Not ready, and Installed</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Open</h3><span class="pl-control-card__purpose">Navigates to the same-origin installed app route</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When installed and route-ready</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>App card</dd></div><div><dt>What happens next</dt><dd>Opens the app</dd></div><div><dt>Success looks like</dt><dd>App route loads</dd></div><div><dt>May be blocked when</dt><dd>App not installed or route not ready</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Manage</h3><span class="pl-control-card__purpose">Opens supported management sections</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For a catalog app</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>App card</dd></div><div><dt>What happens next</dt><dd>Shows Photos, Safety, Recovery, setup, or removal controls</dd></div><div><dt>Success looks like</dt><dd>Visible management state</dd></div><div><dt>May be blocked when</dt><dd>App state does not support the section</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Connect photos / Import photos</h3><span class="pl-control-card__purpose">Requests supported media connection/import</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">After source selection</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Photos</dd></div><div><dt>What happens next</dt><dd>Backend-owned progress</dd></div><div><dt>Success looks like</dt><dd>Connected / Imported</dd></div><div><dt>May be blocked when</dt><dd>Source or safety prerequisite unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Back up app / Check app / Preview restore / Back up to storage device</h3><span class="pl-control-card__purpose">Requests bounded recovery/safety work</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When app and target prerequisites are met</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery and Safety</dd></div><div><dt>What happens next</dt><dd>Progress and sanitized evidence</dd></div><div><dt>Success looks like</dt><dd>Done or verification evidence</dd></div><div><dt>May be blocked when</dt><dd>Waiting, paused for safety, or needs attention</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Install / Update / Repair / Remove app</h3><span class="pl-control-card__purpose">Requests lifecycle work</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When the action is allowed</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>App actions</dd></div><div><dt>What happens next</dt><dd>Backend execution and progress</dd></div><div><dt>Success looks like</dt><dd>Installed or completed state</dd></div><div><dt>May be blocked when</dt><dd>Prerequisite, policy, or recovery guard</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Apps states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Apps status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Apps cannot safely continue. Examples: App not installed or route not ready; App state does not support the section; Source or safety prerequisite unavailable.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Open an installed app for its own user experience.`
- `Manage PhotoPrism to select sources and request an action, then follow progress and recovery evidence.`
- `Use status chips to distinguish working from complete or blocked.`

## When something is unavailable

Not available, Waiting, Not ready, and Paused for safety are truthful states; retry only after the stated prerequisite or recovery path is resolved.

## Safety / trust boundaries

App requests remain same-origin through FastAPI and backend services. Media, raw logs, secrets, and private paths are not exposed by this documentation.

## Related Feature Journey

[Apps Feature Journey](../enterprise/journeys/apps.md)

## Related technical references

[Apps architecture](architecture/apps.md) · [Backup & Restore](recovery.md) · [Security boundaries](security-boundaries.md)
