---
title: "Threat Model"
description: "Architecture-aware STRIDE threat model with promoted posture, controls and modeled attack paths; never live monitoring."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Threat Model

<div class="pl-page-lede"><strong>Architecture-aware threat reasoning backed by promoted evidence.</strong><p>This is not live monitoring. Animated paths represent modeled control/evidence flow, never observed network traffic or active attacks.</p></div>

## Current promoted threat posture

<div class="pl-kpi-grid pl-threat-kpis"><div class="pl-kpi"><span>Trust boundaries</span><strong>9</strong></div><div class="pl-kpi"><span>STRIDE candidates</span><strong>54</strong></div><div class="pl-kpi"><span>Security controls</span><strong>7</strong></div><div class="pl-kpi"><span>Controls observed</span><strong>5</strong></div><div class="pl-kpi"><span>Reviewed attack paths</span><strong>8</strong></div><div class="pl-kpi"><span>Posture evidence gaps</span><strong>4</strong></div><div class="pl-kpi"><span>Human review</span><strong>Required</strong></div></div>

Promoted runtime release: **lite-2026.08.12.2** · authority: **promoted/canonical evidence only**.

## Threat Model Diagram

<div class="pl-threat-toolbar" role="toolbar" aria-label="Threat model diagram controls"><button type="button" data-threat-mode="system" class="md-button md-button--primary">System</button><button type="button" data-threat-mode="controls" class="md-button">Controls</button><button type="button" data-threat-mode="attack-paths" class="md-button">Attack paths</button><button type="button" data-threat-mode="evidence" class="md-button">Evidence posture</button><button type="button" data-threat-motion="toggle" class="md-button">Pause animation</button></div>
<div class="pl-threat-layout"><div class="pl-threat-canvas"><object id="pl-threat-model-svg" data="../../assets/enterprise/threat-model.svg" type="image/svg+xml" aria-label="Interactive Pocket Lab Lite threat model diagram"><img src="../../assets/enterprise/threat-model.svg" alt="Pocket Lab Lite threat model diagram"></object><p class="pl-muted">Blue = modeled allowed/control flow · red dashed = selected modeled attack path · shields = controls. Motion never means live traffic.</p></div><aside class="pl-threat-detail" id="threat-selection" aria-live="polite"><strong>Select a boundary, control or attack path</strong><p>Details remain evidence-bound and source-derived.</p></aside></div>

### Attack-path explorer

<div class="pl-threat-path-grid">
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-01"><span class="pl-card-kicker">AP-01</span><strong>Browser control-plane bypass</strong><small>Spoofing · Tampering · Elevation of Privilege</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-02"><span class="pl-card-kicker">AP-02</span><strong>Browser shell execution</strong><small>Tampering · Elevation of Privilege</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-03"><span class="pl-card-kicker">AP-03</span><strong>Forged managed-device identity</strong><small>Spoofing · Tampering · Elevation of Privilege</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-04"><span class="pl-card-kicker">AP-04</span><strong>Messaging command tampering or replay</strong><small>Tampering · Repudiation · Denial of Service</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-05"><span class="pl-card-kicker">AP-05</span><strong>Supply-chain artifact compromise</strong><small>Tampering · Information Disclosure · Elevation of Privilege</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-06"><span class="pl-card-kicker">AP-06</span><strong>Evidence poisoning</strong><small>Tampering · Repudiation · Information Disclosure</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-07"><span class="pl-card-kicker">AP-07</span><strong>Tailnet/private-network exposure</strong><small>Spoofing · Information Disclosure · Denial of Service</small></button>
<button class="pl-threat-path-card" type="button" data-attack-path-id="AP-08"><span class="pl-card-kicker">AP-08</span><strong>Recovery state tampering</strong><small>Tampering · Repudiation · Denial of Service</small></button>
</div>

## Threat framework

Primary framework: **STRIDE**. Reference mapping: **OWASP Top 10 where applicable**.

| STRIDE | Pocket Lab interpretation |
| --- | --- |
| Spoofing | Impersonating a user, device, service or release identity. |
| Tampering | Unauthorized modification of commands, durable state, releases or evidence. |
| Repudiation | Loss of trustworthy evidence about who or what performed an action. |
| Information Disclosure | Exposure of secrets, private paths, credentials or sensitive operational metadata. |
| Denial of Service | Loss of availability, command delivery or recovery capability. |
| Elevation of Privilege | Bypassing browser, control API, execution-owner or host boundaries. |

## How Pocket Lab applies STRIDE

1. Identify canonical trust boundaries, assets, actors and flows.
2. Generate STRIDE candidates for every trust boundary.
3. Map repository-owned controls to applicable threat categories and boundaries.
4. Attach promoted runtime, security, release and dependency evidence to control posture.
5. Require human review for threat relevance, mitigation adequacy, residual risk, risk acceptance and exceptions.

