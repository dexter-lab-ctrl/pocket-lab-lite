---
title: "Performance and Edge Budget Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Performance and Edge Budget Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Profile | VUs | Duration | Endpoints | Thresholds | Status |
| --- | --- | --- | --- | --- | --- |
| wsl | 3 | 20s | /api/lite/recovery/summary, /api/lite/fleet | http_req_duration=p(95)<750, http_req_failed=rate<0.01 | ready |
| edge | 1 | 15s | /api/lite/recovery/summary, /api/lite/fleet | http_req_duration=p(95)<1500, http_req_failed=rate<0.02 | ready-with-accepted-limitations |

The edge profile is read-only, explicitly enabled, battery/memory/CPU guarded, and intentionally not a stress test. `lite:api:read-latency` captures two to five bounded cold/warm samples for Recovery and Security reads, records median/p95/max timing without host disclosure, and rejects non-loopback targets. Runtime thresholds are evidence-driven rather than guessed.
