# Pocket Lab Lite

Pocket Lab Lite is the low-resource variant of Pocket Lab for Android/Termux and small edge devices.

It keeps the Pocket Lab control-plane architecture but removes heavyweight default observability services and presents a simpler appliance-style UI.

```text
React / Vite PWA
→ FastAPI
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

## Product goals

Pocket Lab Lite is designed to be:

- lightweight;
- mobile-first;
- self-hostable;
- friendly for Android/Termux;
- simple for normal operators;
- still grounded in typed operations, workers, events, and audit evidence.

## Default user-facing areas

- Home
- App Catalog
- Identity & Access
- Security
- Devices
- Rules
- Recovery
