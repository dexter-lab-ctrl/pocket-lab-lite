---
title: "Test Failure Triage Guide"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Test Failure Triage Guide
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## Failure attribution

- **backend ≠ API:** inspect manifest/current-state writers, transactions, projection refresh, and allowlist mapping.
- **API ≠ selector:** inspect query key, selector normalizer, enum mapping, and omitted sensitive fields.
- **selector ≠ rendered UI:** inspect conditional labels, component state, stale/offline indicators, and test selectors.
- **mocked passes, live fails:** inspect Caddy origin, API freshness, authentication, runtime projection, and external browser configuration.
- **API/browser match, authority differs:** treat as backend/projection drift; do not patch the UI to hide it.
- **Storybook passes, page fails:** inspect integrated providers, routing, query invalidation, and overlay state.
- **offline conflicts with live:** inspect Dexie snapshot revision and TanStack replacement rules.
- **Schemathesis server error:** reproduce once, inspect sanitized PM2 traceback, and fix the route invariant; never document `500` as an accepted response.
- **Schemathesis timeout:** classify streams separately, inspect cold/warm read-latency evidence, and adjust bounded endpoint behavior rather than disabling the gate.
- **Expected `503`:** verify the response is documented, sanitized, retryable, and carries bounded `Retry-After`; focused read-only schemas must never activate maintenance.
- **Discovery-only finding:** categorize it in the sanitized summary and keep it non-gating until an explicit contract policy is approved.
