---
title: "Known issues"
description: "Current limitations without hiding accepted constraints."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Known issues

| Area | Status | What it means |
| --- | --- | --- |
| apps | accepted | PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract. |
| apps | open | Application-owned media indexing is not a Pocket Lab parity authority. |
| devices | accepted | Heartbeat freshness can move during capture; comparison records the observed revision. |
| devices | open | Per-device profile fields remain partial when the agent has not published them. |
| home | accepted | CPU, memory, and storage presentation may be rounded or unit-formatted. |
| home | open | Live runtime semantic evidence remains explicit and release-bound. |
| identity | accepted | Credential values are never observable parity fields. |
| identity | accepted | Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented. |
| identity | open | The current tab is direct-rendered and has no dedicated selector layer. |
| identity | open | Identity guard and protected server-host projections are not fully implemented. |
| recovery | accepted | Status labels intentionally use Lite-friendly wording instead of raw backend enums. |
| recovery | accepted | App restore apply remains explicitly unsupported where the repository reports it unavailable. |
| recovery | accepted | Historical restore previews are evidence only and never authorize a new restore. |
| recovery | open | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. |
| rules | accepted | The current product contract is a protection-mode policy surface, not a general arbitrary rule engine. |
| rules | open | Per-rule identity and execution history are planned, not present in the current API. |
| security | accepted | Raw scanner output and sensitive paths are intentionally excluded. |
| security | open | A missing scanner is runtime-unavailable, not semantic drift. |
