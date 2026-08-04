---
title: "Frontend state ownership"
description: "Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 20bffc9aa51b0c5cedb30ae9e2be0a9cfb0925972f81f056d9792accd7d4e7ee
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Frontend state ownership

Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/frontend-state.svg" alt="" loading="lazy" decoding="async" /><span>Frontend state</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/tanstack.svg" alt="" loading="lazy" decoding="async" /><span>TanStack</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/xstate.svg" alt="" loading="lazy" decoding="async" /><span>XState</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/snapshot.svg" alt="" loading="lazy" decoding="async" /><span>Safe snapshot</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/frontend-state.light.svg" aria-label="Open full-size Frontend state ownership mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/frontend-state.light.svg" alt="Frontend state ownership mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/frontend-state.dark.svg" alt="Frontend state ownership mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Frontend state ownership mini architecture. <a href="../../../../../assets/diagrams/production/components/frontend-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth. |
| Primary inputs | Safe GET responses, saved snapshots |
| Primary outputs | Rendered view models, write requests |
| Protocols / uses | IndexedDB, Fetch API |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | ui |
| Runs on | Browser / installed PWA |
| Started / runtime owner | Browser |
| Process owner | React |
| Execution owner | Lite UI |
| Data owner | FastAPI; Dexie is safe read-only fallback |
| Recovery owner | TanStack revalidation and UI workflows |
| Security boundary | Browser trust boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-frontend-state |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-tanstack, brand-xstate, semantic-snapshot |

## Inputs

- Safe GET responses
- saved snapshots

## Outputs

- Rendered view models
- write requests

## Protocols

- IndexedDB
- Fetch API

## Durable state

- safe Dexie snapshots

## Health and readiness

- query freshness
- saved-state metadata

## Evidence

- None declared

## Failure behavior

- offline
- stale snapshot

## Recovery behavior

- refetch on reconnect
- write actions stay disabled

## Connections

### Incoming

- Prepared read, health, readiness, diagnostics, and evidence APIs — safe summary
- React / Vite PWA — selects and renders

### Outgoing

- None declared

## Source verification

- `path` — `src/hooks/useLiteQuery.js`
- `path` — `src/lib/liteSafeSnapshots.js`
- `path` — `src/stores/liteUiStore.js`
- `path` — `src/machines/liteSecurityCheckMachine.js`
- `contract` — `contracts/generated/ui-state-catalog.json`

## Existing documentation

- [ui-state-catalog.md](../../../development/ui-state-catalog.md)
- [fixtures-schemas.md](../../../development/fixtures-schemas.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Request and control flow](../request-control.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
