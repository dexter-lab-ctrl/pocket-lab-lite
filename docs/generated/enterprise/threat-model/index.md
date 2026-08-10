---
title: "Threat Model"
description: "Current promoted threat posture and canonical STRIDE model; never live monitoring."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Threat Model

## Current promoted threat posture

This is **not live monitoring**. Posture is derived from promoted runtime evidence, Security operational health, Tailscale readiness, NATS health, node-agent/supervisor status, normalized scanner evidence, release evidence, dependency health, SBOM/vulnerability evidence and security-control verification.

| Signal | Boundary | State | Observed | Source |
| --- | --- | --- | --- | --- |
| apps operational health | application-container | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| scanner results | application-container | control-observed | normalized-evidence-present | contracts/generated/supply-chain/automation-summary.json |
| release evidence | application-container | control-observed | release-evidence-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
| dependency health | application-container | control-observed | Counter({'healthy': 22, 'unvalidated': 4}) | contracts/generated/documentation-intelligence/dependency-health.json |
| SBOM/vulnerability evidence | application-container | control-observed | normalized canonical evidence present | contracts/generated/supply-chain/vulnerability-correlation.json |
| home operational health | browser | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| home operational health | control-api | control-observed | degraded | contracts/generated/runtime/domain-operational-health.json |
| NATS/JetStream health | control-api | control-observed | healthy | contracts/generated/documentation-intelligence/dependency-health.json |
| recovery operational health | durable-state | evidence-stale | degraded | contracts/generated/runtime/domain-operational-health.json |
| security operational health | external-release | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| scanner results | external-release | control-observed | normalized-evidence-present | contracts/generated/supply-chain/automation-summary.json |
| release evidence | external-release | control-observed | release-evidence-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
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
| release evidence | server-host | control-observed | release-evidence-model-operational | contracts/generated/documentation-enterprise/release-evidence.json |
| devices operational health | private-network | control-observed | healthy | contracts/generated/runtime/domain-operational-health.json |
| Tailscale readiness | private-network | control-observed | yes | contracts/generated/runtime/domain-operational-health.json |

## Canonical threat model

All nine requested trust boundaries receive STRIDE candidate generation. Residual risk and acceptance remain human review. Threat Dragon is a derived review surface only.
