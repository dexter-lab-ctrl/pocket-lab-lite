# P0 — Shared Design System and Action Safety

Status: **IMPLEMENTED IN FEATURE BRANCH; UNVALIDATED**. No builds, tests, qualification, runtime execution or CI monitoring were performed by design.

## Scope

- Shared semantic statuses distinguish accepted, verifying, uncertain, stale, and saved from actual success.
- Shared Lite buttons have an explicit busy state, native disabled behavior, accessible status, and disabled explanations.
- Shared action rows preserve independent click ownership and explain disabled controls.
- Consequence summaries gain an accessible landmark.
- Additive design tokens normalize control sizing, focus visibility, word wrapping, overlay viewport limits and reduced motion.
- Storybook scenarios and Vitest component tests cover representative shared states.

## Invariants

FastAPI owns operational truth. The frontend never dispatches shell commands or connects to NATS, never stores backend secrets, never assumes accepted means completed, and never queues unsafe writes while disconnected. These changes do not modify app, device, security, identity, rules, or recovery execution paths.

## Deferred

P1–P4 screen-specific redesign, new global navigation, capability changes, policy changes, runtime qualification and visual baseline regeneration.

## Later validation (not run for this PR)

```bash
npm run test -- src/lite/LiteDesignSystemP0.test.jsx
npm run build
npm run test:mock-regression
npm run test:perf
task lite:check
```

Before merging, run the repository's established CI and live/Android regression qualification where appropriate. Review all changed states at mobile and desktop widths and verify accessible focus and overlay behavior.
