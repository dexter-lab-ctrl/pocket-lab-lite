---
title: "Operational health encyclopedia"
description: "Operational health kept distinct from semantic parity."
generated: true
audience: knowledgebase
confidence: release-promoted
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Operational health encyclopedia

| Domain | Implementation | Runtime | Operational health | Reason | Semantic parity | Evidence | Freshness | Readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apps | implemented | observed | unvalidated | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |
| Devices | implemented | observed | unvalidated | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |
| Home | implemented | observed | healthy | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |
| Identity | partial | observed | unvalidated | — | partial | release-promoted | promoted-observation | partial |
| Backup & Restore | implemented | observed | degraded | projection_too_old | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |
| Rules | partial | observed | unvalidated | — | partial | release-promoted | promoted-observation | partial |
| Security | implemented | observed | unvalidated | — | verified-with-mapped-presentation | release-promoted | promoted-observation | ready-with-guardrails |

Operational degradation is not converted into semantic mismatch.
