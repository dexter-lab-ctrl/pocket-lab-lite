# P2 — Safety, Identity & Access and Rules UI

**Status: CODE-PROVIDED ON FEATURE BRANCH; UNVALIDATED.** Tests, builds, runtime qualification, Android checks, visual baselines, and CI monitoring intentionally not executed.

## Objective

Introduce low-power, evidence-led cross-tab summaries above existing controls while preserving rich scanner, access-governance and rule-policy detail workflows.

### Safety

The Safety Center surfaces reported score provenance, active Quick/Full/App scan profile, number of review items, checked-count indicator and last check. Avoid reporting missing scores as clean, and explain that coverage, freshness, excluded targets and partial/timed-out checks must be reviewed in existing Manage Safety. No scanner or profile execution change.

### Identity & Access

Show sign-in state, server-projected role, Personal/Enterprise mode and browser support for passkeys; explain that role labels are not authorization and mode switching may terminate the current session. Keep existing owner/passkey enrollment, session management, enterprise persons/roles and backend approval controls unchanged.

### Rules

Show policy mode, protection-engine readiness, activation state and recent decisions. Explicitly distinguish hypothetical simulation, server authorization, command acceptance and confirmed execution. Preserve protected approval/activation/rollback, policy audit and enterprise sections.

### Shared P2 components

`src/lite/components/LiteEvidenceGuide.jsx` is read-only and bounded to five sanitized, caller-supplied facts; it has no network calls, commands, storage or independent authority. CSS honors narrow/mobile layouts, reduced motion, visible focus through existing controls and current theme tokens.

## Tests and tasks (added, not run)

```bash
task lite:ui:p2:unit
task lite:ui:p2:regression
npm run test:mock-regression
npm run test:a11y:states
npm run build:budget
task lite:check
```

Storybook fixtures cover partial Safety coverage, saved Access and a Rules update in progress. These are UI fixtures, not runtime qualification.

## Limitations and future work

Real scan coverage/confidence modeling, backend-verifiable scan comparisons, full role/session-impact previews, richer human-friendly Rules builder and deterministic conflict checking require separate server-owned contracts and UI implementation. This increment does not invent evidence, authorization, scan progress or policy capabilities.

## Risk before future merge

Review score semantics, active scan state, current-session role precedence, mode changes, Rules activation status, CSS cascade across dark/daylight themes and mobile focus/spacing. Everything remains unvalidated by request.
