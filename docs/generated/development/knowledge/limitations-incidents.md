---
title: "Known issues and incidents"
description: "Canonical limitation lifecycle plus incident model without fabricated history."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Known issues / limitations lifecycle

| ID | Domain | Status | Description | Confidence |
| --- | --- | --- | --- | --- |
| limitation:apps:accepted-1 | apps | accepted | PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract. | contract-derived |
| limitation:apps:gap-1 | apps | open | Application-owned media indexing is not a Pocket Lab parity authority. | contract-derived |
| limitation:devices:accepted-1 | devices | accepted | Heartbeat freshness can move during capture; comparison records the observed revision. | contract-derived |
| limitation:devices:gap-1 | devices | open | Per-device profile fields remain partial when the agent has not published them. | contract-derived |
| limitation:home:accepted-1 | home | accepted | CPU, memory, and storage presentation may be rounded or unit-formatted. | contract-derived |
| limitation:home:gap-1 | home | open | Live runtime semantic evidence remains explicit and release-bound. | contract-derived |
| limitation:identity:accepted-1 | identity | accepted | Credential values are never observable parity fields. | contract-derived |
| limitation:identity:accepted-2 | identity | accepted | Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented. | contract-derived |
| limitation:identity:gap-1 | identity | open | The current tab is direct-rendered and has no dedicated selector layer. | contract-derived |
| limitation:identity:gap-2 | identity | open | Identity guard and protected server-host projections are not fully implemented. | contract-derived |
| limitation:recovery:accepted-1 | recovery | accepted | Status labels intentionally use Lite-friendly wording instead of raw backend enums. | contract-derived |
| limitation:recovery:accepted-2 | recovery | accepted | App restore apply remains explicitly unsupported where the repository reports it unavailable. | contract-derived |
| limitation:recovery:accepted-3 | recovery | accepted | Historical restore previews are evidence only and never authorize a new restore. | contract-derived |
| limitation:recovery:gap-1 | recovery | open | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. | contract-derived |
| limitation:rules:accepted-1 | rules | accepted | The current product contract is a protection-mode policy surface, not a general arbitrary rule engine. | contract-derived |
| limitation:rules:gap-1 | rules | open | Per-rule identity and execution history are planned, not present in the current API. | contract-derived |
| limitation:security:accepted-1 | security | accepted | Raw scanner output and sensitive paths are intentionally excluded. | contract-derived |
| limitation:security:gap-1 | security | open | A missing scanner is runtime-unavailable, not semantic drift. | contract-derived |

# Incident knowledgebase

No structured historical incident records exist in the repository, so none are fabricated. The canonical metadata defines the incident template for future records.
