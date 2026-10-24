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

The relationship map preserves the server-host identity, uses horizontal/stacked existing layout, shows text and semantic icons as well as colored rails, and keeps peer identity stable. New explicit presentation labels cover joining, waiting, stopped, blocked and stale; the visual link is no longer a claim of fresh connectivity for saved state. The map renders six peers initially and places further peer identity/status rows in accessible progressive disclosure; the full fleet remains accessible in the card list. Desktop uses a server-to-peers horizontal relationship; <=700px uses vertical rails.

The card now exposes independently reported agent and supervisor state where present; missing facts remain 'Not reported'. The existing Manage entry and technical disclosure remain in place; no duplicate Manage button was added.

Responsive CSS uses the existing Azure tokens and a single Devices tree for light, dark and system. It scopes inputs, services, cards, geometry controls, code/technical blocks, dialogs and safe-area behavior. The mobile breakpoint remains 700px. No additional theme provider, remote font, animation engine or polling loop was introduced.

## 5. Connections and remote access

`deviceRelationshipPresentation` is a **UI mapping**, not a new backend lifecycle. Underlying `deviceLinkState` continues to own canonical connection classification. UI labels distinguish Connected, Repairing, Disconnected, Joining, Waiting, Offline, Agent stopped, identity blocked and saved/unconfirmed.

Remote Access Health still uses `remoteAccessPresentation`, `remoteAccessSummaryRows` and `remoteAccessDetailRows`. IP display is guarded by fresh readiness, not merely by the existence of an address in an old payload. Tailscale and NATS reachability remain separately reported; read-only health checks remain side-effect-free.

## 6. Manage, device responsibilities and data facts

`DeviceDetailsLazy.jsx` and `DeviceActionPortal.jsx` remain the source of technical facts, role controls, services, history, health, backup and model selection. `DeviceRoleManager`, `DevicePhotoBackup`, `DeviceHealthHistory` and `DeviceModelPickerLazy` were not replaced. The existing desktop movable/resizable, keyboard arrow and reset controls still use the shared hook, while mobile presents a bottom sheet. The header now includes the device type, canonical connection and last-reported freshness; role and backup controls have explicit labeled groups. Fully separate eight-group navigation is **[PARTIAL / UNVALIDATED]**: existing technical/history, services, health and capability sections remain progressive, and no unsupported empty sections have been invented.

Metrics are only displayed where reported; missing values are not filled with percentages or thermal readings. Backend-only evidence and secrets remain outside normal UI.

## 7. Onboarding, invitations, recovery and safe removal

The existing `useLiteAddDeviceFlow`, name normalization and server-side duplicate/identity protections remain authoritative. A header **Add Device** action opens the original disclosure below the device cards; four presentation-only stages guide name, responsibilities, invite and verification. The frontend no longer synthesizes a shell command from a bootstrap URL: it offers only an explicitly backend-delivered `copy_text` or `bootstrap_command`. Backend invite request, joining steps, acceptance and fresh-heartbeat confirmation remain authoritative. No invite was created.

`safeRestartSteps` and restart status querying still distinguish request acceptance from actual recovery. A disconnected or stopped agent is not falsely rendered as a recovered backend command. Supervisor recovery and NATS transport remain backend-owned.

`useLiteDeviceRemovalFlow` and `LiteProtectedConfirmation` still require authoritative impact assessment and preserve protected Server Host and authorization limitations. Healthy online devices are not automatically removed. Existing role, health history, DevicePhotoBackup and model picker interactions are preserved, not reimplemented.

## 8. Accessibility, contrast and low-power behavior

New semantic statuses remain textual, with distinct icons. Focus styling uses `--azure-focus`, controlled inputs inherit `--azure-input` and `--azure-text`, technical strings can wrap or scroll independently, and cards accommodate small screens. Layout adapts at 700px and narrower 360px. New animations are not required for comprehension; reduced motion disables affected transitions. Contrast ratios, accessible navigation, 200% text scaling, focus behavior and screen-reader results are **[UNVALIDATED]** until browser qualification.

