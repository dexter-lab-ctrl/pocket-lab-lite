---
title: "NATS / JetStream"
description: "Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# NATS / JetStream

Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend.

## Why it exists

Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:nats-jetstream` |
| Owner | Messaging backbone |
| Execution owner | pocket-nats |
| Data owner | JetStream storage |
| Recovery owner | Startup scripts / PM2 |
| Runtime owner | PM2 |
| Runtime process | pocket-nats |
| Runtime platform | Server host |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend.

## Inputs

- Validated commands
- events

## Outputs

- Durable command delivery
- event fan-out

## Health signals

- NATS monitor
- JetStream status

## Failure modes

- listener unavailable
- consumer stalled

## Recovery behavior

- reconnect
- durable consumer re-enrollment

## Evidence

- consumer health

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `FastAPI owns the browser-facing control API`
- depends_on: `Device command executor`
- depends_on: `Enrollment and device lifecycle state`
- depends_on: `Worker process`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- recovers_with: `Device offline or reconnecting`
- recovers_with: `NATS or JetStream unavailable`
- recovers_with: `Worker stopped`
- related_to: `pocketlab.commands.lite.security.scan`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Heartbeat, telemetry, and health publishers`
- depends_on: `Fleet, Apps, Security, Recovery, and Release APIs`
- depends_on: `Primary and secondary NATS listeners`
- uses: `Device offline and reconnect recovery`
- uses: `Sanitized Termux runtime capture`
- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/nats-jetstream.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
