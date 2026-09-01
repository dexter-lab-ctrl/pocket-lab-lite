---
title: "Devices"
description: "Devices manages the server host and enrolled devices through backend-generated invitations, identity guards, agents, supervisors, and truthful prepared state."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae40f6fa0fb418913108c52f1c221f9f65fbf45bbd848604e6c14b20ebaf6585
schema_revision: 1
validation_status: generated
---

# Devices

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Devices manages the server host and enrolled devices through backend-generated invitations, identity guards, agents, supervisors, and truthful prepared state.

## What this tab is for

Devices manages the server host and enrolled devices through backend-generated invitations, identity guards, agents, supervisors, and truthful prepared state.

## What you see at a glance

- `Refresh and Connected now`
- `online / total / health-attention counts`
- `Remote access ready or Remote access not ready; Tailscale IP only when ready`
- `Add a device disclosure, invite, device cards, details, model/type control, restart and retirement controls`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Refresh and Connected now</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>online / total / health-attention counts</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Remote access ready or Remote access not ready; Tailscale IP only when ready</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Add a device disclosure, invite, device cards, details, model/type control, restart and retirement controls</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Refresh</h3><span class="pl-control-card__purpose">Refreshes prepared device state</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When reads are available</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Devices header</dd></div><div><dt>What happens next</dt><dd>Updates counts and cards</dd></div><div><dt>Success looks like</dt><dd>Fresh state label</dd></div><div><dt>May be blocked when</dt><dd>Backend read unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Add Device</h3><span class="pl-control-card__purpose">Prepares a bounded invite</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">After device name and role validation</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Add a device</dd></div><div><dt>What happens next</dt><dd>Shows hostname, role, expiry, Connect this device and Copy command</dd></div><div><dt>Success looks like</dt><dd>Preparing invite / copied / invite details</dd></div><div><dt>May be blocked when</dt><dd>Reconnect to continue, duplicate name, or device already added</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Role selector</h3><span class="pl-control-card__purpose">Chooses a currently emitted device role</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">During invite preparation</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Add a device</dd></div><div><dt>What happens next</dt><dd>Role is included in the invite request</dd></div><div><dt>Success looks like</dt><dd>Invite displays selected role</dd></div><div><dt>May be blocked when</dt><dd>Role/name validation fails</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Restart Agent</h3><span class="pl-control-card__purpose">Requests supervised agent recovery</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For an eligible enrolled device</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Device details</dd></div><div><dt>What happens next</dt><dd>Preparing request → private channel → device agent → back online</dd></div><div><dt>Success looks like</dt><dd>Completed or fresh heartbeat</dd></div><div><dt>May be blocked when</dt><dd>Waiting, stopped, repairing, failed, or command undeliverable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Remove Old Device</h3><span class="pl-control-card__purpose">Assesses and requests explicit retirement</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">After dependency and protected-host checks</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Device details</dd></div><div><dt>What happens next</dt><dd>Confirmation and recovery assessment</dd></div><div><dt>Success looks like</dt><dd>Removal outcome and audit evidence</dd></div><div><dt>May be blocked when</dt><dd>Hosted apps/backups, stale assessment, delivery failure, or protected server host</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Devices states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Devices status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Devices cannot safely continue. Examples: Backend read unavailable; Reconnect to continue, duplicate name, or device already added; Role/name validation fails.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Add a named device, copy the backend-generated bootstrap command, and wait for safe acceptance and heartbeat.`
- `Use Remote access only after its ready state is shown.`
- `Read status glossary: Online, Joining, Waiting, Offline, Agent stopped, Repairing, Remote access not ready, and Protected server host.`

## When something is unavailable

A disconnected running agent follows reconnect/watchdog recovery; a stopped agent requires supervisor recovery; stopped without a supervisor results in guidance, not fabricated delivery.

## Safety / trust boundaries

Duplicate names/identities are protected case- and separator-insensitively. Identity mismatch fails closed: no environment overwrite or PM2 restart. Bootstrap material is never reproduced in this guide.

## Related Feature Journey

[Devices Feature Journey](../enterprise/journeys/devices.md)

## Related technical references

[Device onboarding architecture](architecture/device-onboarding.md) · [Remote access](remote-access.md) · [Troubleshooting](troubleshooting.md)
