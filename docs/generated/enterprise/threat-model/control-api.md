---
title: "Control API boundary"
description: "Generated STRIDE threat model for Control API boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Control API boundary

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../evidence-zone/">Promoted evidence → documentation</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede pl-threat-boundary-lede"><strong>Control API boundary in the saved security model.</strong><p>This page keeps assets, actors, flows, threats, controls and evidence together so the boundary can be reviewed without leaving the canonical Threat Model context.</p></div>

<div class="pl-threat-boundary-summary" aria-label="Threat Model detail summary"><article><span>Type</span><strong>Canonical trust boundary</strong></article><article><span>Assets</span><strong>2</strong></article><article><span>Controls</span><strong>1</strong></article><article><span>Review</span><strong>human-review-required</strong></article></div>

## Boundary

<div class="pl-threat-boundary-callout"><strong>Control API boundary</strong><span>Canonical threat boundary · source-derived · not live monitoring</span></div>

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

## Runtime evidence & provenance

| Signal | State | Source |
| --- | --- | --- |
| home operational health | control-observed | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | control-observed | contracts/generated/documentation-intelligence/dependency-health.json |

## Residual risk

human review required

## Review status

human-review-required
