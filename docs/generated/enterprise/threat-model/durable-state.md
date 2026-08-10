---
title: "Durable-state boundary"
description: "Generated STRIDE threat model for Durable-state boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Durable-state boundary

## Boundary
Durable-state boundary

## Assets
- SQLite state
- audit evidence
- backup metadata

## Actors
- operator
- Pocket Lab service
- joined device

## Entry points
- repository-defined API/event/runtime/release flow

## Data flows
- UI → Caddy → FastAPI → NATS/JetStream → worker/agent/supervisor → evidence → FastAPI → UI

## Allowed flows
- canonical control-plane paths only

## Forbidden flows
- frontend → NATS
- frontend → shell
- documentation generator → live runtime
- raw scanner output → MkDocs

## Threats
| STRIDE | Scenario | OWASP mapping | Controls |
| --- | --- | --- | --- |
| Spoofing | Source-derived candidate Spoofing threat affecting the Durable-state boundary. | OWASP Top 10 A07 Identification and Authentication Failures | — |
| Tampering | Source-derived candidate Tampering threat affecting the Durable-state boundary. | OWASP Top 10 A08 Software and Data Integrity Failures | CTRL-EXPLICIT-PROMOTION |
| Repudiation | Source-derived candidate Repudiation threat affecting the Durable-state boundary. | OWASP Top 10 A09 Security Logging and Monitoring Failures | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION |
| Information Disclosure | Source-derived candidate Information Disclosure threat affecting the Durable-state boundary. | OWASP Top 10 A01 Broken Access Control, OWASP Top 10 A02 Cryptographic Failures | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION |
| Denial of Service | Source-derived candidate Denial of Service threat affecting the Durable-state boundary. | No direct OWASP Top 10 mapping; availability/resilience control review | — |
| Elevation of Privilege | Source-derived candidate Elevation of Privilege threat affecting the Durable-state boundary. | OWASP Top 10 A01 Broken Access Control | — |

## Controls
- `CTRL-EVIDENCE-SANITIZE`
- `CTRL-EXPLICIT-PROMOTION`

## Runtime evidence
| Signal | State | Source |
| --- | --- | --- |
| recovery operational health | evidence-stale | contracts/generated/runtime/domain-operational-health.json |

## Residual risk
human review required

## Review status
human-review-required
