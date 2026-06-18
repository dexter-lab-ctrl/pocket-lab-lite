# Phase 6 Domain Worker Command Handlers

Domain commands now use explicit typed command subjects only. The legacy `retired update compatibility endpoint` intent bridge has been removed.

Supported domain command subjects include catalog refresh, drift actions, fleet join/key storage, release check/apply, health check, security scan/configure, Vault rotate, and dynamic secret read.

All write actions are queued through NATS/JetStream and executed by the worker.
