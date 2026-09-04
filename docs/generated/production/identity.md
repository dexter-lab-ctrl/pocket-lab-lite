---
title: "Identity & Access"
description: "Identity & Access owns local human credentials, passkeys, sessions, recovery codes, purpose-bound step-up, and safe identity-class visibility. Opt-in Enterprise Mode uses server-owned memberships and roles. Device identities and the separate API-token path remain outside this tab."
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

# Identity & Access

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Identity & Access owns local human credentials, passkeys, sessions, recovery codes, purpose-bound step-up, and safe identity-class visibility. Opt-in Enterprise Mode uses server-owned memberships and roles. Device identities and the separate API-token path remain outside this tab.

## What this tab is for

Identity & Access owns local human credentials, passkeys, sessions, recovery codes, purpose-bound step-up, and safe identity-class visibility. Opt-in Enterprise Mode uses server-owned memberships and roles. Device identities and the separate API-token path remain outside this tab.

## What you see at a glance

- `Personal Mode owner claim/connect link, passkey and Advanced setup fallback`
- `Sign-in with passkey, password, advanced sign-in, and recovery access`
- `Passkeys, password, recovery codes, active sessions and Sign Out`
- `Enterprise Mode: Your access, current server-resolved role, People, activity, role/status and Active/Inactive`

## Main cards and sections

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Personal Mode owner claim/connect link, passkey and Advanced setup fallback</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Sign-in with passkey, password, advanced sign-in, and recovery access</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Passkeys, password, recovery codes, active sessions and Sign Out</p></article>
<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>Enterprise Mode: Your access, current server-resolved role, People, activity, role/status and Active/Inactive</p></article>
</div>

## Buttons, controls and options

<section class="pl-card-grid" aria-label="Buttons, controls and options">
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Create your passkey / Add passkey</h3><span class="pl-control-card__purpose">Starts WebAuthn registration</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">HTTPS/WebAuthn requirements and eligible session</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Owner claim and Passkeys</dd></div><div><dt>What happens next</dt><dd>Server verifies a one-use challenge</dd></div><div><dt>Success looks like</dt><dd>Completed passkey state</dd></div><div><dt>May be blocked when</dt><dd>Browser, origin, RP ID, or challenge constraint</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Sign in with passkey / password / advanced sign-in / Recover access</h3><span class="pl-control-card__purpose">Requests supported authentication or recovery</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">When the required credential/recovery code exists</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Sign-in</dd></div><div><dt>What happens next</dt><dd>Server creates/updates a session</dd></div><div><dt>Success looks like</dt><dd>Server accepted / Verifying / Completed</dd></div><div><dt>May be blocked when</dt><dd>Preparing, Waiting for Pocket Lab, Blocked, or Failed</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Rename / Save rename / Revoke</h3><span class="pl-control-card__purpose">Changes friendly name or revokes a passkey</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For an owned passkey</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Passkeys</dd></div><div><dt>What happens next</dt><dd>Server validates and audits change</dd></div><div><dt>Success looks like</dt><dd>Updated passkey list</dd></div><div><dt>May be blocked when</dt><dd>Step-up or final-access safety constraint</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Change Password</h3><span class="pl-control-card__purpose">Changes the local password</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">With current password and valid session</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Password</dd></div><div><dt>What happens next</dt><dd>Affected sessions are revoked</dd></div><div><dt>Success looks like</dt><dd>Completed status</dd></div><div><dt>May be blocked when</dt><dd>Current-password or policy validation failure</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Generate/regenerate recovery codes</h3><span class="pl-control-card__purpose">Creates a one-time recovery-code batch</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For an eligible owner</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Recovery</dd></div><div><dt>What happens next</dt><dd>Displays/copies once; regeneration invalidates prior batch</dd></div><div><dt>Success looks like</dt><dd>Confirmed generation</dd></div><div><dt>May be blocked when</dt><dd>Session/authorization constraint</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Revoke / Sign Out</h3><span class="pl-control-card__purpose">Revokes a session or signs out</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">For an active session</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Sessions</dd></div><div><dt>What happens next</dt><dd>Server invalidates session</dd></div><div><dt>Success looks like</dt><dd>Session no longer active</dd></div><div><dt>May be blocked when</dt><dd>Final-owner or current-session constraints</dd></div></dl></details></article>
<article class="pl-card"><details class="pl-disclosure--compact pl-control-card"><summary><span class="pl-card-kicker">Control</span><h3>Enable Enterprise Mode / Save</h3><span class="pl-control-card__purpose">Requests opt-in mode or membership change</span><span class="pl-control-card__availability"><span class="pl-control-card__availability-label">Available when</span><span class="pl-control-card__availability-value">Only when exposed and authorized</span></span><span class="pl-control-card__toggle" aria-hidden="true"></span></summary><dl class="pl-detail-list pl-control-card__facts"><div><dt>Where</dt><dd>Enterprise</dd></div><div><dt>What happens next</dt><dd>Server resolves role/status</dd></div><div><dt>Success looks like</dt><dd>Updated People/activity</dd></div><div><dt>May be blocked when</dt><dd>Final active Owner protection or authorization</dd></div></dl></details></article>
</section>

