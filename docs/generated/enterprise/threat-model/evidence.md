---
title: "Evidence & Provenance"
description: "Promoted/canonical evidence lineage for the saved threat model."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Evidence & provenance

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../evidence-zone/">Promoted evidence → documentation</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>Evidence explains why the saved model says what it says.</strong><p>Promoted runtime, dependency, scanner, release and security-control evidence are provenance inputs. They are not a live feed and do not convert modeled scenarios into observed attacks.</p></div>

## Evidence lineage

| Stage | Canonical/promoted source |
| --- | --- |
| Promoted runtime baseline | contracts/parity/runtime-verification-baseline.json |
| Domain operational health | contracts/generated/runtime/domain-operational-health.json |
| Dependency health | contracts/generated/documentation-intelligence/dependency-health.json |
| Normalized scanner/SBOM evidence | contracts/generated/supply-chain |
| Threat posture projection | contracts/generated/documentation-enterprise/threat-posture.json |
| Threat model diagram | docs/generated/assets/enterprise/threat-model.svg |

## Current promoted evidence posture

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

## Truth boundary

- Canonical architecture owns topology.
- Canonical threat metadata owns threats, controls and review status.
- Promoted sanitized evidence can inform posture.
- MkDocs only renders static projections.
- Human review owns exploitability, residual risk and acceptance.

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

## Human review required

- threat relevance
- mitigation adequacy
- residual risk
- risk acceptance
- exceptions
