---
title: "Projection parity readiness"
description: "Current repository-derived and promoted-runtime evidence for Pocket Lab Lite backend-to-frontend projection parity."
generated: true
audience: production
status: needs-review
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source-derived</span><span class="pl-status pl-status--needs-review">Needs Review</span></div>

# Projection parity readiness

Pocket Lab Lite has deterministic repository-derived parity contracts for Home, Apps, Devices, Security, Identity, Rules, and Backup & Restore. Runtime capture remains explicit, read-only, sanitized, and independent of ordinary documentation generation.

| Domain | Repository | Live API | Live UI | Live Termux | Semantic parity |
| --- | --- | --- | --- | --- | --- |
| Home | verified | observed | observed | observed | verified-with-mapped-presentation |
| Apps | needs-review | observed | observed | observed | drift-detected |
| Devices | verified | observed | observed | observed | verified-with-mapped-presentation |
| Security | verified | observed | observed | observed | verified-with-mapped-presentation |
| Identity | partial | observed | observed | observed | partial |
| Rules | partial | observed | observed | observed | partial |
| Backup & Restore | needs-review | observed | observed | observed | drift-detected |

A promoted drift result is a review signal, not a documentation failure and not permission to change application behavior automatically.