Cards and details remain lazy, no extra resize listeners or continuous animation added, and existing render budgets remain unchanged. Performance impact is unmeasured.

## 9. Tests, stories and qualification tasks (defined, not executed)

- `src/lite/devices/deviceHorizonPresentation.js`: display-only connection and fleet-count mapping; fail-closed identity/saved states
- `src/lite/devices/deviceHorizonPresentation.test.js`: explicit offline/joining/stopped/blocked/stale/unknown, counts and no PM2-based connectivity assumption
- `tests/e2e/lite-azure-horizon-devices-operations.spec.ts`: mock-only staged onboarding, duplicate names, invite states, backend-owned recovery, keyboard geometry, mobile sheet and Axe
- `tasks/Taskfile.ui.yml`: dedicated `lite:test:devices:azure:*` tasks built on existing UI preflight infrastructure

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


## 12. Detailed implementation inventory — P0–P4

| Phase | Repository-backed changes | Status / proof boundary |
| --- | --- | --- |
| P0 | `azureDevices.css` consumes shared `--azure-*` tokens across map, cards, form, portal, service and nested Manage content, with static rails and focus styles | [IMPLEMENTED] stylesheet; [UNVALIDATED] cascades, AA contrast, appearance switch |
| P1 | `LiteDevices.jsx` includes Header Refresh + Add Device, operational story, freshness, Next Steps, bounded map, fleet summary, Remote Access Health, server and device cards | [IMPLEMENTED] authoring; [UNVALIDATED] user-visible layout |
| P2 | `DeviceCard.jsx` conditionally shows agent/supervisor read facts; `DeviceDetailsLazy.jsx` maintains RoleManager, health, history, services, technical data and PhotoBackup; `DeviceDetailsPortal` keeps shared geometry and now exposes dialog semantics/focus cycle | [IMPLEMENTED] partial grouping; [UNVALIDATED] nested overlays/drag/keyboard |
| P3 | Add Device guided instructions and move below cards; server-authorized command only; existing invite/restart/removal/role/backup backend flows remain unchanged | [IMPLEMENTED] visual refinements; [UNVALIDATED] safety in browser |
| P4 | Pure unit tests, existing Storybook additions, mocked E2E + new action suite, Axe, visual reference definitions, timing samples, npm and Taskfile tasks | [IMPLEMENTED] test definitions; [NOT RUN] all tests and snapshots |

## 13. Desktop hierarchy and interaction ownership

1. Existing `PageHeader` with one Refresh and one Add Device opener, not a new app shell.
2. Existing `LiteOperationalStory`, freshness, and `LiteNextSteps` show urgency before the relationship map.
3. Bounded `DeviceRelationshipMap` displays protected server identity and reported secondary-device states.
4. `lite-devices-horizon-summary` reads existing fleet data; saved/expired state is never labeled as a confirmed count.
5. Remote Access Health reports Tailscale readiness separately from per-device connectivity, then exposes optional technical rows.
6. Existing server/secondary cards and `LiteVirtualList` preserve virtualization and on-demand details.
7. Add Device disclosure moves after the fleet cards, opened by the header action and preserving the original secure workflow.

**[UNVALIDATED]** Pixel alignment and layout at 320/360/375/390/430/768/1024/1440px.

## 14. Mobile and zoom hierarchy

- The same data/component tree adapts under the established 701px geometry query.
- `useDesktopManageGeometry` returns non-desktop panel behavior; CSS ignores desktop transforms for a full-width safe-area-aware bottom sheet.
- Connection peers stack vertically using static rails; no scroll-driven animated graph or extra theme provider.
- All critical button labels, invitation command code and technical strings wrap or scroll within their own surfaces.
- **[UNVALIDATED]** 200% text zoom, landscape and browser safe-area boundaries.

