---
title: "NATS / JetStream"
description: "Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# NATS / JetStream

Provides the command and event backbone with durable delivery; it is never contacted directly by the frontend.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/nats-jetstream.light.svg" aria-label="Open full-size NATS / JetStream mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/nats-jetstream.light.svg#only-light" alt="NATS / JetStream mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/nats-jetstream.dark.svg#only-dark" alt="NATS / JetStream mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>NATS / JetStream mini architecture. <a href="../../../../../assets/diagrams/production/components/nats-jetstream.light.svg">View full-size diagram</a></figcaption>
</figure>


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | event |
| Runs on | Server host |
| Started / runtime owner | PM2 |
| Process owner | pocket-nats |
| Execution owner | Messaging backbone |
| Data owner | JetStream storage |
| Recovery owner | Startup scripts / PM2 |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Validated commands
- events

## Outputs

- Durable command delivery
- event fan-out

## Protocols

- NATS
- JetStream

## Durable state

- JetStream streams and consumers

## Health and readiness

- NATS monitor
- JetStream status

## Evidence

- consumer health

## Failure behavior

- listener unavailable
- consumer stalled

## Recovery behavior

- reconnect
- durable consumer re-enrollment

## Connections

### Incoming

- Fleet, Apps, Security, Recovery, and Release APIs — publishes validated command
- Primary and secondary NATS listeners — listener endpoints
- Heartbeat, telemetry, and health publishers — heartbeat/telemetry/health

### Outgoing

- delivers device command — Device command executor
- durable delivery — Worker process
- fleet events projected — Enrollment and device lifecycle state

## Source verification

- `pm2_process` — `pocket-nats`
- `contract` — `contracts/generated/lite-asyncapi.json`
- `nats_subject` — `pocketlab.commands.lite.security.scan`

## Existing documentation

- [lite-events.md](../../../development/lite-events.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Request and control flow](../request-control.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Security and safety](../security.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
