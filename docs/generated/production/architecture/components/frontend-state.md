---
title: "Frontend state ownership"
description: "Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Frontend state ownership

Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth.

![Frontend state ownership mini architecture](../../../../assets/diagrams/production/components/frontend-state.light.svg#only-light)
![Frontend state ownership mini architecture](../../../../assets/diagrams/production/components/frontend-state.dark.svg#only-dark)


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
