---
title: "Projection parity readiness"
generated: true
audience: production
status: ready-with-accepted-limitations
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Projection parity readiness

Pocket Lab Lite has deterministic repository-derived parity contracts for Home, Apps, Devices, Security, Identity, Rules, and Backup & Restore. Runtime capture remains explicit, read-only, sanitized, and independent of ordinary documentation generation.

| Domain | Repository | Live API | Live UI | Live Termux | Semantic parity |
| --- | --- | --- | --- | --- | --- |
| Home | verified | observed | observed | observed | verified-with-mapped-presentation |
| Apps | verified | observed | observed | observed | verified-with-mapped-presentation |
| Devices | verified | observed | observed | observed | verified-with-mapped-presentation |
| Security | verified | observed | observed | observed | verified-with-mapped-presentation |
| Identity | partial | observed | observed | observed | partial |
| Rules | partial | observed | observed | observed | partial |
| Backup & Restore | ready-with-accepted-limitations | observed | observed | observed | partial |

A promoted drift result is a review signal, not a documentation failure and not permission to change application behavior automatically.
