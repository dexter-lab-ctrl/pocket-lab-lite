---
title: "Reliability Objectives"
description: "SLO-style engineering objectives from promoted evidence; not live monitoring."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Reliability Objectives — not live monitoring

| Objective | Target | Latest promoted observation | Status | Evidence |
| --- | --- | --- | --- | --- |
| heartbeat freshness | Devices canonical freshness threshold | promoted-observation | pass | contracts/generated/runtime/domain-operational-health.json |
| API availability expectations | FastAPI/Caddy dependencies observed healthy for normal read/control paths | degraded | degraded | promoted Home operational health |
| command delivery latency | bounded command-delivery latency is measured only when promoted command timing evidence exists; readiness alone is not treated as latency | unobserved | unknown | promoted Devices operational health / command evidence when present |
| supervisor recovery time | recovery duration is reported only from promoted supervisor recovery timing evidence | unobserved | unknown | promoted Devices operational health / supervisor recovery evidence when present |
| runtime evidence freshness | promoted evidence freshness remains explicit per-domain | 2026-08-07T18:04:28Z | degraded | promoted operational-health contract |
| documentation determinism | zero drift on consecutive generator checks | verified | pass | parity/docs.json |
