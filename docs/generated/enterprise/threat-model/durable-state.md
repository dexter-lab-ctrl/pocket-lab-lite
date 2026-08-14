---
title: "Durable-state boundary"
description: "Generated STRIDE threat model for Durable-state boundary."
generated: true
audience: production
page_type: threat-model
confidence: generated
---

# Durable-state boundary

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../evidence-zone/">Promoted evidence → documentation</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede pl-threat-boundary-lede"><strong>Durable-state boundary in the saved security model.</strong><p>This page keeps assets, actors, flows, threats, controls and evidence together so the boundary can be reviewed without leaving the canonical Threat Model context.</p></div>

<div class="pl-threat-boundary-summary" aria-label="Threat Model detail summary"><article><span>Type</span><strong>Canonical trust boundary</strong></article><article><span>Assets</span><strong>3</strong></article><article><span>Controls</span><strong>2</strong></article><article><span>Review</span><strong>human-review-required</strong></article></div>

## Boundary

<div class="pl-threat-boundary-callout"><strong>Durable-state boundary</strong><span>Canonical threat boundary · source-derived · not live monitoring</span></div>

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

## Runtime evidence & provenance

| Signal | State | Source |
| --- | --- | --- |
| recovery operational health | evidence-stale | contracts/generated/runtime/domain-operational-health.json |

## Residual risk

human review required

## Review status

human-review-required
