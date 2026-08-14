---
title: "Operational health encyclopedia"
description: "Operational health kept distinct from semantic parity."
generated: true
audience: knowledgebase
confidence: release-promoted
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Operational health encyclopedia

| Domain | Implementation | Runtime | Operational health | Reason | Semantic parity | Evidence | Freshness | Readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apps | implemented | observed | healthy | — | drift-detected | release-promoted | promoted-observation | ready-with-guardrails |
| Devices | implemented | observed | healthy | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |
| Home | implemented | observed | degraded | read_degraded | verified-with-mapped-presentation | release-promoted | promoted-observation | degraded |
| Identity | partial | observed | unvalidated | — | partial | release-promoted | promoted-observation | partial |
| Backup & Restore | implemented | observed | degraded | projection_too_old | drift-detected | release-promoted | stale | degraded |
| Rules | partial | observed | unvalidated | — | partial | release-promoted | promoted-observation | partial |
| Security | implemented | observed | healthy | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |

Operational degradation is not converted into semantic mismatch.