## 15. Connection-state contract

| Source-backed interpretation | UI status | Confirmation rule |
| --- | --- | --- |
| Protected server role | Protected server host | Never implies removal readiness |
| Canonical online + joined link + fresh/non-saved evidence | Connected | Reported connection, not mere PM2 process state |
| Repair/repairing | Repairing | Backend-reported repair only |
| Joining/accepted/setup | Joining | No automatic completion |
| Waiting/pending/invited | Waiting | No fresh heartbeat claimed |
| Agent stopped | Agent stopped | Do not show reconnect success |
| Offline | Offline | Not a current live connection |
| Explicit disconnected or unknown transport | Disconnected/Not confirmed | Unknown state cannot be green |
| Identity mismatch/blocked/repair-required | Identity check blocked | Explicit repair/rejoin only |
| Saved or expired/stale evidence | Saved · connection unconfirmed | No current online claim |

Canonical `canonicalDevicePresentation` and `deviceLinkState` in `src/lite/LiteUi.jsx` remain authoritative inputs. `deviceHorizonConnection` is **presentation-only**. Peer grouping does not touch command delivery, backend auth, PM2 or agent state.

## 16. Bounded relationship map and low-power contract

`DeviceRelationshipMap` initially shows six peers. Additional named peers remain reachable via `<details>` as text rows, while every fleet card remains accessible in the existing virtualized list. There is no SVG physics layout, remote diagram request, JS animation loop or new observer. CSS rails are static by default; media query stacks the view vertically. The no-animation behavior is deliberate even when reduced motion is not requested.

## 17. Server Host and secondary-card differentiation

The existing `DeviceCard` sets `isServerCard` from protected host flags/roles and leaves Remove/Restart prohibited by existing `canRemoveDevice` and `canRestartDeviceAgent`. Agent/Supervisor facts render only from reported projections. The primary Manage interaction still comes through `LiteOperationalStory`, and technical/safety details remain optional. Saved/expired cards must not imply current NATS connectivity.

## 18. Remote Access Health

`remoteAccessPresentation`, `remoteAccessSummaryRows` and `remoteAccessDetailRows` were preserved. Tailnet IP is shown only when live backend remote readiness is reported. Read paths never call `tailscaled`, restart PM2 or mutate NATS. An unready Tailnet status remains separate from an offline node status.

## 19. Manage information architecture

`DeviceDetailsLazy.jsx` presents device identity, connection status/freshness, system summary and explicit Role/Backup groups, followed by the existing lazy health, operational awareness, history and technical disclosure. The implementation retains `DeviceRoleManager`, `DeviceHealthHistory`, `DevicePhotoBackup`, `DeviceModelPickerLazy`, `LiteProgressiveDetails` and `DeviceFactsPrimitives`.

The eight conceptual groups (Overview, Connection, Health, Roles, Services, History, Backup, Technical) are represented by the existing component sections **where real data supports them**, not by eight newly created empty navigation tabs. **[PARTIAL]** Unified eight-group navigation and keyboard verification remain for stabilization.

## 20. Shared desktop Manage geometry

`src/lite/components/useDesktopManageGeometry.js` provides `panelRef`, `desktopPanel`, `panelStyle`, `announcement`, `reset`, `startPanelInteraction` and `adjustPanelWithKeyboard`. The existing dedicated Move/Resize/Reset controls are preserved; the rest of the form is not a drag handle. The dialog now has an accessible name, modal semantics and Tab cycle. Escape and focus restoration remain owned by `DeviceDetailsPortal`. Small-screen CSS suppresses transforms and desktop controls. **[UNVALIDATED]** Interaction with nested dialogs requires a full focus-safety review.

## 21. Onboarding and duplicate identity guard

