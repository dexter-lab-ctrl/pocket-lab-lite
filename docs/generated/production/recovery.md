---
title: "Backup & Restore"
description: "Backup & Restore manages a guarded sequence: Backup \u2192 Verified \u2192 Preview \u2192 Checkpoint \u2192 Restored. A backup is not automatically verified, and saved state never authorizes a write."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae852e970e2385b9f84509e4a446d978365eb0e16ee80c312f96ab8f18ee8983
schema_revision: 1
validation_status: generated
---

# Backup & Restore

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Backup & Restore manages a guarded sequence: Backup → Verified → Preview → Checkpoint → Restored. A backup is not automatically verified, and saved state never authorizes a write.

## What this tab is for

Backup & Restore manages a guarded sequence: Backup → Verified → Preview → Checkpoint → Restored. A backup is not automatically verified, and saved state never authorizes a write.

## What you see at a glance

- `Backup readiness, history/restore points, app backups, targets, evidence and copy controls`
- `Backup, verification, non-mutating preview, explicit restore confirmation`
- `Maintenance lock, unresolved-restore guard, active restore, historical preview, and projection reconciliation states`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Backup readiness, history/restore points, app backups, targets, evidence and copy controls</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Backup, verification, non-mutating preview, explicit restore confirmation</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Maintenance lock, unresolved-restore guard, active restore, historical preview, and projection reconciliation states</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Backup Now</h3><span class="pl-control-card__purpose">Requests a backup</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When target and guards allow</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Backend/worker creates a backup</dd></div><div><dt>Success looks like</dt><dd>Backup entry</dd></div><div><dt>May be blocked when</dt><dd>Target, lock, or stale projection guard</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Verify Backup</h3><span class="pl-control-card__purpose">Requests verification</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a backup exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Backup detail</dd></div><div><dt>What happens next</dt><dd>Produces verification evidence</dd></div><div><dt>Success looks like</dt><dd>Verified state</dd></div><div><dt>May be blocked when</dt><dd>Backup unavailable or verification failure</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Preview Restore</h3><span class="pl-control-card__purpose">Requests a non-mutating preview</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a restore point exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Shows planned restore evidence</dd></div><div><dt>Success looks like</dt><dd>Preview result</dd></div><div><dt>May be blocked when</dt><dd>Historical/projection state unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Restore Latest</h3><span class="pl-control-card__purpose">Requests confirmed restore</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">After confirmation and guards</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Checkpoint → restore → service restart → health validation</dd></div><div><dt>Success looks like</dt><dd>Restored and health evidence</dd></div><div><dt>May be blocked when</dt><dd>Maintenance lock, unresolved guard, active restore, or validation failure</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Manage / details / copy evidence</h3><span class="pl-control-card__purpose">Opens details or copies bounded evidence</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When an item exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery cards</dd></div><div><dt>What happens next</dt><dd>Shows retained status</dd></div><div><dt>Success looks like</dt><dd>Visible evidence</dd></div><div><dt>May be blocked when</dt><dd>No safe evidence available</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Backup & Restore states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Backup & Restore status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Backup & Restore cannot safely continue. Examples: Target, lock, or stale projection guard; Backup unavailable or verification failure; Historical/projection state unavailable.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Create a backup, verify it, and use Preview Restore before a confirmed restore.`
- `Read restore points and app-backup/target details before acting.`
- `Resolve stale/saved projection status before retrying a write.`

## When something is unavailable

Active restore, maintenance locks, unresolved guards, and stale projection write blocking are safety controls, not successful completion.

## Safety / trust boundaries

Restore is backend/worker-owned, requires confirmation and a pre-restore checkpoint, and ends with post-restore health validation. The browser cannot write backup storage directly.

## Related Feature Journey

[Backup & Restore Feature Journey](../enterprise/journeys/recovery.md)

## Related technical references

[Backup/recovery architecture](architecture/backup-recovery.md) · [Security boundaries](security-boundaries.md)
