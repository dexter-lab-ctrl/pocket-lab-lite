# Pocket Lab Architecture Context

Pocket Lab is an edge-first self-hosted control plane for app deployment, GitOps, fleet management, drift detection, security posture, NOC telemetry, release orchestration, and disaster recovery.

It is designed around a modern control-plane pattern:

```text
UI → FastAPI → NATS / JetStream → Worker → Events → UI
```

The system intentionally avoids retired shell-command compatibility paths for control-plane writes. Typed operations, NATS subjects, generated API contracts, and event-sourced workflow state form the main architectural backbone.

![](embed:system-context)
