---
title: "Security & Safety"
description: "Security & Safety runs bounded Quick Safety Check, Full Local Check, and PhotoPrism App Check profiles through FastAPI, NATS/JetStream, and workers, then presents normalized and sanitized results."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1e5f5d670709b6324dce94d69b2ded047b1f786d63494cb256639742a6f6112d
schema_revision: 1
validation_status: generated
---

# Security & Safety

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Security & Safety runs bounded Quick Safety Check, Full Local Check, and PhotoPrism App Check profiles through FastAPI, NATS/JetStream, and workers, then presents normalized and sanitized results.

## What this tab is for

Security & Safety runs bounded Quick Safety Check, Full Local Check, and PhotoPrism App Check profiles through FastAPI, NATS/JetStream, and workers, then presents normalized and sanitized results.

## What you see at a glance

- `Quick Scan / Quick Safety Check for the default low-power scope`
- `Full Scan / Full Local Check for explicit deeper local review`
- `App Scan / PhotoPrism App Check where enabled`
- `Safety Center Manage sections: Overview, Changes, Issues, Check path, Evidence, History, Technical details`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Quick Scan / Quick Safety Check for the default low-power scope</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Full Scan / Full Local Check for explicit deeper local review</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>App Scan / PhotoPrism App Check where enabled</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Safety Center Manage sections: Overview, Changes, Issues, Check path, Evidence, History, Technical details</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Choose scan</h3><span class="pl-control-card__purpose">Requests the selected profile</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When the profile is enabled</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Security header</dd></div><div><dt>What happens next</dt><dd>Shows progress and execution stages</dd></div><div><dt>Success looks like</dt><dd>Completion or review state</dd></div><div><dt>May be blocked when</dt><dd>Profile unavailable or preflight fails</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Show check path</h3><span class="pl-control-card__purpose">Reveals the bounded execution path</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a result exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Safety Center</dd></div><div><dt>What happens next</dt><dd>Expands details</dd></div><div><dt>Success looks like</dt><dd>Visible path</dd></div><div><dt>May be blocked when</dt><dd>No result is available</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Open history / Open all review items</h3><span class="pl-control-card__purpose">Navigates to retained summaries</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When history/findings exist</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Safety Center</dd></div><div><dt>What happens next</dt><dd>Shows reviewable normalized items</dd></div><div><dt>Success looks like</dt><dd>Rows and timestamps</dd></div><div><dt>May be blocked when</dt><dd>No retained items</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>View evidence / finding details</h3><span class="pl-control-card__purpose">Shows sanitized evidence and details</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When evidence is retained</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Result cards</dd></div><div><dt>What happens next</dt><dd>Expands bounded detail</dd></div><div><dt>Success looks like</dt><dd>Normalized finding</dd></div><div><dt>May be blocked when</dt><dd>Raw payload, secrets, media, or private paths are excluded</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Protection dashboard / Execution timeline</h3><span class="pl-control-card__purpose">Shows summarized protection and stages</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When supported</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Manage</dd></div><div><dt>What happens next</dt><dd>Displays status progression</dd></div><div><dt>Success looks like</dt><dd>Completion/review/failure state</dd></div><div><dt>May be blocked when</dt><dd>No execution evidence</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Security & Safety states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Security & Safety status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Security & Safety cannot safely continue. Examples: Profile unavailable or preflight fails; No result is available; No retained items.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Use Quick for the default low-power check; use Full only when deeper local scope is needed; use App Scan for supported PhotoPrism checks.`
- `Review completion, findings, evidence, and history rather than interpreting raw scanner output.`

## When something is unavailable

Failure or skipped content is reported as such. Photos/media, secrets, private paths, raw scanner payloads, and raw logs remain excluded.

## Safety / trust boundaries

The UI cannot run a scanner directly. Findings are normalized and sanitized after backend/worker execution.

## Related Feature Journey

[Security & Safety Feature Journey](../enterprise/journeys/security.md)

## Related technical references

[Security architecture](architecture/security.md) · [Security boundaries](security-boundaries.md)
