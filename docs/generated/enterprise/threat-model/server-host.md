---
title: "Server-host boundary"
description: "Generated STRIDE threat model for Server-host boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Server-host boundary

## Boundary
Server-host boundary

## Assets
- Termux runtime
- PM2 services
- local secrets

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
| Spoofing | Source-derived candidate Spoofing threat affecting the Server-host boundary. | OWASP Top 10 A07 Identification and Authentication Failures | — |
| Tampering | Source-derived candidate Tampering threat affecting the Server-host boundary. | OWASP Top 10 A08 Software and Data Integrity Failures | CTRL-EXECUTION-OWNERS, CTRL-EXPLICIT-PROMOTION |
| Repudiation | Source-derived candidate Repudiation threat affecting the Server-host boundary. | OWASP Top 10 A09 Security Logging and Monitoring Failures | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION |
| Information Disclosure | Source-derived candidate Information Disclosure threat affecting the Server-host boundary. | OWASP Top 10 A01 Broken Access Control, OWASP Top 10 A02 Cryptographic Failures | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION |
| Denial of Service | Source-derived candidate Denial of Service threat affecting the Server-host boundary. | No direct OWASP Top 10 mapping; availability/resilience control review | CTRL-EXECUTION-OWNERS |
| Elevation of Privilege | Source-derived candidate Elevation of Privilege threat affecting the Server-host boundary. | OWASP Top 10 A01 Broken Access Control | CTRL-EXECUTION-OWNERS |

## Controls
- `CTRL-EXECUTION-OWNERS`
- `CTRL-EVIDENCE-SANITIZE`
- `CTRL-EXPLICIT-PROMOTION`

## Runtime evidence
| Signal | State | Source |
| --- | --- | --- |
| home operational health | control-observed | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |
| node-agent status | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |
| supervisor status | control-partial | contracts/generated/documentation-intelligence/dependency-health.json |
| worker status | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |
| scanner results | control-observed | contracts/generated/supply-chain/automation-summary.json |
| release evidence | control-observed | contracts/generated/documentation-enterprise/release-evidence.json |

## Residual risk
human review required

## Review status
human-review-required
