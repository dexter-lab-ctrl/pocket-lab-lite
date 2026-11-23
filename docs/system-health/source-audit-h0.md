# H0 — System Health source and evidence audit

**Source basis:** GitHub `main` at `a9f8b2d7625fd84f82dffee5f44bcee20225661e`, 23 November 2026. **Status:** SOURCE-INSPECTED; qualification NOT RUN. This audit is not a physical Android observation.

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

## Limitations

No screenshots were supplied as viewable images in this session. Historical suspicious identities, Android UI geometry, light/dark parity, focus, CI, NATS operation, and server-device behavior remain **UNVALIDATED**. No production SQLite repair, pruning or migration is authorized.
