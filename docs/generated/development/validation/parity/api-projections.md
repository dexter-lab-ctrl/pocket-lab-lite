---
title: "API Projection Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# API Projection Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Method | Endpoint | Identity | Pagination | Freshness | Degraded | Offline | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET | /api/lite/recovery/summary | recovery-summary-r3-v1 | none | summary ETag/revision and last-good semantics | safe saved-state summary | safe-summary | verified |
| GET | /api/lite/recovery/details | recovery-screen-view | history excluded from first paint | detail read on Manage intent | last-good safe details when available | safe-details | verified |
| GET | /api/lite/recovery/operations?limit={limit}&cursor={cursor} | recovery-operation-history | cursor, limit 1..50 | prepared projection revision | invalid cursor returns sanitized 400 | first-page-only | verified |
| GET | /api/lite/recovery/backups?limit={limit}&cursor={cursor} | recovery-history-snapshot-v2 | opaque cursor, limit 1..50 | manifest ordering | invalid cursor returns sanitized 400 | first-page-only | verified |
| GET | /api/lite/recovery/receipts/{backup_id} | backup-receipt | none | immutable per backup update | 404 sanitized | not-cached-by-default | verified |
| GET | /api/lite/recovery/database | database-protection | separate backup list | prepared database recovery state | safe summary | safe-summary | verified |
| GET | /api/lite/fleet | devices-screen-view | none | heartbeat and projection revision | saved state marked stale | safe-summary | partial |
| GET | /api/lite/catalog | catalog-view | none | catalog revision | saved state | safe-summary | partial |
| GET | /api/lite/security/summary | security-summary | none | ETag/revision | saved summary | safe-summary | partial |
