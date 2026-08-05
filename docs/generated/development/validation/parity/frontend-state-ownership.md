---
title: "Frontend State Ownership Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Frontend State Ownership Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Layer | Responsibility | Allowed | Prohibited | Status |
| --- | --- | --- | --- | --- |
| tanstack-query | live FastAPI read cache, query invalidation, stale/reconnect behavior | sanitized API projections, ETags, query timestamps | durable business authority, secrets, raw SQLite rows, write success before FastAPI confirmation | verified |
| dexie | sanitized read-only fallback snapshots | recovery summary, first page recovery history, snapshot metadata | write responses, credentials, raw manifests, raw evidence, private paths | verified |
| zustand | transient overlay, Manage, selection and feedback state | recovery Manage open state, selected recovery section, confirmation sheet state | authoritative recovery status, backup truth, restore completion truth, secrets | verified |
| xstate | visible recovery workflow coordination | requested/queued/running UI stages, accepted command reference, confirmation state | durable operation truth, raw backend payloads, offline write queue | verified |
| component-local | ephemeral copy feedback and local presentation | copied evidence label | backend authority | verified |
| storybook-msw | deterministic fixture rendering | synthetic sanitized scenarios | production truth, live credentials | verified |
| playwright | mocked and live browser observation | sanitized traces, failure screenshots, JUnit/JSON results | backend authority, raw secrets, phone identity | verified |
