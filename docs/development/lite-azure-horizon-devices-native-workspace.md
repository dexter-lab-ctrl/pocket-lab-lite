# Azure Horizon Devices Experience Revamp — Implementation and Qualification Handoff

> **QUALIFIED WITH DOCUMENTED RESIDUALS · DEV-PC AND ANDROID EVIDENCE RECORDED**
>
> This handoff now records the executed qualification for PR #643. Dev-PC build, unit, mocked browser, Storybook, accessibility, visual, documentation and repository gates passed. Physical Android Devices functional/CDP qualification passed for the available read-only surfaces, while the 60 FPS target and hard-gate results remain misses with baseline-normalized `MIXED` / `PLATFORM_DOMINATED` attribution. This is not a production approval; the PR remains Draft.

## 1. Executive summary

This feature changes the default Devices experience from an information-dense diagnostics dashboard into a native-inspired device library. The visual sequence is **workspace status → three fleet metrics → searchable/filterable device cards → secondary Connections & Topology → existing protected Add Device flow**. A device card contains identity, role/type, one authoritative status, and **Manage**. Management has eight task-oriented sections backed by existing device APIs and frontend state; no new execution API is introduced.

The project remains an edge-first React/Vite PWA backed by Caddy, FastAPI `/api/lite/*`, NATS/JetStream, agents/worker/supervisor and sanitized lifecycle evidence. The browser does not execute commands, communicate with NATS, own enrollment identity, or cache credentials.

## 2. Authoritative repository baseline

