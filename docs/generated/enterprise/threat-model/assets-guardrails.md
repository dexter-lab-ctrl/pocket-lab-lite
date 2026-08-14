---
title: "Assets & Guardrails"
description: "Protected assets and canonical forbidden architecture paths."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Assets & architectural guardrails

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>What Pocket Lab protects — and the paths architecture forbids.</strong><p>Assets come directly from canonical boundary metadata. Forbidden paths are rendered only when the exact canonical statement exists.</p></div>

## Protected assets

| Boundary | Assets | Data classification |
| --- | --- | --- |
| Application-container boundary | PhotoPrism runtime/config, app route | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Browser trust boundary | PWA session/UI state, safe snapshots | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Control API boundary | API request/response contracts, authorization/context | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Durable-state boundary | SQLite state, audit evidence, backup metadata | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| External release boundary | dist.zip, SBOM, release manifest, provenance | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Managed-device boundary | device identity, agent state, bootstrap state | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Messaging and execution boundary | commands, events, durable consumers | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Server-host boundary | Termux runtime, PM2 services, local secrets | sanitized operational metadata, restricted identity/configuration metadata where applicable |
| Private network and Tailnet boundary | Tailnet connectivity, same-origin remote access | sanitized operational metadata, restricted identity/configuration metadata where applicable |

## Forbidden paths

| Canonical guardrail | Declared at boundaries |
| --- | --- |
| documentation generator → live runtime | application-container, browser, control-api, durable-state, external-release, managed-device, messaging-execution, private-network, server-host |
| frontend → NATS | application-container, browser, control-api, durable-state, external-release, managed-device, messaging-execution, private-network, server-host |
| frontend → shell | application-container, browser, control-api, durable-state, external-release, managed-device, messaging-execution, private-network, server-host |
| raw scanner output → MkDocs | application-container, browser, control-api, durable-state, external-release, managed-device, messaging-execution, private-network, server-host |

## Poster guardrail overlay

The Overview **Show guardrails** control reveals only forbidden paths that have an explicit visual mapping and an exact canonical forbidden-flow statement. No missing path is inferred.
