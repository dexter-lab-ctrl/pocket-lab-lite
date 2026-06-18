# Lite Security Model

Pocket Lab Lite keeps the safety model of Pocket Lab while presenting it in simpler language.

## Preserved controls

- FastAPI remains the only frontend-facing control API.
- Write actions flow through NATS / JetStream and workers.
- Typed Operations remain the execution contract.
- Risky actions require clear confirmation.
- Restore and destructive workflows must not run silently.
- Approval, auto-approval, rejection, resume, and audit evidence remain explicit internally.

## Hidden by default

The lite UI should not expose:

- raw Vault tokens;
- raw secret paths;
- policy source internals;
- NATS or JetStream details;
- worker implementation details;
- backend file paths;
- raw event payloads;
- raw audit payloads.

## User-facing language

Use plain labels such as:

- Passwords & Access
- Change Password
- Protection enabled
- Requires confirmation
- Allowed actions
- Safety Check
- No critical issues