!!! info "Candidate does not mean exploitable"
    STRIDE candidates identify what deserves review. Exploitability, mitigation adequacy, residual risk and risk acceptance remain human-review decisions.

## Three truth layers

| Layer | Question | Authority |
| --- | --- | --- |
| threat-model | What could go wrong? | canonical architecture and security source |
| control-posture | Which mitigations currently have evidence? | source plus promoted evidence |
| operational-posture | What does the latest promoted evidence report? | promoted sanitized runtime/security/release evidence |

## Security controls

| Control | Where used | Threats mitigated | Effect | Current evidence | If the control fails |
| --- | --- | --- | --- | --- | --- |
| CTRL-BROWSER-NATS | browser, messaging-execution | Spoofing, Tampering, Elevation of Privilege | mitigates | mitigation-source-derived | browser could bypass the control API and attempt unauthorized messaging/command injection |
| CTRL-BROWSER-SHELL | browser | Tampering, Elevation of Privilege | mitigates | mitigation-source-derived | browser-originated input could reach host shell execution and mutate the server host |
| CTRL-API-CONTROL | browser, control-api, messaging-execution | Spoofing, Tampering, Elevation of Privilege | mitigates | control-observed | frontend intent could bypass centralized validation, authorization, reason codes and audit ownership |
| CTRL-EXECUTION-OWNERS | messaging-execution, managed-device, server-host | Tampering, Denial of Service, Elevation of Privilege | mitigates | control-observed | commands or recovery could execute outside worker/agent/supervisor ownership and lose delivery/recovery guarantees |
| CTRL-EVIDENCE-SANITIZE | durable-state, external-release, server-host | Information Disclosure, Repudiation | mitigates | control-observed | secret-bearing or private-path evidence could enter canonical documentation or mislead security posture |
| CTRL-EXPLICIT-PROMOTION | external-release, durable-state, server-host | Tampering, Repudiation, Information Disclosure | mitigates | control-observed | transient/unreviewed capture could be mistaken for canonical release/runtime evidence |
| CTRL-SUPPLY-CHAIN | external-release, application-container | Tampering, Information Disclosure, Elevation of Privilege | mitigates | control-observed | unqualified dependencies or release artifacts could enter runtime without normalized SBOM/scanner evidence |

Controls **mitigate or reduce exposure**. The page does not claim complete threat prevention unless separate evidence explicitly proves it.

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

## Modeled attack paths

| Path | Entry | Target | Boundaries | STRIDE | Controls | Consequences | Review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AP-01 Browser control-plane bypass | browser | nats-jetstream | browser, messaging-execution | Spoofing, Tampering, Elevation of Privilege | CTRL-BROWSER-NATS, CTRL-API-CONTROL | unauthorized command injection, control-plane bypass, loss of expected audit/control ownership | human-review-required |
| AP-02 Browser shell execution | browser | server-host | browser, control-api, server-host | Tampering, Elevation of Privilege | CTRL-BROWSER-SHELL, CTRL-API-CONTROL | host mutation, secret exposure, runtime integrity loss | human-review-required |
| AP-03 Forged managed-device identity | managed-device | node-agent | managed-device, control-api, messaging-execution | Spoofing, Tampering, Elevation of Privilege | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | unauthorized device enrollment, command execution under a forged identity, audit attribution failure | human-review-required |
| AP-04 Messaging command tampering or replay | lite-api | node-agent | control-api, messaging-execution, managed-device | Tampering, Repudiation, Denial of Service | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | incorrect or repeated device commands, loss of command integrity, device availability impact | human-review-required |
| AP-05 Supply-chain artifact compromise | github-release | server-host | external-release, server-host, application-container | Tampering, Information Disclosure, Elevation of Privilege | CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION, CTRL-EVIDENCE-SANITIZE | compromised release execution, dependency or artifact integrity loss, misleading release posture | human-review-required |
| AP-06 Evidence poisoning | scanner-evidence | documentation | external-release, durable-state, server-host | Tampering, Repudiation, Information Disclosure | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION | incorrect security posture, secret or private-path disclosure, loss of evidence trust | human-review-required |
| AP-07 Tailnet/private-network exposure | private-network | lite-api | private-network, control-api, server-host | Spoofing, Information Disclosure, Denial of Service | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | unexpected control-plane reachability, service exposure, availability impact | human-review-required |
| AP-08 Recovery state tampering | sqlite | recovery-state | durable-state, control-api | Tampering, Repudiation, Denial of Service | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL | unsafe restore decisions, loss of recovery evidence integrity, recovery unavailability | human-review-required |

These are **reviewed modeled attack-path scenarios**, not confirmed exploits.

## Architecture integration

The diagram is an overlay on the [canonical Pocket Lab Lite Architecture](../../production/architecture/index.md). Threat visualization nodes reference canonical architecture component ids; security overlays never redefine topology ownership. It currently binds **16** architecture components into the security view.

## Current evidence posture

