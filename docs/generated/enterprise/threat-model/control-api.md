---
title: "Control API boundary"
description: "Generated STRIDE threat model for Control API boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Control API boundary

## Boundary
Control API boundary

## Assets
- API request/response contracts
- authorization/context

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
| Spoofing | Source-derived candidate Spoofing threat affecting the Control API boundary. | OWASP Top 10 A07 Identification and Authentication Failures | CTRL-API-CONTROL |
| Tampering | Source-derived candidate Tampering threat affecting the Control API boundary. | OWASP Top 10 A08 Software and Data Integrity Failures | CTRL-API-CONTROL |
| Repudiation | Source-derived candidate Repudiation threat affecting the Control API boundary. | OWASP Top 10 A09 Security Logging and Monitoring Failures | — |
| Information Disclosure | Source-derived candidate Information Disclosure threat affecting the Control API boundary. | OWASP Top 10 A01 Broken Access Control, OWASP Top 10 A02 Cryptographic Failures | — |
| Denial of Service | Source-derived candidate Denial of Service threat affecting the Control API boundary. | No direct OWASP Top 10 mapping; availability/resilience control review | — |
| Elevation of Privilege | Source-derived candidate Elevation of Privilege threat affecting the Control API boundary. | OWASP Top 10 A01 Broken Access Control | CTRL-API-CONTROL |

## Controls
- `CTRL-API-CONTROL`

## Runtime evidence
| Signal | State | Source |
| --- | --- | --- |
| home operational health | control-observed | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |

## Residual risk
human review required

## Review status
human-review-required
