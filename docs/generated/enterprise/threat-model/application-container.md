---
title: "Application-container boundary"
description: "Generated STRIDE threat model for Application-container boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Application-container boundary

## Boundary
Application-container boundary

## Assets
- PhotoPrism runtime/config
- app route

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
| Spoofing | Source-derived candidate Spoofing threat affecting the Application-container boundary. | OWASP Top 10 A07 Identification and Authentication Failures | — |
| Tampering | Source-derived candidate Tampering threat affecting the Application-container boundary. | OWASP Top 10 A08 Software and Data Integrity Failures | CTRL-SUPPLY-CHAIN |
| Repudiation | Source-derived candidate Repudiation threat affecting the Application-container boundary. | OWASP Top 10 A09 Security Logging and Monitoring Failures | — |
| Information Disclosure | Source-derived candidate Information Disclosure threat affecting the Application-container boundary. | OWASP Top 10 A01 Broken Access Control, OWASP Top 10 A02 Cryptographic Failures | CTRL-SUPPLY-CHAIN |
| Denial of Service | Source-derived candidate Denial of Service threat affecting the Application-container boundary. | No direct OWASP Top 10 mapping; availability/resilience control review | — |
| Elevation of Privilege | Source-derived candidate Elevation of Privilege threat affecting the Application-container boundary. | OWASP Top 10 A01 Broken Access Control | CTRL-SUPPLY-CHAIN |

## Controls
- `CTRL-SUPPLY-CHAIN`

## Runtime evidence
| Signal | State | Source |
| --- | --- | --- |
| apps operational health | control-observed | contracts/generated/runtime/domain-operational-health.json |
| scanner results | control-observed | contracts/generated/supply-chain/automation-summary.json |
| release evidence | control-observed | contracts/generated/documentation-enterprise/release-evidence.json |
| dependency health | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |
| SBOM/vulnerability evidence | control-observed | contracts/generated/supply-chain/vulnerability-correlation.json |

## Residual risk
human review required

## Review status
human-review-required