Guidance stages are user explanations, not backend state. Backend-owned invite issuance and identity validation remain the only source of enrollment authority. Local duplicate matching does not bypass case/separator insensitive server guards, protected host names, pending/accepted invite checks or enrolled identity mismatch. The UI never overwrites agent env or sends PM2 commands.

## 22. Invite-ready and bootstrap command safety

Only authorized server-generated `copy_text` or `bootstrap_command` may be presented. UI does not construct `curl | bash` from a URL or rebuild expired invite content. The command block scrolls internally; copy feedback remains UI-only. Snapshot definitions mask `.lite-invite-command code` and must undergo human review before baseline approval.

## 23. Joining, Restart Agent, and recovery

`useLiteAddDeviceFlow` remains a UX state machine; accepted invites are not treated as connected until fresh evidence appears. Existing `restartAgent` and status fetch path preserve accepted/queued/working/repairing/failed/unknown states. A command accepted by FastAPI is not proof it was delivered. The UI leaves explicit recovery guidance for stopped agents and identity mismatches, and never resets identity automatically.

## 24. Device removal

`useLiteDeviceRemovalFlow`, backend removal assessment, impact warnings and `LiteProtectedConfirmation` retain the original roles/confirmation semantics. No healthy online device is automatically removed and a protected server host receives no Remove button. Saved/offline status alone does not override backend permission checks.

## 25. Roles, health and services

`DeviceRoleManager` keeps existing role definitions and backend apply/deny. `ResourceMetric` and `SoftwarePosture` keep actual measured values, stale/no-report/unsupported distinctions, and existing thresholds. Service lists preserve reported freshness; running-agent or running-supervisor process status alone does not establish a current NATS path.

## 26. Health history and audit

`DeviceHealthHistory` and `LiteHistoryTimeline` preserve on-demand data and loading/empty/partial states. FastAPI sanitizes records before UI receives them. No new raw evidence endpoint, token printing, private filesystem paths or unrestricted telemetry persistence was added.

## 27. Photo Backup, model picker, and recovery scopes

`DevicePhotoBackup` remains the backed-by-device photo workflow with its existing capability, readiness, progress and backend verification records. It is not presented as a full-app record backup. `DeviceModelPickerLazy` continues to change friendly display metadata only without modifying protected host identity.

## 28. Black, Daylight and System completeness

`azureHorizonTokens.css` remains the semantic authority for surface, raised, border, text, subdued text, accent, focus, input, success, warning, danger, selection and backdrop. `azureDevices.css` is the only new Devices-scoped stylesheet; its selector rules address cards, relationship map, role cards, invites, technical/code areas and contextual portals. The same controls/flow remain enabled or disabled according to backend state regardless of selected appearance.

**[UNVALIDATED]** Full cascade audit, measured WCAG contrast and physically rendered dark-surface completeness.

## 29. Accessibility matrix

| Area | Source behavior added/preserved | Pending browser qualification |
| --- | --- | --- |
| Connection | Text/icon/rail meanings; list roles; neutral saved state | Screen reader order, every state |
| Page actions | Existing Refresh, one header Add Device; focus rules | Tab order, target size |
| Add Device | Labeled name, checkbox role group, inline error, stages | Error/live announcement, scale |
| Manage | Labeled dialog, Escape, Tab focus cycle, return focus, keyboard geometry | Nested overlays, 200%, focus traps |
| Invite code | Scoped horizontal scroll and masked visual baseline | Clipboard permissions and screen reader |
| Reduced motion | No animated rails, reduced-motion CSS | Device reduced-motion preference |
| Themes | Azure focus/input/foreground tokens | Measured 4.5:1/3:1 AA, disabled controls |

## 30. Test/Storybook inventory and deferred gates

