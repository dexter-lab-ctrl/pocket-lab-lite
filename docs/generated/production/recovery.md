---
title: "Backup & Restore"
description: "Backup & Restore manages a guarded sequence: Backup \u2192 Verified \u2192 Preview \u2192 Checkpoint \u2192 Restored. A backup is not automatically verified, and saved state never authorizes a write."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: b28a73f26d5d1fe5a14b54c998516d1848edb8c54ebf78e4b394a52dc53a77df
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
- `Backend-owned Server Phone backup location, location health, and immutable restore-point binding`
- `Backup, verification, non-mutating preview, explicit restore confirmation`
- `Maintenance lock, unresolved-restore guard, active restore, historical preview, and projection reconciliation states`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Backup readiness, history/restore points, app backups, targets, evidence and copy controls</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Backend-owned Server Phone backup location, location health, and immutable restore-point binding</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Backup, verification, non-mutating preview, explicit restore confirmation</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Maintenance lock, unresolved-restore guard, active restore, historical preview, and projection reconciliation states</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Backup Now</h3><span class="pl-control-card__purpose">Requests a backup in the selected backend location</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When target, location, and guards allow</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Backend/worker creates a backup</dd></div><div><dt>Success looks like</dt><dd>Backup entry with location</dd></div><div><dt>May be blocked when</dt><dd>Target, location, lock, or stale projection guard</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Choose backup location</h3><span class="pl-control-card__purpose">Selects or discovers a validated Server Phone location</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When no Recovery mutation is running</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Shows backend-discovered candidates and bounded health</dd></div><div><dt>Success looks like</dt><dd>Selected location</dd></div><div><dt>May be blocked when</dt><dd>Picker unavailable, location missing, read-only, or low space</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Verify Backup</h3><span class="pl-control-card__purpose">Requests verification from the restore point's recorded repository</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a backup and its location are available</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Backup detail</dd></div><div><dt>What happens next</dt><dd>Produces verification evidence</dd></div><div><dt>Success looks like</dt><dd>Verified state</dd></div><div><dt>May be blocked when</dt><dd>Backup unavailable, repository mismatch, or verification failure</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Preview Restore</h3><span class="pl-control-card__purpose">Requests a non-mutating preview from the recorded source location</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a restore point exists and its repository is available</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Shows planned restore evidence</dd></div><div><dt>Success looks like</dt><dd>Preview result</dd></div><div><dt>May be blocked when</dt><dd>Historical/projection state unavailable</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Restore Latest</h3><span class="pl-control-card__purpose">Requests confirmed restore to This Server Phone</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">After confirmation and guards</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Checkpoint → restore → service restart → health validation</dd></div><div><dt>Success looks like</dt><dd>Restored and health evidence</dd></div><div><dt>May be blocked when</dt><dd>Location, maintenance, unresolved guard, active restore, or validation failure</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Manage / details / copy evidence</h3><span class="pl-control-card__purpose">Opens details or copies bounded evidence</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When an item exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery cards</dd></div><div><dt>What happens next</dt><dd>Shows retained status</dd></div><div><dt>Success looks like</dt><dd>No safe evidence available</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Backup & Restore states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Backup & Restore status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Backup & Restore cannot safely continue. Examples: Target, location, lock, or stale projection guard; Picker unavailable, location missing, read-only, or low space; Backup unavailable, repository mismatch, or verification failure.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Create a backup, verify it, and use Preview Restore before a confirmed restore.`
- `Choose a backend-discovered location when needed; history keeps older restore points tied to their original location.`
- `Resolve stale/saved projection status or reconnect an unavailable location before retrying a write.`

## When something is unavailable

Active restore, maintenance locks, unresolved guards, and stale projection write blocking are safety controls, not successful completion.

## Safety / trust boundaries

Restore is backend/worker-owned, requires confirmation and a pre-restore checkpoint, and ends with post-restore health validation. The browser cannot write backup storage directly or submit a trusted raw path.

## Related Feature Journey

[Backup & Restore Feature Journey](../enterprise/journeys/recovery.md)

## Related technical references

[Backup/recovery architecture](architecture/backup-recovery.md) · [Security boundaries](security-boundaries.md)
