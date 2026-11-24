# H0 — System Health source and evidence audit

**Source basis:** GitHub `main` at `a9f8b2d7625fd84f82dffee5f44bcee20225661e`, 23 November 2026. **Status:** SOURCE-INSPECTED; implementation and bounded qualification completed against candidate `b65d83c2f83229e3abd59e01b33aaecaa5797734`. This audit remains source-led and does not convert isolated candidate evidence into production evidence.

## Confirmed findings

| ID | Classification | Source finding | Scope of correction |
|---|---|---|---|
| SH-01 | VERIFIED / SOURCE DEFECT | `lite_system_health.summary()` counts all unresolved incidents as `active_problems` and uses that count in its attention determination, even if matching observation evidence is stale. | Retain the legacy unresolved count; add current/saved concern fields and derive current attention from fresh unhealthy observations. |
| SH-02 | VERIFIED / PRESENTATION DEFECT | `LiteSystemHealth.jsx` shows raw `target_id`, source, incident state, repair operation IDs and availability codes in ordinary rows. | Centralize display labels; put technical IDs behind disclosure. |
| SH-03 | VERIFIED / PRESENTATION DEFECT | Incident actions say **Diagnose & Fix** and display a disabled Fix button while the executor remains disabled. | Replace with Review issue, Check cause and navigation to existing protected controls. |
| SH-04 | VERIFIED / PRESENTATION DEFECT | Generic saved-observation wording repeats across every evidence row and old unresolved incidents appear under Active Problems. | Split current and saved concerns, consolidate saved-state explanations and keep history available. |
| SH-05 | VERIFIED / SOURCE HARDENING | Projection ingestion assumes `items` and `devices` are sliceable lists. A malformed mapping/primitive can trigger errors; mixed `components` keys can fail sorting. | Accept typed record collections and known component keys only; skip malformed identities without altering stored history. |
| SH-06 | VERIFIED / PRESENTATION DEFECT | The Home System Health preview uses legacy `active_problems` as a current KPI, and includes automatic-repair and verified-recovery counters irrespective of usefulness. | Display healthy/current/older/unknown observations. |
| SH-07 | UNVALIDATED / HISTORICAL DATA ISSUE | Screenshot descriptions mention `3`, `c`, `i` and `k-u` as devices. Their origin cannot be proved from source alone. | Preserve legitimate short IDs. Reject malformed collection shapes and unsafe identity values. Require a separate, authorized read-only runtime provenance investigation before cleanup. |

## Existing flow

`LiteHome.jsx`, `LiteDevices.jsx`, `LiteSecurity.jsx` and `LiteRecovery.jsx` already contain System Health entry points. The Apps experience can reach the normal navigation shell; no new Apps-specific System Health entry was proven in inspected `LiteCatalog.jsx` (which delegates to the catalog implementation).

UI: `LiteSystemHealth.jsx` → `liteApi.healthIntelligence*` → FastAPI `routers/lite_system_health.py` → prepared SQLite reads in `services/lite_system_health.py`.

Writes: committed Phase 3B projection updates → `lite_phase3b_projections.commit_projection_if_changed` → `ingest_projection`. System Health GET requests do not perform live collectors, process restarts or migrations. A POST diagnosis records a sanitized deterministic assessment. The separate repair endpoint remains fail-closed.

## Reference and reuse inventory

| Requirement | Existing source | Reference | Disposition |
|---|---|---|---|
| Shared buttons/cards/state rows | `src/lite/LiteUi.jsx` | PR #606 | Reused; opt-in action-row haptic bridge |
| Safe status surfaces | `src/components/ui.jsx` via `LiteUi.jsx` | PR #606 | Reused |
| Azure Horizon semantic colors | `src/lite/theme/azureHorizonTokens.css` | PR #622 | Reused without introducing a second palette |
| Shared Manage overlay | `src/lite/LiteOverlay.jsx` | PR #606 / #623 | Reused `LiteDetailsPanel` |
| Desktop move/resize | `src/lite/components/useDesktopManageGeometry.js` | PR #623 | Reused as-is |
| Mobile sheet snap | `LiteDetailsPanel` `mobileSnap` | PR #623 | Reused as-is |
| Grouped Manage navigation | `src/lite/components/HomeGroupedSections.jsx` | Existing current source | Reused; opt-in haptic navigation |
| App premium spacing reference | `src/lite/catalog/appsPremiumRefinement.css` | PR #636 | Referenced for spacing, rhythm, token-backed geometry |
| Source contracts and incident model | `lite_system_health.py`, `docs/system-health/contracts.md` | PR #649 | Retained; additive current/saved semantics |
| Haptic behavior | `src/lib/liteNativeFeedback.js` and `LiteButton` | Current repo / PR #640 | Reused; honors unsupported devices and reduced motion |

**New source:** `src/lite/systemHealthPresentation.js` is required because generic component primitives must not encode System Health evidence semantics. No second theme, sheet, state store or execution pathway was introduced.

## Qualification result and limitations

The focused backend, frontend, Storybook, mocked desktop/mobile Playwright and Axe coverage passed on the feature branch. The focused System Health visual suite passed after review of representative light/dark desktop/mobile captures; 40 canonical snapshots were approved. The saved-state correction added safe-read nonce forwarding in the candidate proxy and forced a first live summary revalidation on System Health mount; focused regression coverage proves saved-to-fresh and fresh-to-saved presentation transitions. The physical Android Chrome System Health qualifier consumed the Dev-PC-hosted exact candidate `b65d83c2f83229e3abd59e01b33aaecaa5797734` through the standard-user CDP path, opened Manage and diagnosis, returned a `200` diagnosis response, returned to Home, and observed no repair or preflight execution.

The bounded Android System Health-only performance collector completed three repetitions over nine interactions with 23 exact-SHA System Health responses per repetition. The established PR #588/#589 comparison retained all thresholds and classified every interaction as reproducible **MIXED**: the platform baseline already missed absolute limits and candidate deltas included LoAF/Event Timing residuals; no interaction classified as `APP_INCREMENTAL_COST`, and no attributable optimization was justified. Absolute target and hard-gate passes were both `0/9`; this is a retained performance **RESIDUAL**, not a fabricated pass. The two `/api/lite/events` request failures per run were expected stream aborts during deliberate navigation and were recorded separately from non-streaming System Health failures. The phone’s production checkout and services were observed read-only and were not used as the candidate backend.

The two Devices assertion failures were reproduced unchanged against an isolated worktree at `origin/main` (`a9f8b2d7625fd84f82dffee5f44bcee20225661e`): missing `navigator?.vibrate` in `DeviceModelPickerLazy.jsx` and missing `lite-device-health-strip` in `DeviceCard.jsx`. Both files are unchanged by PR #656, so the failures remain pre-existing and out of scope.

The local full repository gate remains blocked before project checks by the protected Java baseline: `17.0.20.1` is required, while the only installed/available Ubuntu JDK is `17.0.21.1` (the repository sources expose `17.0.18`, not the protected patch). No global toolchain change or guard weakening was made; exact-head GitHub CI remains the authoritative CI result.

Historical short identities remain unmodified. No production SQLite repair, pruning, migration, PM2 change or deployment was authorized.
