# Premium Home and activity intelligence — implementation handoff

**Status: PARTIALLY QUALIFIED / BLOCKED · OPEN · DRAFT · NOT MERGED.** The implementation and exact evidence are tracked in PR #608; this page records the source-owned behavior and the remaining qualification boundaries.

## Home composition

Default Home reuses PageHeader, LiteRefreshButton and LiteOperationalStory, with a single Refresh. Attention uses LiteNextSteps with at most three initial actionable/reviewable items; healthy service entries are filtered and source-service duplicates are collapsed. Four compact Apps/Devices/Safety/Backups tiles open their canonical areas. One recent event previews activity. The detailed event list, private review cursor, update card, workflow diagram and diagnostics are not mounted as default Home content.

The existing LiteDetailsPanel controls mobile bottom sheet and desktop side panel, focus management, Escape and safe area. Workspace Details has Overview, Service health, Updates and Diagnostics. The existing workspace relationship diagram lives in Service health; LiteReleaseUpdateCard appears only in Updates; LiteTechnicalFacts appears in Diagnostics. No new generic framework or dependency was introduced.

## Truthful activity semantics

Phase 3C prepared reads now count *running* only when lifecycle status is executing and updated within **30 minutes**; *queued/waiting* is separate and older unfinished records are *stale*, not confirmed running. *Completed recently* means successful terminal operations within **seven days**. Historical failed lifecycle rows are retained and separately counted, not automatically treated as unresolved. Only existing explicit active device command attention flags are authoritative enough for the unresolved count; app/recovery/security explicit resolution provenance remains a limitation. SQL counts are exact for the defined window, never capped at 9,999. Unavailable source counts are not represented as zero.

Activity labels are allow-listed; unknown names receive safe generic labels. Twelve recent lifecycle rows remain a bounded sample, not a complete history. Repeated failures are grouped only with a known operation family, entity relationship and one-hour occurrence window; a group is **historical**, not an invented current incident. Recovered lifecycle IDs that finish successfully are no longer counted as failures. Cross-operation recovery is not inferred.

\`GET /api/lite/home/activity-history\` reads the existing prepared history snapshot on demand and exposes only allow-listed fields with private/no-store cache control. The Activity panel has Attention, Running, Recent and History sections; its personal SQLite review cursor is fetched only after the panel opens. Marking history reviewed does not resolve an issue, approve an action, clear audit history or retry any operation.

## Architectural boundaries

React/Vite → Caddy → FastAPI → NATS/JetStream → worker/agent/supervisor → sanitized evidence → prepared API → UI remains unchanged. TanStack Query manages reads, Dexie remains sanitized snapshots, Zustand remains UI-only, and existing XState workflows continue to own guided UI journeys. No new migration, worker command, scheduler, frontend shell execution, browser-held backend secrets, or direct NATS connection was added.

## Limits and risks

A 30-minute freshness rule does not prove OS-level execution and may conservatively classify legitimate long operations as stale. The 12-event sample and 8 groups are not paginated history. Domain-wide unresolved states other than explicit device command flags cannot safely be inferred. The bounded isolated Android runtime lane is qualified separately from Home browser rendering; Android Chrome/CDP rendering remains blocked when its documented bridge is unavailable. No production baseline, historical record, media library, credential, or audit history was changed.

## Validation record

- Backend compilation and focused backend coverage pass; the focused cursor, projection and audit-scope set is 29 passing tests.
- Frontend unit coverage is 301 passing tests; the Vite build and Storybook qualification pass.
- Accessibility, overlay visual, canonical visual, visual-state, content-stress, P4 and component-performance gates pass on the Dev-PC.
- The exact isolated Android candidate lane passes with run-owned NATS/JetStream, synthetic authentication, recovery, cleanup and production-baseline preservation. This is runtime/API evidence, not a physical Home browser-rendering pass.
- The Android Chrome/CDP preflight is blocked by the unavailable documented Windows bridge. Mocked performance remains partial where unchanged cross-tab/device surfaces exceeded local timing budgets; thresholds were not relaxed.
- Generated OpenAPI/contracts, platform catalogs, architecture, knowledge, lineage and Codebase Map outputs are regenerated from canonical source and must remain exact-head evidence.

## Deferred to Future PRs — Not a PR #608 Merge Blocker

### Exhaustive, paginated activity history

PR #608 intentionally supports the existing bounded prepared-history presentation only. It does not claim that the twelve-event sample is the complete record. A follow-up should add backend-owned pagination with stable cursors, indexed filters/time windows, long-history scalability, per-user review semantics, evidence linkage and Android low-power limits.

### Authoritative unresolved/recovered operation classification across Apps, Recovery and Security

PR #608 intentionally uses only existing lifecycle and recovery evidence. It does not infer that a historical failure remains open, that an unrelated success resolved it, or that an operation recovered without authoritative provenance. A follow-up should define domain-specific resolution sources, immutable linkage, recovery provenance, cross-domain tests and truthful unavailable/ambiguous states.

Both items are explicit scope boundaries, not PR #608 merge blockers. The current bounded history, lifecycle classification, explicit device attention flags, personal cursor isolation and fail-closed unavailable states remain supported.

## Remaining qualification commands

\`\`\`bash
LITE_BASE_URL='<exact isolated candidate origin reachable by Android Chrome>' npm run check:perf:android-cdp
LITE_BASE_URL='<exact isolated candidate origin reachable by Android Chrome>' npm run test:perf:android-cdp
\`\`\`

These commands require the documented physical Android Chrome bridge and a candidate origin; they must not be replaced by a Dev-PC browser or a production deployment. CI must be rechecked against the exact final feature SHA after the final docs/contracts commit.

**Rollback:** Before merge, close the Draft without changing main. After any separately authorized future merge, revert via a reviewable PR, without resetting production databases, deleting private review cursors or altering audit evidence.


## Azure Horizon Home panel follow-up (PR #626 qualification)

Workspace details and Recent activity now have a qualified Dev-PC implementation on `fix/azure-home-panel-premium-refinement`, with shared scroll navigation, semantic activity surfaces, Azure-scoped Daylight/Black styling and shared desktop move/resize. Unit, mocked browser, accessibility, Storybook and build gates pass after two source fixes. New visual snapshots remain **not approved**, the production synthetic-owner harness is disabled, and physical Android CDP attach is blocked. Exact-head CI passed; local and earlier PR #588/#589 evidence retains one documented pre-existing Devices performance residual. The definitive source map and evidence matrix are in [Azure Home panel refinement](lite-home-azure-panel-refinement.md). Treat the branch as **OPEN / DRAFT / NOT MERGED** while the visual, owner and Android evidence boundaries remain unresolved.
