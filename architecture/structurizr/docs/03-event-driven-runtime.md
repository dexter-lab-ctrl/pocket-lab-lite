# Event Driven Runtime

The runtime uses NATS and JetStream as the durable command and event backbone.

FastAPI publishes typed commands, workers consume them, and events are emitted for:

- UI state
- operation logs
- workflow recovery
- retry handling
- auditability
- dead-letter analysis

![](embed:event-driven-runtime)

![](embed:typed-operation-flow)
