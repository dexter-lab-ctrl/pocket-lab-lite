# Premium Recovery & Restore Center — implementation handover

> **Status:** SOURCE AUTHORED · NOT RUN — INTENTIONALLY DEFERRED BY OWNER · NOT QUALIFIED.

## Objective and former limitations

Consolidate the previous Recovery hero, competing protection summary, latest-backup
card, and recent activity block into one **Your Recovery Point** hero, a four-stage
**Your Recovery Journey**, and bounded **Recent Activity**. The pre-existing
Manage sheet, lazy details, backend restore engine, XState flow, safe snapshots,
database guard, action API and protective confirmation remain in place.

The previous landing page required scanning several similar cards, duplicated
readiness badges and showed operational detail before user intent. The premium
layout is intentionally summary-first, not a rewritten Recovery execution engine.

## Hierarchy, provenance and interaction

1. **Protection Hero:** reports Backup / Restore / Safety separately. Saved,
   verified and preview-ready are distinct. Offline, stale, missing data, active
   maintenance, failed restores, blocked repository and active work cannot become
   success. Back Up Now remains an existing FastAPI action, disabled while the
   existing guard or live operation applies. Manage Recovery opens the existing
   shared LiteSheet.
2. **Recovery Journey:** four real native buttons: Back Up, Verify, Preview,
   Restore. The explanation is explicitly educational. Clicking stages never
   dispatches an action and never changes server status. The status under each
   stage is derived independently from backup ID, verification, matching preview,
   actual restore record, and bounded operation state. A preview is not restore
   completion. A planned checkpoint is not a created checkpoint.
3. **Recent Activity:** maximum three sanitized records. The preferred source
   is the compact backend-projected recent_activity with stable IDs, recognized
   kinds and actual occurred_at fields. Repeated IDs deduplicate. If that feed is
   absent, a single latest-backup or restore *current record* can be shown but is
   explicitly labeled as a snapshot, not a fabricated historical event. No
   separate "verification event" is invented from a verification field. Unknown
   times are labeled unknown; full cursor history mounts only in Manage → History.
4. **Manage:** existing Backup, Restore, Protection, History sections and
   roving-tab keyboard behavior remain. Backup locations, per-app backups,
   database protection, restore preview, history and troubleshooting are not
   removed. Restore impact is now a focused, safe read-only summary.
5. **Restore confirmation:** existing responsive LiteSheet, backup identity,
   verification and preview, explicit confirmation, server authorization,
   XState-guided guards, backend-owned checkpoint, execution and health
   verification remain intact. The preview count is "Not reported" when missing,
   not automatically zero. Included and excluded lists appear only when supplied.
6. **Progress:** shared operation status UI is mounted when work is active. The
   UI never auto-advances steps, estimates a percentage from elapsed time or
   mistakes an accepted command for a completed restore.

## Data ownership and architecture

React/Vite → Caddy → FastAPI /api/lite/* → NATS/JetStream → worker/agent/
supervisor → sanitized recovery evidence → FastAPI → UI.

Zustand owns only UI sheet selection; XState guides protected user interactions;
TanStack Query owns live reads; Dexie retains sanitized read-only snapshots.
Browser code never uses shell, restic, NATS, backup files, backend secrets, raw
evidence, command queueing, or direct recovery execution. The new presentation
selectors cannot grant restore permissions.

The main screen reads the compact Recovery summary and does not fetch full
history for decorative timeline rendering. Manage and details retain lazy
hydration. No dependency, backend endpoint or destructive capability was added.

## Responsive / accessibility design

Desktop uses a centered stack with a four-stage horizontal journey. Mobile
uses a two-by-two ordered stage grid without horizontal scrolling. The existing
PR #606 LiteSheet provides portal overlay, safe-area, backdrop, focus trapping,
focus return, Escape close and internal scrolling. CSS uses existing theme
tokens, responsive grids and semantic borders. Essential labels wrap, 44px
actions remain accessible, focus-visible is explicit, and semantic button,
ordered-list, heading, time and live-status markup is authored. Status words
remain visible independent of color. Reduced-motion CSS respects the system
preference. WCAG 2.2 AA and 200% / 400% zoom remain **unqualified** pending
browser execution and manual review.

## Files and components

- src/lite/LiteRecovery.jsx — premium landing composition and existing handlers
- src/lite/recovery/recoveryPremiumView.js — backend-truth presentation
- src/lite/recovery/RecoveryJourney.jsx — selectable educational workflow
- src/lite/recovery/RecoveryPremiumTimeline.jsx — bounded, sourced records
- src/lite/recovery/RecoveryManageSheetLazy.jsx — restore impact summary
- src/lite/recovery/RecoveryActionDetailsLazy.jsx — focused impact details
- src/lite/recovery/RecoveryConfirmSheetLazy.jsx — protected confirmation summary
- src/lite/recovery/recoveryPremium.css — scoped theme and responsive treatment
- src/lite/recovery/*.test.{js,jsx} — selectors, component behavior, unknown states
- src/lite/LiteRecovery.stories.jsx — existing and added scenarios
- tests/e2e/lite-recovery-premium-*.spec.ts — mocked UX, Axe, visual and timing
- package.json and tasks/Taskfile.ui.yml — focused future qualification commands

## Tests authored; NOT EXECUTED

- Vitest unit tests: missing data, failed/offline states, stage truth, chronology,
  deduplication, preview identity and count semantics.
- React component tests: accessible stages, selection without dispatch,
  keyboard behavior and timeline distinctions.
- Storybook: first run, verification, preview, restore, database, blocked,
  saved, long text, responsive, Manage, Journey and dark/light candidates.
- Playwright: desktop/mobile layout, manage and details, long text, keyboard,
  reduced motion, no horizontal overflow and Axe serious/critical violations.
- Visual specs: baselines are intentionally **not** generated; future owner
  must generate, inspect and approve screenshots.
- Performance spec: capture relative first paint, stage click and Manage opening
  without adding new arbitrary thresholds or changing owner budgets.

## Future qualification (commands only — do not run in this session)

~~~sh
npm run test:recovery:premium:unit
npm run test:recovery:premium:mocked
npm run test:recovery:premium:visual
npm run test:recovery:premium:perf
npm run build
npm run build-storybook
task lite:check
~~~

Before approving new visual baselines, inspect desktop/mobile screenshots,
long labels, 200% / 400% reflow, light/dark contrast, Android Chrome/PWA
safe areas, touch and TalkBack behavior. Separately verify XState restore
confirmation, database guards, fresh matching preview, duplicate submission
prevention, worker-owned checkpoint and post-restore health behavior on an
approved isolated runtime. Do not execute destructive restore in production.

## Risks / deferred acceptance

Untested CSS cascade and imported component contracts; existing Storybook
fixture provenance; missing screenshot baselines; unqualified accessibility,
performance, physical Android rendering and backend restore regression. The
full source/test matrix is **NOT RUN — INTENTIONALLY DEFERRED BY OWNER**.
No claim of PASS or production readiness is made.

## Enterprise value

Clear separation of recovery creation, trust, review and execution reduces
operator ambiguity. The timestamp-aware record surface improves traceability,
while explicit unknown/blocked states protect decision quality. Focused Manage,
existing backend audit ownership and lightweight Android-first rendering
preserve Pocket Lab Lite's control-plane boundaries.
