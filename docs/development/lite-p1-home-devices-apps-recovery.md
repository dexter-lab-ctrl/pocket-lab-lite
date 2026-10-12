# P1 — Home, Devices, Apps and Recovery UI enhancements

Status: **PATCH-PROVIDED / COMMITTED WHEN MERGED INTO THE FEATURE BRANCH; UNVALIDATED**. No tests, builds, runtime checks, qualification or CI monitoring have been run.

## Design

Adds a compact shared `LiteNextSteps` read-only projection to the four P1 screens. The existing mature screen structure remains authoritative: cards, status summaries, refresh/freshness, device connection map, action panels, app Manage portal, recovery confirmation and audit evidence all remain in place.

- **Home:** surfaces up to three non-ready workspace areas directly from existing `buildLiteHomeOverview` projection; linked areas use existing navigation.
- **Devices:** identifies up to two peers without a confirmed connection and separates Tailnet/remote-access readiness from local device connectivity; uses existing details panel.
- **Apps:** shows catalog-derived secure-access and setup warnings without substituting app-specific capabilities or assuming that install state implies readiness. Existing app card Open/Manage remains primary.
- **Recovery:** clarifies backup missing/unverified, verified backup without current restore preview and write-blocked state. Guidance opens existing Manage sections; never triggers restore.
- **Shared:** current/saved information classification, up to four items to avoid unbounded DOM, accessible named region, disabled explanation, responsive vertical controls.

## Trust and safety

Presentation only: all inputs originate from existing sanitized API-derived views. No new polling, writes, storage, shell, NATS, secrets, backend endpoints or recovery bypass. Saved/stale information never exposes actionable navigation. Existing backend-owned approval and restore safety controls remain unchanged.

## Tests added / NOT RUN

```bash
task lite:ui:p1:unit
task lite:ui:p1:regression
npm run test:mock-regression
npm run test:a11y:states
npm run test:perf
task lite:check
```

## Risks and deferrals

Need visual/cascade, theme, iOS/Android, keyboard, accessibility and content-state inspection before merging. Deeper cross-screen navigation, generic multi-app contract work, device diagnostics, verification timeline/history, true evidence-based 'since last visit', and further screen-specific redesign remain separate follow-on scope; no inventing change history or running result assumptions.
