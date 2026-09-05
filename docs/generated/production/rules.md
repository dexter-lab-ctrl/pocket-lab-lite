---
title: "Rules"
description: "Rules presents bounded policy governance for registered protected actions. FastAPI keeps authority and applies domain invariants before its loopback-only OPA consultation; the browser never calls OPA."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 10afae9869997284bf0e7a7a7ae232ae31e2cb3f8bebdc642b75be0961460422
schema_revision: 1
validation_status: generated
---

# Rules

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Rules presents bounded policy governance for registered protected actions. FastAPI keeps authority and applies domain invariants before its loopback-only OPA consultation; the browser never calls OPA.

## What this tab is for

Rules presents bounded policy governance for registered protected actions. FastAPI keeps authority and applies domain invariants before its loopback-only OPA consultation; the browser never calls OPA.

## What you see at a glance

- `Personal Safety Rules posture, protections, safe templates, active/available rules, diagnostics and sanitized recent decisions`
- `Enterprise tabs: Active Rules, Simulate, Decisions, Approvals, Exceptions, Health`
- `Readiness, active/known-good/runtime-observed revision, degraded state and uncertain recovery where exposed`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Personal Safety Rules posture, protections, safe templates, active/available rules, diagnostics and sanitized recent decisions</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Enterprise tabs: Active Rules, Simulate, Decisions, Approvals, Exceptions, Health</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Readiness, active/known-good/runtime-observed revision, degraded state and uncertain recovery where exposed</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Copy revision</h3><span class="pl-control-card__purpose">Copies the displayed revision</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When a revision is visible</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Active Rules</dd></div><div><dt>What happens next</dt><dd>Copies display text only</dd></div><div><dt>Success looks like</dt><dd>Copied feedback</dd></div><div><dt>May be blocked when</dt><dd>No revision present</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Run Simulation</h3><span class="pl-control-card__purpose">Requests a non-executing evaluation</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">With revision, action, target and mode</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Simulate</dd></div><div><dt>What happens next</dt><dd>Returns allow/block/step-up, constraints and technical reason</dd></div><div><dt>Success looks like</dt><dd>Simulation result</dd></div><div><dt>May be blocked when</dt><dd>Invalid scenario or unavailable policy</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Approve / Reject / Cancel</h3><span class="pl-control-card__purpose">Reviews a bounded approval request</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For an eligible independent reviewer</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Approvals</dd></div><div><dt>What happens next</dt><dd>Passkey step-up and approval status change</dd></div><div><dt>Success looks like</dt><dd>Recorded approval outcome</dd></div><div><dt>May be blocked when</dt><dd>Initiator cannot self-approve, step-up fails, expiry, or cancellation</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Create exception / Revoke</h3><span class="pl-control-card__purpose">Requests an exact temporary exception or its revocation</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For allowed app/device/human/revision scope</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Exceptions</dd></div><div><dt>What happens next</dt><dd>Server records expiry and revision binding</dd></div><div><dt>Success looks like</dt><dd>Visible exception status</dd></div><div><dt>May be blocked when</dt><dd>Role restriction, unsupported scope, or expiry</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Decision filters / details</h3><span class="pl-control-card__purpose">Filters and expands bounded decision evidence</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When decisions exist</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Decisions</dd></div><div><dt>What happens next</dt><dd>Shows action, target, reason, time and sanitized metadata</dd></div><div><dt>Success looks like</dt><dd>Visible decision row</dd></div><div><dt>May be blocked when</dt><dd>No matching evidence</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Rules states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Rules status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Rules cannot safely continue. Examples: No revision present; Invalid scenario or unavailable policy; Initiator cannot self-approve, step-up fails, expiry, or cancellation.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `Personal Mode: review protections, diagnostics (engine, runtime, network boundary, package/revision, reason code), and recent allowed/blocked decisions.`
- `Enterprise: inspect revisions, use non-executing simulation, review decisions/approvals/exceptions/health.`
- `After a valid one-use approval continuation, the requester retries the exact protected action.`

## When something is unavailable

Degraded, uncertain recovery, unavailable policy, insufficient role/assurance, and blocked decisions fail closed. Approval does not execute the protected action.

## Safety / trust boundaries

OPA is loopback-only and additive to FastAPI domain invariants. Evidence excludes raw policy input, command payloads, credentials, secrets, and private paths.

## Related Feature Journey

[Rules Feature Journey](../enterprise/journeys/rules.md)

## Related technical references

[OPA policy-engine architecture](architecture/components/opa-policy-engine.md) · [Security boundaries](security-boundaries.md)
