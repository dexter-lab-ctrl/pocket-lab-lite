# Phase 6 Domain Worker Command Handlers

Domain commands now use explicit typed command subjects only. The legacy `retired update compatibility endpoint` intent bridge has been removed.

Supported domain command subjects include catalog refresh, native drift/policy
consistency checks, fleet join/key storage, release check/apply, health check,
security scan/configure, native Identity & Access, and recovery workflows.

The former Vault rotation and dynamic-secret subjects are retired. Historical
messages are acknowledged with a deterministic sanitized rejection and are
never dispatched to a worker or recorded as a new operation.

All write actions are queued through NATS/JetStream and executed by the worker.
