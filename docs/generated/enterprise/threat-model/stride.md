---
title: "STRIDE Lens"
description: "STRIDE categories and boundary coverage without exploit claims."
generated: true
audience: production
page_type: reference
confidence: generated
---

# STRIDE exploration lens

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>STRIDE is a review lens, not a vulnerability verdict.</strong><p>Categories are applied only where the canonical model says they apply. A candidate does not mean an exploit is confirmed.</p></div>

## Threat framework

Primary framework: **STRIDE**. Reference mapping: **OWASP Top 10 where applicable**.

## STRIDE definitions

| STRIDE | Pocket Lab interpretation |
| --- | --- |
| Spoofing | Impersonating a user, device, service or release identity. |
| Tampering | Unauthorized modification of commands, durable state, releases or evidence. |
| Repudiation | Loss of trustworthy evidence about who or what performed an action. |
| Information Disclosure | Exposure of secrets, private paths, credentials or sensitive operational metadata. |
| Denial of Service | Loss of availability, command delivery or recovery capability. |
| Elevation of Privilege | Bypassing browser, control API, execution-owner or host boundaries. |

## Boundary coverage

| Boundary | Spoofing | Tampering | Repudiation | Disclosure | Denial | Elevation |
| --- | --- | --- | --- | --- | --- | --- |
| Application-container boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Browser trust boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Control API boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Durable-state boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| External release boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Managed-device boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Messaging and execution boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Server-host boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Private network and Tailnet boundary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## How Pocket Lab applies STRIDE

1. Identify canonical trust boundaries, assets, actors and flows.
2. Generate STRIDE candidates for every trust boundary.
3. Map repository-owned controls to applicable threat categories and boundaries.
4. Attach promoted runtime, security, release and dependency evidence to control posture.
5. Require human review for threat relevance, mitigation adequacy, residual risk, risk acceptance and exceptions.

## Three truth layers

| Layer | Question | Authority |
| --- | --- | --- |
| threat-model | What could go wrong? | canonical architecture and security source |
| control-posture | Which mitigations currently have evidence? | source plus promoted evidence |
| operational-posture | What does the latest promoted evidence report? | promoted sanitized runtime/security/release evidence |

!!! info "Human review remains authoritative"
    Exploitability, mitigation adequacy, residual risk and risk acceptance are not inferred by the poster.
