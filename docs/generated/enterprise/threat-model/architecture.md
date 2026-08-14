---
title: "Architecture & Trust Zones"
description: "Pocket Lab-specific trust zones over the canonical architecture."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Architecture & trust zones

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>The canonical architecture remains the map.</strong><p>This page explains where trust changes. The security layer annotates architecture component IDs and canonical flows; it does not create a second topology.</p></div>

## Threat Model Diagram

This is a security overlay on the [canonical Pocket Lab Lite Architecture](../../production/architecture/index.md). Architecture continues to own topology and component ownership; this page only adds threat-model context.

<figure class="pl-generated-diagram pl-threat-detail-diagram"><img src="../../../assets/enterprise/threat-model-detail.svg" alt="Detailed Pocket Lab Lite threat architecture overlay" loading="eager" decoding="async"><figcaption>Detailed source-derived architecture overlay. Open the Overview for the museum-style Security Poster.</figcaption></figure>

## Trust zones

| Boundary | Assets | Controls | Review |
| --- | --- | --- | --- |
| Application-container boundary | PhotoPrism runtime/config, app route | CTRL-SUPPLY-CHAIN | human-review-required |
| Browser trust boundary | PWA session/UI state, safe snapshots | CTRL-BROWSER-NATS, CTRL-BROWSER-SHELL, CTRL-API-CONTROL | human-review-required |
| Control API boundary | API request/response contracts, authorization/context | CTRL-API-CONTROL | human-review-required |
| Durable-state boundary | SQLite state, audit evidence, backup metadata | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION | human-review-required |
| External release boundary | dist.zip, SBOM, release manifest, provenance | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-SUPPLY-CHAIN | human-review-required |
| Managed-device boundary | device identity, agent state, bootstrap state | CTRL-EXECUTION-OWNERS | human-review-required |
| Messaging and execution boundary | commands, events, durable consumers | CTRL-BROWSER-NATS, CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | human-review-required |
| Server-host boundary | Termux runtime, PM2 services, local secrets | CTRL-EXECUTION-OWNERS, CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION | human-review-required |
| Private network and Tailnet boundary | Tailnet connectivity, same-origin remote access | — | human-review-required |

## Boundary pages

- [Application-container boundary](application-container.md)
- [Browser trust boundary](browser.md)
- [Control API boundary](control-api.md)
- [Durable-state boundary](durable-state.md)
- [External release boundary](external-release.md)
- [Managed-device boundary](managed-device.md)
- [Messaging and execution boundary](messaging-execution.md)
- [Server-host boundary](server-host.md)
- [Private network and Tailnet boundary](private-network.md)

## Architecture ownership

Threat visualization nodes reference canonical architecture component ids; security overlays never redefine topology ownership.
