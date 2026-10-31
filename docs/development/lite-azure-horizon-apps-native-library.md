# Azure Horizon Apps — Native App Library & Management Workspace

> **SOURCE AUTHORED — QUALIFICATION NOT EXECUTED.** This document accompanies a Draft PR. No tests, builds, screenshot captures, accessibility scans, benchmarks, documentation generators, CI reruns, Android/Termux runtime probes, releases or merges were performed in this implementation session.

## Product information hierarchy

```text
Apps (Your library: installed applications)
  → Open (backend-approved same-origin route)
  → Manage (existing responsive portal)
      → Overview (reported app facts)
      → Photos / Safety / Recovery / App setup / Remove (capability-aware actions)
      → Activity (reported action outcomes)
          → Action Details (existing lazy, sanitized details overlay)
Discover apps (backend-catalogued, not installed; install only when eligible)
```

The first screen contains a restrained `PageHeader`, safe-state freshness, installed count, one or more identity-first cards, and a disclosure-based Discover entry point. The previous search/filter UI is shown only for eight or more installed apps; it is not necessary for a small local workspace. An empty installed library remains honest when backend discovery still contains uninstalled applications. PhotoPrism is not hardcoded into the generic library layout.

Card status comes from `selectCanonicalAppState`; categorization, host and description come from registered metadata; protection appears only for a fresh backend-projected protected state. The icon resolver permits only packaged `/assets/apps/*` SVG/PNG/WebP paths, with PhotoPrism's existing asset as an approved fallback and a generic icon when no trusted local icon exists. Unknown hosts and missing capabilities do not become made-up labels. When the backend is unavailable, saved state is identified and mutating actions are disabled.

### Mobile

The library is one column, with 60px contained icons, two 44px-or-taller Open/Manage controls, natural text wrapping, existing navigation clearance, and Azure layout parity. Manage retains `CatalogManagePortal`, `useMobileSheetSnap`, its dedicated grip, body scroll lock, portal stacking, and nested `LiteDetailsPanel`. The Overview screen presents navigable settings rows; selecting a category shows focused content with an All settings back action. There are no gestures on critical app actions.

### Desktop

The library uses a maximum-width adaptive 1–3-column grid; a single app remains deliberately constrained in width. Existing shell/sidebar geometry is unchanged. The same Manage portal retains `useDesktopManageGeometry` for pointer/keyboard Move, Resize and Reset, with a two-column category navigation/content workspace when there is room. Narrow desktop panels may stack without changing the canonical overlay controls.

## Reuse and compatibility

| Authority | Source reused | Approach |
|---|---|---|
| PR #606 | `src/lite/LiteUi.jsx` `PageHeader`, `LiteButton`, `StatusBadge`, `StateSurface`; `AppSummaryCard.jsx` → `GlassCard`; `src/lite/LiteOverlay.jsx` | Reused; no new shared UI/overlay framework |
| PR #622 | `src/lite/theme/azureHorizonTokens.css`, `azureHorizon.css`, `LiteThemeProvider.jsx`, `liteThemeRuntime.js` | Reused semantic tokens and existing Daylight/Dark/System theme resolution |
| PR #623 | `AppCatalogScreen.jsx`, `src/lite/components/useDesktopManageGeometry.js` and Manage section primitives | Extended interior composition, retained dialog/geometry |
| PR #629 | `appsPremiumRefinement.css`, `AppActionRow.jsx`, shared action state | Reused status/interaction patterns |
| PR #634 | `src/lite/components/useMobileSheetSnap.js`, `src/lite/LiteOverlay.jsx` | Reused snapping and safe focus/overlay behavior |
| PR #635 | `PhotoPrismMediaFlowCard`, existing desktop toolbar and nested Action Details | Kept original backend-truthful flow; not replaced with timer progress |
| PR #636 | `appsPremiumRefinement.css` theme-neutral spacing, typography and density | Preserved; new rules use the same geometry for all themes |
| PR #588 | `docs/validation/ui-performance-qualification.md` and the existing performance instrumentation/tests | Preserved the 60 FPS contract and thresholds; qualification deferred |

Source additions are deliberately narrow: `catalogPresentation.js` gains identity, partition and icon selectors; `AppCatalogScreen.jsx` receives the new composition; `appsPremiumRefinement.css` receives scoped styles. No new dependency or parallel navigation/overlay system was added.

### Azure semantic mapping

All new styling uses existing `--azure-canvas`, `--azure-surface`, `--azure-raised`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-border`, `--azure-strong-border`, `--azure-selected`, `--azure-warning`, `--azure-warning-subtle`, `--azure-radius-card`, `--azure-radius-control`, `--azure-shadow`, and existing Apps spacing variables. No new appearance-specific geometry, independent palette or theme provider was introduced.

### Trust, authority and performance

The frontend only reads same-origin Lite APIs and dispatches actions through existing `liteApi`, TanStack Query and `useLiteMutation`. FastAPI, NATS/JetStream and backend workers remain responsible for authority, command admission, execution, media operations and evidence. Unsafe/offline writes fail closed. The generic app registry and PhotoPrism adapter are not bypassed. The existing action state machine, mutation invalidation, polling, saved Dexie snapshots and Zustand UI state remain intact.

No simulated percentages, fabricated completion, indexing-complete claims, raw receipts, logs, private filesystem paths or secrets are added. PhotoPrism's import progress keeps its existing source-driven stage mapping. Action Details remain lazy and backend-sanitized. The library does not pre-render action histories.

## Authored qualification — NOT RUN

The following must be executed in a **separate qualification session**, after inspecting the Draft PR and agreeing on screenshot candidates:

```bash
npx vitest run src/lite/catalog/catalogLibraryPresentation.test.js src/lite/catalog/AppBalancedDensity.test.jsx
npx playwright test tests/e2e/lite-apps-native-library.spec.ts --project=mocked-desktop --project=mocked-mobile
npm run test:a11y:states
npm run build
```

Additional manual/review gates: Storybook native-library stories and snapshots; 320/360/390/430/768/1280px responsive layout; Daylight, Dark and System (both resolved appearances); Open routing, Manage focus trapping/restoration and mobile snap states; PhotoPrism import/backup success and failure; nested Action Details collision checks; keyboard navigation, 200% zoom and reduced-motion; PR #636 pixel/computed-style parity; PR #588 unchanged performance gates on Dev-PC and controlled Android hardware.

The new Playwright screenshots are **unbaselined candidates**. Never accept them automatically. Separately verify actual contrast, keyboard behavior, app-count states, browser-specific back handling and 60 FPS requirements. If documentation generators need updating, do so only in the qualification session.

### Known limitations and follow-up qualification risks

- No runtime or browser measurement is available for this source-only implementation.
- Existing approved screenshots reflect the old Apps composition; their diffs require deliberate human review.
- System appearance and Android installed PWA behavior are unverified.
- The generic icon resolver intentionally rejects remote/custom URLs; a trusted registry icon proxy could be considered later.
- Discover only lists backend-registered, uninstalled applications; it does not invent a marketplace.
- Activity summarizes backend-returned action outcomes, not a full unbounded audit log.
- Prior PR #588 performance thresholds were not changed; new layout cost has not been measured.

## Rollback

The changes exist only on `feat/azure-horizon-apps-native-library-revamp` and target `main` through a Draft PR. The feature branch can be abandoned without altering `main`. No server process, deployment, release tag or Android environment was modified.