| Signal | Boundary | State | Observed | Source |
| --- | --- | --- | --- | --- |
| apps operational health | application-container | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| scanner results | application-container | control-observed | normalized-evidence-present | contracts/generated/supply-chain/automation-summary.json |
| release evidence | application-container | control-observed | release-assurance-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
| dependency health | application-container | control-observed | Counter({'healthy': 22, 'unvalidated': 4}) | contracts/generated/documentation-intelligence/dependency-health.json |
| SBOM/vulnerability evidence | application-container | control-observed | normalized canonical evidence present | contracts/generated/supply-chain/vulnerability-correlation.json |
| home operational health | browser | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| home operational health | control-api | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | control-api | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| recovery operational health | durable-state | evidence-stale | degraded | contracts/generated/runtime/domain-operational-health.json |
| security operational health | external-release | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| scanner results | external-release | control-observed | normalized-evidence-present | contracts/generated/supply-chain/automation-summary.json |
| release evidence | external-release | control-observed | release-assurance-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
| dependency health | external-release | control-observed | Counter({'healthy': 22, 'unvalidated': 4}) | contracts/generated/documentation-intelligence/dependency-health.json |
| SBOM/vulnerability evidence | external-release | control-observed | normalized canonical evidence present | contracts/generated/supply-chain/vulnerability-correlation.json |
| devices operational health | managed-device | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| Tailscale readiness | managed-device | control-observed | yes | contracts/generated/runtime/domain-operational-health.json |
| node-agent status | managed-device | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| supervisor status | managed-device | control-partial | unvalidated | contracts/generated/documentation-intelligence/dependency-health.json |
| worker status | managed-device | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| home operational health | messaging-execution | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | messaging-execution | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| node-agent status | messaging-execution | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| supervisor status | messaging-execution | control-partial | unvalidated | contracts/generated/documentation-intelligence/dependency-health.json |
| worker status | messaging-execution | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| dependency health | messaging-execution | control-observed | Counter({'healthy': 22, 'unvalidated': 4}) | contracts/generated/documentation-intelligence/dependency-health.json |
| SBOM/vulnerability evidence | messaging-execution | control-observed | normalized canonical evidence present | contracts/generated/supply-chain/vulnerability-correlation.json |
| home operational health | server-host | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | server-host | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| node-agent status | server-host | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| supervisor status | server-host | control-partial | unvalidated | contracts/generated/documentation-intelligence/dependency-health.json |
| worker status | server-host | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| scanner results | server-host | control-observed | normalized-evidence-present | contracts/generated/supply-chain/automation-summary.json |
| release evidence | server-host | control-observed | release-assurance-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
| devices operational health | private-network | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| Tailscale readiness | private-network | control-observed | yes | contracts/generated/runtime/domain-operational-health.json |

## What this threat model does not do

- Live attack monitoring or packet inspection
- Live NATS polling or traffic visualization
- Running Trivy, Lynis, Semgrep or other scanners from MkDocs
- Scanning the live Android filesystem from documentation generation
- Automatically deciding whether a vulnerability is exploitable
- Automatically accepting residual risk or security exceptions
- Replacing penetration testing, source review or operational monitoring
- Replacing incident detection, release qualification or runtime health checks

## Consequences of not threat modelling

- Trust assumptions become implicit and easier to violate during change.
- Controls can exist without a clear statement of which threats and assets they protect.
- Runtime, release and supply-chain evidence become disconnected from security reasoning.
- Boundary changes can ship without exposing their security-review impact.
- Duplicated, missing or weakly evidenced controls are harder to identify.
- Residual risk and human-review decisions become less auditable.

## Evidence lineage

<div class="pl-lineage"><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="runtime"><strong>Promoted runtime baseline</strong><span><code>contracts/parity/runtime-verification-baseline.json</code></span></a><span aria-hidden="true">→</span><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="health"><strong>Domain operational health</strong><span><code>contracts/generated/runtime/domain-operational-health.json</code></span></a><span aria-hidden="true">→</span><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="dependencies"><strong>Dependency health</strong><span><code>contracts/generated/documentation-intelligence/dependency-health.json</code></span></a><span aria-hidden="true">→</span><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="supply-chain"><strong>Normalized scanner/SBOM evidence</strong><span><code>contracts/generated/supply-chain</code></span></a><span aria-hidden="true">→</span><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="threat-posture"><strong>Threat posture projection</strong><span><code>contracts/generated/documentation-enterprise/threat-posture.json</code></span></a><span aria-hidden="true">→</span><a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="diagram"><strong>Threat model diagram</strong><span><code>docs/generated/assets/enterprise/threat-model.svg</code></span></a></div>

## Threat Dragon

Threat Dragon remains a **derived human-review surface only**. Canonical Pocket Lab source, contracts and promoted evidence remain authoritative; manual review notes must be reconciled back into repository-owned source.

## Human review required

- threat relevance
- mitigation adequacy
- residual risk
- risk acceptance
- exceptions
