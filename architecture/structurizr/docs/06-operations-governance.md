# Operations Governance

Pocket Lab governance is centered on typed operations.

Every important UI write action should map to:

- a typed operation
- a FastAPI endpoint
- a NATS command subject
- success and failure events
- audit records where applicable
- generated documentation

The generated operations catalog under `operations/*.yaml` acts as the Backstage-style source of truth for operation metadata.
