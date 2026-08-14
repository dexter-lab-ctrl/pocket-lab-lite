---
title: "Security Controls"
description: "Source-derived control catalog with coverage and failure consequences."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Security controls

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>Controls are architectural guardrails with evidence, not posture scores.</strong><p>Each control shows where it is used, what it mitigates and what can happen if it fails. Prevention is not claimed unless separate evidence supports it.</p></div>

<div class="pl-threat-control-grid"><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-BROWSER-NATS#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">mitigation-source-derived</span><strong>CTRL-BROWSER-NATS</strong><p>Frontend does not connect directly to NATS.</p><small>Used at: browser, messaging-execution</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-BROWSER-SHELL#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">mitigation-source-derived</span><strong>CTRL-BROWSER-SHELL</strong><p>Frontend does not execute shell commands.</p><small>Used at: browser</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-API-CONTROL#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">control-observed</span><strong>CTRL-API-CONTROL</strong><p>FastAPI remains the frontend-facing control API.</p><small>Used at: browser, control-api, messaging-execution</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-EXECUTION-OWNERS#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">control-observed</span><strong>CTRL-EXECUTION-OWNERS</strong><p>Workers, agents and supervisors own execution and recovery.</p><small>Used at: messaging-execution, managed-device, server-host</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-EVIDENCE-SANITIZE#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">control-observed</span><strong>CTRL-EVIDENCE-SANITIZE</strong><p>Runtime/scanner evidence is sanitized before canonical documentation ingestion.</p><small>Used at: durable-state, external-release, server-host</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-EXPLICIT-PROMOTION#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">control-observed</span><strong>CTRL-EXPLICIT-PROMOTION</strong><p>Runtime and scanner evidence promotion is explicit; MkDocs does not capture or promote.</p><small>Used at: external-release, durable-state, server-host</small></div></a><a class="pl-threat-control-card pl-intent-link" href="../catalog/?atlas-control=CTRL-SUPPLY-CHAIN#security-atlas"><span class="pl-threat-shield" aria-hidden="true">◇</span><div><span class="pl-card-kicker">control-observed</span><strong>CTRL-SUPPLY-CHAIN</strong><p>Pinned WSL2/CI tooling produces sanitized normalized SBOM/security evidence before docs consumption.</p><small>Used at: external-release, application-container</small></div></a></div>

## Control evidence

| Control | Where used | Effect | Current evidence | If it fails |
| --- | --- | --- | --- | --- |
| CTRL-BROWSER-NATS | browser, messaging-execution | mitigates | mitigation-source-derived | browser could bypass the control API and attempt unauthorized messaging/command injection |
| CTRL-BROWSER-SHELL | browser | mitigates | mitigation-source-derived | browser-originated input could reach host shell execution and mutate the server host |
| CTRL-API-CONTROL | browser, control-api, messaging-execution | mitigates | control-observed | frontend intent could bypass centralized validation, authorization, reason codes and audit ownership |
| CTRL-EXECUTION-OWNERS | messaging-execution, managed-device, server-host | mitigates | control-observed | commands or recovery could execute outside worker/agent/supervisor ownership and lose delivery/recovery guarantees |
| CTRL-EVIDENCE-SANITIZE | durable-state, external-release, server-host | mitigates | control-observed | secret-bearing or private-path evidence could enter canonical documentation or mislead security posture |
| CTRL-EXPLICIT-PROMOTION | external-release, durable-state, server-host | mitigates | control-observed | transient/unreviewed capture could be mistaken for canonical release/runtime evidence |
| CTRL-SUPPLY-CHAIN | external-release, application-container | mitigates | control-observed | unqualified dependencies or release artifacts could enter runtime without normalized SBOM/scanner evidence |

## Where controls are used

| Control | application-container | browser | control-api | durable-state | external-release | managed-device | messaging-execution | server-host | private-network |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CTRL-BROWSER-NATS | — | ✓ | — | — | — | — | ✓ | — | — |
| CTRL-BROWSER-SHELL | — | ✓ | — | — | — | — | — | — | — |
| CTRL-API-CONTROL | — | ✓ | ✓ | — | — | — | ✓ | — | — |
| CTRL-EXECUTION-OWNERS | — | — | — | — | — | ✓ | ✓ | ✓ | — |
| CTRL-EVIDENCE-SANITIZE | — | — | — | ✓ | ✓ | — | — | ✓ | — |
| CTRL-EXPLICIT-PROMOTION | — | — | — | ✓ | ✓ | — | — | ✓ | — |
| CTRL-SUPPLY-CHAIN | ✓ | — | — | — | ✓ | — | — | — | — |