| Item | Source |
| --- | --- |
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Authoritative base | `main` at `cfe34e6a5d36b7503469f3e79a08c1a90eb49d46` |
| Implementation branch | `feat/azure-horizon-devices-experience-revamp` |
| First implementation commit | `e672c0046e4b425a194f439c3bb9d9d6939ee899` |
| Final branch head | Verify from GitHub after the final documentation commit; this handoff is regenerated from the stabilized branch |
| PR | [#643](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/643), open Draft against `main`; no merge, release or deployment |
| Server Phone runtime | `main` at `cfe34e6a5d36b7503469f3e79a08c1a90eb49d46`, read-only verified |
| Physical candidate checkpoint | `fe201f5183b17fc7c9bf833b54148745e8403a65` before documentation/test-only changes |

The uploaded project handovers explain history; current GitHub source was inspected as the authority before edits. Prior Azure Horizon PRs #606, #622–#623, #629, #634–#642 and #588 were checked for merge status and relevant source entry points.

## 3. Existing Devices architecture preserved

The original `src/lite/LiteDevices.jsx` owned fleet reads, backend-owned Add Device invite creation, restart progress, removal assessment and confirmation, remote-access presentation, virtualized cards and responsive detail portals. `src/lite/devices/DeviceCard.jsx` rendered a verbose status, micro-topology, agent/supervisor facts and technical action disclosures. `src/lite/devices/DeviceDetailsLazy.jsx` owned lazy device health, roles, backup, capabilities, device history and troubleshooting.

These foundations remain: `selectDevicesScreenView` / `useLiteResource`, `deviceHorizonConnection`, `useLiteAddDeviceFlow`, `useLiteDeviceRemovalFlow`, `useLiteDeviceHealthReviewFlow`, `LiteVirtualList`, safe backend action APIs, protected invite commands and existing modal/portal protections. Neither FastAPI's fleet schema nor NATS command flow was altered.

## 4. Before/after information hierarchy

| Before | Source-authored after |
| --- | --- |
| Detailed operational story, link map and remote access dominate first paint | Compact authoritative story and freshness indication lead |
| Large connection diagram always visible | Connections & Topology collapsed secondary workspace |
| Several operational fact strips in every card | Identity, platform/role, single primary state, Manage |
| Technical/recovery actions embedded on cards | Tasks revealed under Manage; backend authorization unchanged |
| Device details are a long undifferentiated inspection scroll | Overview / Connection / Health / Roles / Services / Backup / History / Technical |
| Limited inventory navigation | Search and All / Connected / Needs attention filters without new API or write cache |

## 5. Desktop layout

The desktop layout keeps the existing `PageHeader`, primary Add Device and Refresh controls, a three-column metric row, search/filter toolbar, and a two-lane `LiteVirtualList`. It uses the same rendered card identity/source objects and retains virtualization and focus pinning. Each card is bounded by shared `--azure-spacing-card` and `--azure-radius-card` tokens. A separate Connections & Topology disclosure offers the server-to-device diagram and Remote Access Health when explicitly opened.

Device **Manage** uses the existing body portal and `useDesktopManageGeometry`: move grip, resize grip, keyboard arrow interactions, reset button, viewport clamping and focus restoration. Destructive confirmation dialogs are *not* made draggable.

## 6. Mobile and tablet layout

At phone widths the metric row retains three compact values, toolbar stacks, and fleet cards use a single lane. Names and roles wrap. Device Manage is a body-portalled bottom sheet, controlled by the pre-existing `useMobileSheetSnap` hook. The grip has a 44px+ interactive target with a visual handle; separate Smaller/Expand buttons are keyboard accessible. Tablet-size layout follows viewport/CSS rules, not a separate feature fork.

Snap target semantics, from the unchanged shared controller: **compact 35%**, **medium 72%**, **expanded 94%** of the visual viewport (bounded). On desktop the mobile snap is inactive; on mobile the desktop geometry controls do not render. The sheet uses a contained scroll surface, safe-area padding, focus trap, Escape close, and originating Manage focus restoration. Native installed-PWA and mobile-landscape behavior remain to be qualified on a real device.

## 7. Device card architecture

`src/lite/devices/DeviceCard.jsx` now renders:

1. Semantic Lucide device type (`Server`, `Monitor`, `Smartphone`) based on **reported** type/platform with a neutral default; no invented hardware classification.
2. Name with bounded wrap, role/OS summary, and protected-server lock.
3. One textual status from `deviceLibraryEntry` / `deviceHorizonConnection`; visible dot color is redundant rather than the only meaning.
4. Accessible Manage action; existing lazy preload remains on intent.

Connection states remain **server, blocked, stale, repairing, joining, waiting, stopped, connected, disconnected, unknown**. Saved state explicitly displays *Saved · connection not confirmed*. A running PM2 or agent process cannot by itself produce Connected. Role and health evidence are not guessed.

No card initiates removal or restart, so action gating still belongs to backend assessments and existing protected flows in Manage.

## 8. Interactive Device Manage navigation

`src/lite/devices/DeviceDetailsLazy.jsx` presents real functional sections rather than eight placeholder labels:

| Area | Current implementation |
| --- | --- |
| Overview | Projected connection, health, identity, responsibility, display model and condensed responsibilities |
| Connection | Heartbeat/activity, identity trust, private link / remote access indications and recovery context |
| Health | Existing detailed resource cards, live/saved posture, dependency impact, recommendations and health timeline |
| Roles | Existing guarded role manager, server-owned capabilities and responsibility boundaries; hidden for protected server |
| Services | Agent/supervisor states, hosted services, responsibilities and backend-authorized Restart Agent when offered |
| Backup | Existing `DevicePhotoBackup` workflow; hidden for protected server; no new backup execution |
| History | Existing bounded device history, now requested on section intent rather than default mount |
| Technical | Existing progressive safe details, capability/trust/removal facts and guarded removal review |

Some sections intentionally share existing device fact primitives. Selection changes only transient UI state; the source of connection/health/action truth remains FastAPI. `key` on the selected device's lazy Manage body resets section state when switching target devices. Identity/role/backup requests continue through original ownership layers; no browser-side write queue was added.

## 9. Connections, topology and remote access

`DeviceRelationshipMap` uses the existing `deviceRelationshipPresentation` (which delegates to `deviceHorizonConnection`) and the existing server/peer relationship rails. On wide viewports server-to-device edges run horizontally; on mobile they stack vertically. Edge color is accompanied by textual state: connected, repairing, waiting, stopped, blocked, disconnected, stale or not confirmed. Peer nodes are keyboard-operable entry points to Manage.

Remote Access Health and its technical details remain based on `remoteAccessPresentation` and `remoteAccessSummaryRows`. Tailnet IP is shown only if ready, live and backend-projected; saved/offline state cannot claim live remote connectivity. Connection and remote access remain separate statuses.

## 10. Shared desktop drag and resize ownership

**Reused unchanged:** `src/lite/components/useDesktopManageGeometry.js`.

**Scoped Devices integration:** `src/lite/LiteDevices.jsx` uses its returned ref, style, move/resize handlers, keyboard adjustment, reset and announcements. The feature intentionally does not create a second drag engine. `DeviceActionPortal` preserves overlay, backdrop and body-layer behavior. Confirmation and destructive review panels retain their existing bounded modal surfaces.

## 11. Shared mobile sheet geometry ownership

**Reused unchanged:** `src/lite/components/useMobileSheetSnap.js` with compact/medium/expanded heights. The Devices grip is the only drag surface; neither device cards nor operational actions acquire broad swipe/drag gestures. `src/lite/devices/azureDevices.css` owns device-specific controls, visual handle, safe-area and scroll styling; sheet selection remains ephemeral.

Add Device remains the existing inline backend-owned progressive disclosure because conversion to a body-portalled multi-step flow could destabilize invite/identity safeguards; this is an explicit **residual design gap**, not a hidden claim of mobile Add Device three-snap coverage. Small restart/removal dialogs remain protected, not automatically expanded/draggable.

## 12. CSS source audit and ownership

Source review identified potentially conflicting historical Daylight/dark portal backgrounds in `src/lite/devices/deviceActionFocus.css`; these were replaced by Azure semantic tokens and obsolete theme-specific blocks removed. A mobile rule forcing `height:auto!important` was relaxed so the shared snap controller may set its height. New Device Library composition lives in **the existing** `src/lite/devices/azureDevices.css`, not a second override stylesheet or new palette.

Retained sources: `src/index.css` legacy base declarations, `src/lite/theme/azureHorizon.css` shared theme rules, `src/lite/theme/azureHorizonTokens.css` semantic tokens, `deviceActionFocus.css` overlay ownership and existing shared component CSS. These were read as source; **computed-style cascade results were not measured**. The authored browser parity suite must uncover residual legacy selector conflicts.

## 13. Semantic token reuse

No new color palette or theme-specific spacing values were introduced. Devices styling references existing `--azure-surface`, `--azure-raised`, `--azure-input`, `--azure-border`, `--azure-strong-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-selected`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-neutral`, `--azure-hover`, `--azure-focus`, `--azure-backdrop`, `--azure-shadow`, `--azure-panel-shadow`, `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card` and `--azure-font-ui`.

The Daylight/Dark/System theme runtime and shared token values were not modified.

## 14. Light/Dark/System parity contract

The Playwright Devices suite compares padding, margins, gaps, typography, border width, min-height and bounding geometry for corresponding Devices nodes across Light, Dark and System at **320 / 360 / 375 / 390 / 430 / 768 / 1024 / 1280 / 1440** pixel widths. Mocked desktop/mobile geometry, overflow, reduced-motion and Axe checks passed. The physical phone rendered Light/Dark/System candidate states and the available touch geometry successfully; 200% text scaling and health-timeline data were unavailable in the selected runtime and remain residuals.

## 15. Haptic feedback integration

The existing `triggerLiteHaptic` from `src/lib/liteNativeFeedback.js` is reused; `triggerLiteTactileFeedback` remains the existing section-selection adapter. Haptics were added to Manage, Refresh, Add Device, metric/filter selection, topology intent, desktop panel reset and mobile snap controls. Existing accepted/success/warning deduplicated feedback for invite, restart and removal is preserved. Support, document visibility and reduced-motion restrictions remain enforced by the shared library. Passive polling and rerenders do not trigger haptics.

Nested photo-backup and individual role-manager actions already use existing shared primitives and may need a follow-up complete haptic matrix audit; no new haptic runtime was created.

## 16. Backend authority, safety and privacy

- Frontend → Caddy → FastAPI `/api/lite/*` → NATS/JetStream → worker/agent/supervisor → sanitized events/evidence → FastAPI → UI.
- Enrolment identity, invite creation, duplicate-device prevention, repair authorization and remote-access readiness remain backend-owned.
- Restart and removal still require the original admissibility/assessment and confirmation logic.
- Protected server hosts are not offered a removal action.
- App/backup/role commands remain in existing backend-owned flows.
- No raw command execution, direct NATS, hardcoded Tailnet endpoint, secrets, raw evidence or offline command queuing was introduced.
- Saved/expired snapshots show *unconfirmed* and suppress relevant live writes.

## 17. Accessibility and interaction

Visible textual connection states supplement decorative colors; Manage/nav/snap controls are actual buttons with labels; the topology node has a keyboard activation path. Existing body portal is dialog-labelled and traps Tab focus; Escape and button close return focus to opener. Responsive layouts use small-screen wrapping and restrained CSS transitions; reduced motion disables newly added motion. No color-only truth indicators were introduced.

Automated Axe checks passed for mocked desktop and mobile. Keyboard, focus return, desktop move/resize/reset, mobile sheet controls and topology activation passed in the mocked qualification. This is not a VoiceOver/TalkBack certification; platform assistive-technology review remains outside the captured evidence.

## 18. Responsive and overflow hardening

The Devices CSS uses bounded grid columns, `min-width:0`, flexible labels and semantic status text. Normal device names wrap at words; numeric/technical values may break as needed. Bottom-sheet grip touch area is at least 44px tall; metric and Manage controls are similarly finger-friendly. Mocked required widths and physical Android touch/overflow inspection passed. Mobile landscape and 200%-text results remain **UNVALIDATED**.

## 19. Source files affected

**New**
- `src/lite/devices/deviceLibraryPresentation.js` — display-only inventory selectors.
- `src/lite/devices/deviceLibraryPresentation.test.js` — source tests.
- `tests/e2e/lite-devices-native-workspace-qualification.spec.ts` — executed mocked Devices qualification.
- `docs/development/lite-azure-horizon-devices-native-workspace.md` — this handoff.

**Modified**
- `src/lite/LiteDevices.jsx` — overview, search/filter, topology, portal and snap.
- `src/lite/devices/DeviceCard.jsx` — simplified card.
- `src/lite/devices/DeviceDetailsLazy.jsx` — task navigation.
- `src/lite/devices/azureDevices.css` — semantic-token responsive composition.
- `src/lite/devices/deviceActionFocus.css` — portal CSS cleanup.
- `src/lite/devices/DeviceCardScreen.test.jsx` — card regression coverage.
- `src/lite/LiteDevices.stories.jsx` — interactive Storybook migration.
- `src/lite/devices/AzureDevices.stories.jsx` — new native library states.
- `tests/e2e/lite-azure-horizon-devices.spec.ts` — existing topology checks adapted for disclosure.

All paths above refer to authored source. The targeted and repository-wide validation results are recorded below; generated contracts and documentation were regenerated after stabilization.

## 20. Reuse traceability matrix (source-backed)

| PR | Source reference | Reused behavior | Change status | Reason |
| --- | --- | --- | --- | --- |
| #606 | `src/lite/LiteUi.jsx`, `src/lite/LiteUx.jsx`, `src/lite/components/LiteSafeForms.jsx` | Existing PageHeader, LiteButton, status/story, safe controls | **Reused unchanged** | Avoid another UI primitive hierarchy |
| #622 | `src/lite/theme/azureHorizonTokens.css`, `src/lite/theme/azureHorizon.css` | Azure Horizon semantic palette, typography and themes | **Reused unchanged** | One color authority for all modes |
| #623 | `src/lite/components/useDesktopManageGeometry.js` | Desktop move/resize/reset/keyboard/clamp | **Reused unchanged**, Devices call site modified | No second drag engine |
| #629 | `src/lite/catalog/` and existing Apps experience | Native Apps progressive layout inspiration | **Reference only** | Design consistency, not a copied component |
| #634 | `src/lite/components/useMobileSheetSnap.js` | 35/72/94 sheet behavior | **Reused unchanged**, Devices call site modified | Shared gesture semantics |
| #635 | Existing Apps UI refinements in `src/lite/catalog/` | Reduced information density | **Reference only** | Avoid duplicating Apps business UI |
| #636 | `tests/e2e/lite-apps-theme-density-parity.spec.ts` | Computed-style theme geometry approach | **New analogous Devices suite**, Apps suite unchanged | Consistent qualification contract |
| #637 | Apps Library and Manage patterns in `src/lite/catalog/` | Device-library and focused Manage structure | **Reference only** | Preserve native product language without cross-domain coupling |
| #638 | `src/lite/LiteHome.jsx` | Native command hierarchy | **Reference only** | Align title/story density |
| #639 | `src/lite/LiteIdentity.jsx` | Guarded Access and semantic state patterns | **Existing backend role checks preserved**, no identity file modified | Maintain authority boundaries |
| #640 | `src/lib/liteNativeFeedback.js`, `src/lite/LiteMotion.jsx` | Haptics, deduplication, reduced-motion policy | **Reused unchanged**, Devices interactions modified | No competing tactile engine |
| #641 | `src/lite/LiteSecurity.jsx` | Safety Manage and theme experience | **Reference only** | Consistent overlay behavior |
| #642 | `src/lite/LiteRules.jsx` | Current theme / user-facing structure | **Reference only** | Keep cross-tab Azure Horizon consistency |
| #588 | `src/lite/components/LiteVirtualList.jsx` | Virtualized list, pinned/focus behavior | **Reused unchanged**, Devices filtering integration modified | Keep low-power performance architecture |

The exact PR/file association was informed by merged PR metadata and the inspected current source; individual historical changes within each PR were not re-proven line by line. This is a source reuse inventory, **not a validated performance claim**.

## 21. Qualification results (executed)

- `src/lite/devices/deviceLibraryPresentation.test.js`: connected, blocked, stale, saved, attention, query/filter and empty states.
- `src/lite/devices/DeviceCardScreen.test.jsx`: concise card, protected server, saved status, Manage affordance and long names.
- Existing `src/lite/devices/DeviceCard.test.jsx` preserved for connection helpers.
- `src/lite/LiteDevices.stories.jsx` existing role/backup/health stories retargeted to focused Manage sections.
- `src/lite/devices/AzureDevices.stories.jsx`: light/dark/system and scenario-based native stories.
- `tests/e2e/lite-azure-horizon-devices.spec.ts` adjusted to open topology before legacy assertions; the Devices matrix passed.
- `tests/e2e/lite-devices-native-workspace-qualification.spec.ts`: mocked states, search, navigation, mobile snaps, desktop panel, accessibility, dark/light/system geometry, haptics and screenshot assertions passed.

Executed evidence:

- `npm run build`: **PASS**.
- Focused Devices Vitest: **13 tests passed**; full `npm run test:unit`: **91 files / 560 tests passed**.
- Devices mocked qualification and related operations/performance sources: **86 passed** across mocked desktop/mobile.
- Storybook: **581 canonical stories documented**, build passed and **17 representative renders passed**.
- Accessibility: Devices Axe suite **36 passed**; repository Axe gate **2 passed** for mocked desktop/mobile.
- Visual snapshots: initial comparisons were inspected, intended differences were approved, then the canonical Devices visual suite passed **192/192** without the update flag. The 189 changed PNG references are intentional PR #643 canonical baselines.
- Geometry/theme: **8 passed** targeted geometry checks; required mocked viewport matrix and Light/Dark/System coverage passed.
- Backend/contract regression: focused device backend tests **38 passed**; repository backend gate **416 passed** with one existing deprecation warning.
- `task lite:docs:generate`: **PASS**; `task lite:docs:check`: **PASS**; `task lite:check`: **PASS**.

Physical Android CDP evidence:

- The repository-owned Windows ADB → WSL bridge was cleaned and freshly established; Chrome package was verified as `com.android.chrome`, CDP attach succeeded, and the exact candidate manifest/header/document/meta SHA boundaries agreed at the physical candidate checkpoint.
- Devices-only CDP qualification ran **13 planned interaction samples**: navigation, inventory render/scroll, search/filter, Manage open, all eight Manage sections, Manage scroll, mobile sheet states, topology expansion/selection, theme states and close/focus return.
- The selected runtime exposed all eight Manage areas. Health timeline data was not projected by the selected runtime and is recorded as unavailable, not invented.
- The candidate was read-only; no destructive action, Server Phone source change, deployment or synthetic Owner credential was required. The only observed request failure was an aborted polling GET for `/api/lite/events` during navigation.
- Physical screenshots are sanitized locally under `.pocketlab-dev/performance/android-devices-fe201f5183b17fc7c9bf833b54148745e8403a65/` and are not treated as canonical Playwright baselines.

Pink screenshot finding:

- Bright pink blocks in physical evidence are deterministic Playwright mask overlays. The Devices-only sanitizer masks dynamic names/facts without specifying a custom mask color, so Playwright renders its default `#FF00FF`. The blocks align exactly with the masked Manage heading, topology name and remote-access fact regions; the underlying UI is normal. This is **not transient rendering** and **not an application visual defect**. Canonical visual snapshots contain no such mask overlay and passed.

Existing CI workflows and performance thresholds were not changed.

## 22. Qualification commands and boundaries

The following commands were run on the feature branch after inspection of the actual repository scripts:

```bash
cd ~/pocket-lab-lite
git fetch origin
git switch feat/azure-horizon-devices-experience-revamp

npm run build
npx vitest run src/lite/devices/deviceLibraryPresentation.test.js src/lite/devices/DeviceCard.test.jsx src/lite/devices/DeviceCardScreen.test.jsx
npm run test:devices:azure:qualification
task lite:docs:generate
task lite:docs:check
task lite:check
```

The physical run used only `npm run test:perf:android:devices` and its bounded baseline variant. The generic seven-screen Android matrix (`test:perf:android-cdp` / `test:perf:android-baseline`) was not run. Existing 60 FPS thresholds were preserved; no threshold or analyzer weakening was introduced.

## 23. Known risks and incomplete requirements

1. **Physical performance residual**: the final three-run Devices baseline-normalized report had `0/13` absolute target passes and `2/13` absolute hard-gate passes. Classifications were `1 PLATFORM_DOMINATED`, `12 MIXED`, `0 APP_INCREMENTAL_COST`; no reproducible Devices-only regression was isolated, so no speculative optimization or threshold weakening was applied.
2. **P5 onboarding design residual**: Add Device remains the existing protected inline progressive disclosure rather than a new native three-snap overlay, preserving invite and identity safeguards.
3. **Health timeline unavailable**: the selected Server Phone projection did not expose this read surface; it is recorded as unavailable rather than synthesized.
4. **Assistive technology / text scaling**: mocked Axe and keyboard checks passed, but TalkBack/VoiceOver and 200% text scaling were not directly validated.
5. **CI**: GitHub CI status must be read from the final pushed PR head; it is not claimed as PASS by local execution.
6. **Pink masks**: physical evidence contains intentional magenta sanitizer masks; this is a capture annotation, not a product defect.

## 24. Follow-up qualification checklist

- [x] Resolve exact current branch SHA and ensure the PR diff is reviewable.
- [x] Run targeted Vitest, existing Devices suites, build checks and backend API regression.
- [x] Run mocked E2E across 320/360/375/390/430/768/1024/1280/1440; 200% text remains UNVALIDATED.
- [x] Check Light/Dark/System computed geometry, contrast, focus and nested panel backgrounds in mocked qualification.
- [x] Inspect projected online, joining, waiting, repairing, offline/saved, blocked, agent-stopped and protected-server states using deterministic fixtures.
- [x] Check desktop horizontal/mobile vertical topology and keyboard target selection.
- [x] Confirm all eight Manage sections expose real information and preserve guarded operations.
- [x] Review invite duplicate/identity mismatch and protected-host removal safeguards through mocked fixtures.
- [x] Confirm non-draggable destructive dialogs, remote-access readiness truth and Tailnet IP suppression.
- [x] Exercise the exact Dev-PC candidate on the physical Android browser through bounded CDP; no feature branch was installed on the phone.
- [x] Check no secrets are retained by frontend storage and no browser direct NATS/shell access.
- [x] Review Storybook stories and inspect/approve canonical visual references.
- [x] Record performance misses and baseline attribution without weakening thresholds.
- [ ] Promote the PR from Draft: intentionally not done while the performance residual and other documented limits remain.

## 25. Rollback

Do not change `main` during this implementation. If qualification identifies regressions, keep the PR draft and revert scoped commits **on the feature branch** using reviewed Git history, or close the unmerged draft PR. Because no backend migrations/contracts or runtime deployment occurred, rollback is a frontend-source and test/documentation operation, not a database, NATS, device-agent or bootstrap rollback. Keep local WSL/Termux worktrees clean and never force push `main`.

**Final declared state:** the implementation, qualification coverage and generated documentation are committed on the feature branch. Dev-PC and functional Android evidence are **VERIFIED**; physical performance is **VALIDATED WITH RESIDUALS** and not a target PASS. The PR remains **DRAFT / DO NOT MERGE**. No merge, release, deployment, Server Phone mutation or main-branch change was performed.