## What happens when you use them

Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.

## Statuses and messages

Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.

<section class="pl-status-panel" aria-label="Status matrix"><div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span><h3>Identity & Access states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div><div class="pl-table-wrap"><table class="pl-status-matrix"><caption>Identity & Access status matrix</caption><thead><tr><th scope="col">Status</th><th scope="col">What it means</th><th scope="col">What to do</th></tr></thead><tbody><tr><th scope="row"><span class="pl-status-pill pl-status-pill--ready">Ready / available</span></th><td data-label="What it means">The displayed control can accept a supported request.</td><td data-label="What to do">Select it, then follow the returned progress and evidence.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--working">Working / waiting</span></th><td data-label="What it means">A request is in progress or is awaiting a stated prerequisite.</td><td data-label="What to do">Wait for a fresh state; resolve the named prerequisite before retrying.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--complete">Completed / verified</span></th><td data-label="What it means">The backend returned a bounded result or verification evidence.</td><td data-label="What to do">Review the visible outcome before taking a related action.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--attention">Needs attention / blocked</span></th><td data-label="What it means">Identity & Access cannot safely continue. Examples: Browser, origin, RP ID, or challenge constraint; Preparing, Waiting for Pocket Lab, Blocked, or Failed; Step-up or final-access safety constraint.</td><td data-label="What to do">Read the specific message and use the stated recovery path; do not infer success.</td></tr><tr><th scope="row"><span class="pl-status-pill pl-status-pill--saved">Saved / degraded / failed</span></th><td data-label="What it means">The view is historical, incomplete, or the request did not complete.</td><td data-label="What to do">Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write.</td></tr></tbody></table></div></section>

## Common workflows

- `First owner: claim/connect, create a passkey, choose owner/display/friendly names where offered, or use Advanced setup.`
- `Sign in and manage passkeys, password, recovery codes, and active sessions.`
- `In Enterprise Mode, read the server-resolved role; role names Owner, Admin, Operator, Auditor, and Viewer do not themselves document permissions.`

## When something is unavailable

Blocked, Failed, and Waiting for Pocket Lab do not create access. The final active Owner cannot be removed or demoted.

## Safety / trust boundaries

Passwords, recovery codes, authenticator material, challenges, and session credentials are never printed. WebAuthn validates origin, RP ID, and one-use challenges; browser storage is not authoritative.

## Related Feature Journey

[Identity & Access Feature Journey](../enterprise/journeys/identity.md)

## Related technical references

[Identity guards](architecture/components/api-guards.md) · [Security boundaries](security-boundaries.md)
