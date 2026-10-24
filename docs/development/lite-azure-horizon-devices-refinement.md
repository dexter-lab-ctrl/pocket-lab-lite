# Azure Horizon Devices — source implementation and deferred qualification

> **Status:** [IMPLEMENTED] source changes committed to `feat/azure-horizon-devices-ui`; [UNVALIDATED] no tests, checks, builds, screenshots, benchmarks or runtime qualification were executed. **Do not merge until stabilization.**

## 1. Objective and baseline

Refine the existing Devices workspace without rebuilding its React/Vite PWA, replacing backend contracts, or introducing a separate theme. The authoritative baseline is remote `main` at `19ab217e42b4e585db7d21f52ff15d893bf5c510`. Source-only enhancements target semantic connections, saved-state truthfulness, Azure Black/Daylight/System consistency, clear overview and conditional technical facts.

## 2. Architecture and authority

```text
React/Vite PWA → Caddy → authenticated FastAPI /api/lite/*
  → NATS/JetStream → worker/node agent/supervisor
  → sanitized events/heartbeat/evidence → FastAPI → UI
```

No browser shell, NATS client, PM2 execution, Tailscale mutation, user identity repair, invite generation, secret storage or offline write queue was added. FastAPI remains authoritative for device status, capability, readiness, invitation, identity, restart delivery and removal assessment. A running PM2 process alone never proves connectivity.

## 3. Exact PR reuse matrix

| Reference | Existing source used | Consumption / boundary |
| --- | --- | --- |
| #606 shared UI | `src/lite/LiteUi.jsx`: `PageHeader`, `GlassCard`, `LiteButton`, `LiteRefreshButton`, `LiteOperationalStory`, `LiteFlowStatusPanel`, `LiteActionRow`, `deviceLinkState`; `src/lite/components/LiteSafeForms.jsx`: `LiteField`, `LiteProtectedConfirmation` | Imported and used by `src/lite/LiteDevices.jsx` and `src/lite/devices/DeviceCard.jsx`; no competing primitives |
| #622 Azure themes | `src/lite/theme/azureHorizonTokens.css`, `src/lite/theme/azureHorizon.css` | Scoped Devices rules in `src/lite/devices/azureDevices.css` consume existing `--azure-*` tokens; html appearance is inherited, no new provider |
| #623 shared Manage geometry | `src/lite/components/useDesktopManageGeometry.js` | `DeviceDetailsPortal` in `src/lite/LiteDevices.jsx` consumes `panelRef`, `desktopPanel`, `panelStyle`, `announcement`, `reset`, `startPanelInteraction`, `adjustPanelWithKeyboard` |
| #624 protected interactions | `src/lite/components/LiteSafeForms.jsx`; `src/hooks/useLiteDeviceRemovalFlow.js`; `src/hooks/useLiteAddDeviceFlow.js` | Existing protected confirmation, invitation/removal assessment and authorization boundaries retained |
| #588 60 FPS contract | `src/performance/`, `tests/e2e/lite-performance.spec.ts`, `scripts/dev/lite/check-ui-performance-evidence.mjs` | Existing budgets untouched; Devices scenarios are additive, not a replacement |

## 4. Desktop and mobile

The existing application shell is unchanged. Devices continues to render `PageHeader`, `LiteOperationalStory`, freshness, `LiteNextSteps`, `DeviceRelationshipMap`, Remote Access Health, Add Device, cards and lazily loaded Manage. A compact operational summary was added below the relationship map using projected fleet data, with explicit unconfirmed values for saved/expired state.

The relationship map preserves the server-host identity, uses horizontal/stacked existing layout, shows text and semantic icons as well as colored rails, and keeps peer identity stable. New explicit presentation labels cover joining, waiting, stopped, blocked and stale; the visual link is no longer a claim of fresh connectivity for saved state. Capped or progressively revealed many-device topology remains a future optimization; the present map still renders every peer.

The card now exposes independently reported agent and supervisor state where present; missing facts remain 'Not reported'. The existing Manage entry and technical disclosure remain in place; no duplicate Manage button was added.

Responsive CSS uses the existing Azure tokens and a single Devices tree for light, dark and system. It scopes inputs, services, cards, geometry controls, code/technical blocks, dialogs and safe-area behavior. The mobile breakpoint remains 700px. No additional theme provider, remote font, animation engine or polling loop was introduced.

## 5. Connections and remote access

`deviceRelationshipPresentation` is a **UI mapping**, not a new backend lifecycle. Underlying `deviceLinkState` continues to own canonical connection classification. UI labels distinguish Connected, Repairing, Disconnected, Joining, Waiting, Offline, Agent stopped, identity blocked and saved/unconfirmed.

Remote Access Health still uses `remoteAccessPresentation`, `remoteAccessSummaryRows` and `remoteAccessDetailRows`. IP display is guarded by fresh readiness, not merely by the existence of an address in an old payload. Tailscale and NATS reachability remain separately reported; read-only health checks remain side-effect-free.

