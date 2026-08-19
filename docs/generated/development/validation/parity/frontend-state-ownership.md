---
title: "Frontend State Ownership Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Frontend State Ownership Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Layer | Responsibility | Allowed | Prohibited | Status |
| --- | --- | --- | --- | --- |
| tanstack-query | live FastAPI read cache, focused invalidation, stale/reconnect behavior across Lite tabs | sanitized Lite API projections, ETags, query timestamps | durable business authority, secrets, raw SQLite rows, write success before FastAPI confirmation | verified |
| dexie | sanitized read-only fallback snapshots for explicitly eligible Lite GET projections | allowlisted safe Lite summaries, bounded snapshot metadata | write responses, credentials, raw manifests, raw evidence, private paths, identity or invite secrets | verified |
| zustand | harmless cross-tab overlay, navigation, selection, and feedback state | active tab, Manage/details open state, selected UI sections, toast and refresh feedback | authoritative backend status, device or app truth, backup or security completion truth, secrets | verified |
| xstate | visible guided workflow coordination for risky or multi-step Lite actions | requested/queued/running UI stages, accepted command reference, confirmation state | durable operation truth, raw backend payloads, offline write queue | verified |
| component-local | small component-local presentation state only | ephemeral disclosure state, copied-label feedback | backend authority, secrets, durable operation truth | verified |
| storybook-msw | deterministic fixture rendering | synthetic sanitized scenarios | production truth, live credentials | verified |
| playwright | mocked and explicit live browser semantic observation | bounded sanitized semantic observations, failure-only local artifacts | backend authority, raw secrets, phone identity, hostnames, usernames, private addresses | verified |
