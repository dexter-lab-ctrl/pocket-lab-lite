# Pocket Lab Lite UX Maturity Contract

**Status:** Source implementation complete on the UX maturity feature branch; execution, generated-doc reconciliation, live Server Phone qualification, and physical Android qualification are intentionally pending the Codex handoff.

## Purpose

Pocket Lab Lite uses one product story across Home, Apps, Devices, Safety, Access, Rules, and Recovery:

> **What is happening? → Does it matter? → What should I do? → What happened when I acted? → Show deeper detail only when requested.**

The default disclosure order is:

```text
Summary
→ next useful action
→ Manage
→ focused details
→ Technical details
```

This contract modernizes presentation only. It does not move execution into the browser and does not weaken existing FastAPI, NATS/JetStream, worker, agent, supervisor, audit, security, recovery, or approval boundaries.

## Plain-language boundary

Normal product UI describes **Pocket Lab behavior**, not implementation plumbing.

Default user-facing surfaces must not depend on terms such as FastAPI, NATS, JetStream, backend worker, durable consumer, polling policy, projection state, ETag, SQLite, command payload, or raw reason code to explain what a user should understand or do.

Where implementation state needs to be translated, the repository-owned presentation layer in `src/lib/liteUxPresentation.js` converts it to product language before it is rendered.

Examples:

| Implementation concept | Product language |
| --- | --- |
| NATS / JetStream | Pocket Lab connection |
| backend worker | Pocket Lab service |
| projection / snapshot | status information / saved information |
| polling | refreshing |
| backend-owned | Pocket Lab-managed |
| raw reason code | support reference |

Scanner/tool names may appear only where a focused technical/support detail genuinely benefits a technical user; normal Safety storytelling describes the stage or scope instead.

## Shared semantic primitives

`src/lite/LiteUx.jsx` owns the product-level patterns:

- `LiteFreshness`
- `LiteSectionHeader`
- `LiteEmptyState`
- `LiteTechnicalFacts`
- `LiteHistoryTimeline`
- `LiteActionOutcome`
- `LiteConsequenceSummary`

Existing lower-level primitives remain in `LiteUi.jsx`, `LiteOverlay.jsx`, and the progressive-detail components.

## Technical Details contract

Technical Details are collapsed by default and must contain useful, sanitized operational facts.

Good technical facts include:

- checked/observed time;
- device or scope;
- current state;
- duration;
- whether anything changed;
- what remained protected;
- a bounded troubleshooting reference.

Technical Details must not expose raw logs, raw evidence, tokens, passwords, API keys, private keys, private Android paths, browser-held backend credentials, command payloads, or unsanitized reason codes.

## Freshness contract

Every primary tab must make freshness understandable without exposing cache mechanics.

Supported product states are:

- **Up to date**
- **Refreshing…**
- **Showing saved information**
- **Information may be out of date**
- **Current information unavailable**

Terms such as stale time, cache state, ETag, snapshot revision, or polling cadence are implementation details and remain hidden.

## History contract

History uses one narrative shape:

```text
Time
Event
Outcome
Optional safe detail
```

Small histories use `LiteHistoryTimeline`. Large or paginated histories may retain virtualized domain components, but their copy and visual semantics must follow the same pattern.

## Consequence confirmation contract

Consequential confirmations answer four questions before the user proceeds:

1. What will happen?
2. What will not happen?
3. Can it be undone?
4. Will anything become unavailable?

This applies to device removal, restore, app removal, deeper safety checks, access changes, and future consequential actions.

## Tab stories

### Home

Home is the narrative of the workspace, not seven mini dashboards. It shows current workspace status, what needs attention, the next useful action, key areas, freshness, and on-demand workspace/technical details.

### Apps

An app card answers whether the app is ready and what the user can do. Normal flow is **Open / Manage**; action outcomes describe what happened, what changed, what did not happen, and what stayed protected.

### Devices

Devices emphasizes **Server Phone ↔ device** relationships. Connected, repairing, and disconnected states are visually distinct. Diagnostics are translated into connection, health, recovery, app/storage responsibility, and safe technical facts.

### Safety

Safety Center remains summary-first. Normal users see current posture and next action. Coverage, findings, check path, history, protected records, and technical details open only when requested.

### Access

Access answers who can access Pocket Lab, how the current person signs in, where they are signed in, and how they can recover access. Governance internals and raw session material remain hidden.

### Rules

Safety Rules explain what Pocket Lab protects and why a protected action was allowed or blocked. A Rules decision is not represented as proof that the downstream action completed.

### Recovery

Recovery tells a confidence story: **backup → verified → preview → checkpoint → restore readiness/health**. Restore confirmation explains consequence and reversibility before any protected work begins.

## Global shell

- Primary navigation uses **Home, Apps, Devices, Safety, Access, Rules, Recovery**.
- Offline mode says **Using saved information** rather than treating safe read-only fallback as a blank/error experience.
- Toasts are transient acknowledgement only; durable results stay near the action.
- PWA update messaging explains what remains protected.
- Reduced-motion behavior remains supported.

## Validation surfaces

Repository-owned validation sources for this contract include:

- `src/lib/liteUxPresentation.test.js`
- `src/lite/LiteUx.stories.jsx`
- `tests/backend/test_lite_ux_maturity_contract.py`
- `tests/e2e/lite-ux-maturity.spec.ts`
- existing visual, accessibility, mocked, live synthetic-owner, and PR #588/#589 performance qualification paths.

Final generated documentation and real-device proof must be produced from the exact feature head during the Codex execution session before merge readiness is claimed.