## 6. Manage, device responsibilities and data facts

`DeviceDetailsLazy.jsx` and `DeviceActionPortal.jsx` remain the source of technical facts, role controls, services, history, health, backup and model selection. `DeviceRoleManager`, `DevicePhotoBackup`, `DeviceHealthHistory` and `DeviceModelPickerLazy` were not replaced. The existing desktop movable/resizable, keyboard arrow and reset controls still use the shared hook, while mobile presents a bottom sheet. Detailed restructuring into eight individually selectable Manage groups is **[MISSING]**; current sections remain the production baseline pending design/interaction review.

Metrics are only displayed where reported; missing values are not filled with percentages or thermal readings. Backend-only evidence and secrets remain outside normal UI.

## 7. Onboarding, invitations, recovery and safe removal

The existing `useLiteAddDeviceFlow`, name normalization and server-side duplicate/identity protections remain authoritative. Name entry, responsibility selection, backend invite request, allowed copyable command, joining steps, backend acceptance and fresh-heartbeat confirmation are unchanged. No invite was created.

`safeRestartSteps` and restart status querying still distinguish request acceptance from actual recovery. A disconnected or stopped agent is not falsely rendered as a recovered backend command. Supervisor recovery and NATS transport remain backend-owned.

`useLiteDeviceRemovalFlow` and `LiteProtectedConfirmation` still require authoritative impact assessment and preserve protected Server Host and authorization limitations. Healthy online devices are not automatically removed. Existing role, health history, DevicePhotoBackup and model picker interactions are preserved, not reimplemented.

## 8. Accessibility, contrast and low-power behavior

New semantic statuses remain textual, with distinct icons. Focus styling uses `--azure-focus`, controlled inputs inherit `--azure-input` and `--azure-text`, technical strings can wrap or scroll independently, and cards accommodate small screens. Layout adapts at 700px and narrower 360px. New animations are not required for comprehension; reduced motion disables affected transitions. Contrast ratios, accessible navigation, 200% text scaling, focus behavior and screen-reader results are **[UNVALIDATED]** until browser qualification.

Cards and details remain lazy, no extra resize listeners or continuous animation added, and existing render budgets remain unchanged. Performance impact is unmeasured.

## 9. Tests, stories and qualification tasks (defined, not executed)

- `src/lite/devices/azureDevicePresentation.test.js`: explicit connection labels, saved-state and remote access
- `src/lite/devices/AzureDevices.stories.jsx`: production screen variants, themes, stopped/repairing/offline/invite/protected-host and 200% text
- `tests/e2e/lite-azure-horizon-devices.spec.ts`: state matrix, themes, viewport scaling, Axe and geometry
- `tests/e2e/lite-azure-horizon-devices-visual.spec.ts`: visual reference definitions, no approved snapshots
- `tests/e2e/lite-azure-horizon-devices-performance.spec.ts`: render/mount bounds; existing PR #588 performance suite still authoritative

```bash
npm run test:devices:azure:unit
npm run test:devices:azure:mocked
npm run test:devices:azure:a11y
npm run test:devices:azure:geometry
npm run test:devices:azure:visual
npm run test:devices:azure:perf
npm run test:devices:azure:storybook
npm run test:devices:azure:qualification
npm run build
npm run test:a11y:states
npm run test:mock-regression
npm run test:perf
task lite:check
```

Every command above: **NOT RUN — DEFERRED TO STABILIZATION**. New visual cases: **DEFINED — CAPTURE AND APPROVAL DEFERRED**. Future work must check fixture discoverability, Playwright selectors, contrast and semantics, screenshot review, complete restart/removal/onboarding matrix, performance and physical Android qualification without relaxing thresholds.

## 10. Risks, deferred work and rollback

**Known risks:** unqualified CSS cascade interactions; unmeasured card/relationship-map layout under dense fleets; all new specs unexecuted; UI formatting and accessibility outcomes unverified; card agent/supervisor status field variability; incomplete eight-group Manage IA; not all requested P0–P4 behavior matrices automated yet. No green CI claim is made.

**Rollback:** revert the feature commits, or close the draft PR without merging. Because the changes are primarily source presentation and test definitions, no runtime migration or device configuration rollback is expected. Do not deploy before qualification.

## 11. Follow-up and cross-tab alignment

During Codex stabilization: execute focused units, accessibility/keyboard, mocked source scenarios, visual capture with human approval, geometry tests shared with Apps/Identity, full PR #588 performance gates, then isolated live/physical Android candidate runs when separately authorized. Recheck no unrelated Home/Apps/Identity/Rules/Recovery regressions, backend-derived connectivity, status freshness, and owner-safe operations. Keep `main` clean and this PR in draft pending evidence.
