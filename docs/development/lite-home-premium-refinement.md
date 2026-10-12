# Premium Home and activity intelligence — implementation handoff

**Status: COMMITTED · UNVALIDATED · NOT MERGED.** This document describes source changes, not proven runtime results.

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

A 30-minute freshness rule does not prove OS-level execution and may conservatively classify legitimate long operations as stale. The 12-event sample and 8 groups are not paginated history. Domain-wide unresolved states other than explicit device command flags cannot safely be inferred. New endpoint/contracts, visual baselines, generated documentation and Android responsiveness require separately authorized qualification. No baseline was auto-updated, and no historical record was changed.

## Test sources — ADDED OR UPDATED, NOT EXECUTED

- \`src/lite/homeActivityEvidence.test.js\`: integer formatting, unavailable counts, safe names and stale running.
- \`src/lite/homeAttentionPriority.test.js\`: deterministic severity and deduplication.
- \`src/lite/components/HomeActivityDetails.test.jsx\`: Activity sections and private review action.
- \`tests/backend/test_lite_phase3c_system_aggregates.py\`: aged lifecycle compatibility.
- Existing Home, activity-cursor, mocked Playwright, Storybook, accessibility, visual and API contracts still require qualification.

## Deferred qualification commands — NOT EXECUTED

\`\`\`bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/backend/test_lite_phase3c_system_aggregates.py tests/backend/test_lite_home_activity_cursor.py
npm run test:unit -- src/lite/homeActivityEvidence.test.js src/lite/homeAttentionPriority.test.js src/lite/components/HomeActivityDetails.test.jsx
npm run build
npm run test:a11y:states
npm run test:visual:overlays
task lite:api:check
task lite:check
\`\`\`

A separate session must additionally review generated OpenAPI/contracts, complete mocked browser interactions and reviewed visual baselines, Dev-PC performance, and isolated Server Phone/Secondary Phone ARM64 compatibility. CI is neither started nor investigated manually by this implementation session.

**Rollback:** Before merge, close the Draft without changing main. After any separately authorized future merge, revert via a reviewable PR, without resetting production databases, deleting private review cursors or altering audit evidence.