- `src/lite/devices/azureDevicePresentation.test.js` and `deviceHorizonPresentation.test.js`: status mapping and fail-closed evidence tests.
- `src/lite/devices/AzureDevices.stories.jsx`, existing `src/lite/LiteDevices.stories.jsx`: black/light/system and reported device/role/health/service/backup examples.
- `tests/e2e/lite-azure-horizon-devices.spec.ts`: mocked fleet states, responsive widths, appearance and Axe.
- `tests/e2e/lite-azure-horizon-devices-operations.spec.ts`: staged onboarding, name conflict, expired invite, access health, Manage keyboard/focus and mobile sheet.
- `tests/e2e/lite-azure-horizon-devices-visual.spec.ts`: unapproved screenshot references for map/Manage/onboarding with private command masking.
- `tests/e2e/lite-azure-horizon-devices-performance.spec.ts`: lightweight DOM bounds and duration samples; PR #588 budgets untouched.
- `package.json`: `test:devices:azure:*` entrypoints.
- `tasks/Taskfile.ui.yml`: `lite:test:devices:azure:*` entrypoints.

Every item is **DEFINED / UNVALIDATED — NEVER EXECUTED IN THIS SESSION**. Visual cases are **DEFINED — CAPTURE AND APPROVAL DEFERRED**.

## 31. Future stabilization commands — documentation only

```bash
npm run test:devices:azure:unit
npm run test:devices:azure:mocked
npm run test:devices:azure:a11y
npm run test:devices:azure:geometry
npm run test:devices:azure:perf
npm run test:devices:azure:storybook
npm run test:devices:azure:qualification
# Only after explicit human baseline approval:
npm run test:devices:azure:visual
npm run build
npm run test:a11y:states
npm run test:mock-regression
npm run test:perf
task lite:check
```

All commands: **NOT RUN — DEFERRED TO CODEX STABILIZATION**. Visual approval requires explicit human review; never silently update snapshots. CI failures were not investigated or remediated.

## 32. Open risks and honest limitations

- **[UNVALIDATED]** New CSS cascade and 320px / 200% zoom may reveal clipping or theme conflicts.
- **[UNVALIDATED]** The focus-cycling dialog must be qualified against nested model picker/removal overlays.
- **[UNVALIDATED]** Mock scenarios and selectors have not been executed; assumptions may require stabilization.
- **[PARTIAL]** Eight-group Manage navigation remains existing progressive section UI, not a full tab-system replacement.
- **[PARTIAL]** All requested backend restart/invite/role/removal result permutations are not exhaustively simulated in new tests; existing suites remain relevant.
- **[DEFERRED]** Android physical devices, NATS reachability, Tailnet readiness, battery/thermal performance, screenshot approval, measured WCAG contrast and runtime qualification.
- **[DEFERRED]** Cross-tab Apps/Identity geometry regression verification.
- **[VERIFIED]** No backend API endpoints, data migrations, release tags or deployment changes introduced by this source-focused work.

## 33. Rollback and recovery

If a later suite fails: leave PR draft, isolate presentation-file regressions, revert or surgically correct the feature branch commits only. Backend state does not require migration or device rollback because no deployment occurred. If required, close the draft PR without merge; leave `main` untouched. No branch force-push is needed.

## 34. Future cross-tab alignment

Use PR #623 geometry tests as shared movement/resize authority and PR #624 protected-dialog checks as the reference for nested focus. Preserve PR #588 60 FPS budgets, `LiteThemeProvider` from PR #622, and PR #606 shared primitives; do not create a parallel component system. Apply any theme fixes in narrowly scoped, regression-protected shared files.

## 35. Engineering value and release boundary

The source provides a more comprehensible self-hosted connection overview without weakening the control-plane boundary. Better distinction between remote access, agent process, NATS reachability and live heartbeat is the principal operational value; backend evidence remains decisive.

> **IMPLEMENTATION-ONLY SESSION — VALIDATION DEFERRED.** No tests, builds, checks, benchmarks, visual comparisons or runtime qualification were executed. CI failures were not investigated or remediated. PR #630 must remain **OPEN — DRAFT — NOT MERGED** until a separately authorized stabilization session.
