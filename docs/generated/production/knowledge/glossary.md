---
title: "Glossary"
description: "Canonical Pocket Lab Lite terminology ontology."
generated: true
audience: production
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Glossary

| Term | Definition | Aliases | Domain |
| --- | --- | --- | --- |
| durable authority | The server-side canonical state that survives process restarts and is authoritative over derived projections. | durable source of truth | architecture |
| Enterprise Mode | Personal Mode is the default local-owner experience. Enterprise Mode is an explicit opt-in that resolves authoritative server-owned Owner, Admin, Operator, Viewer, and Auditor memberships; it is not an external identity-provider integration. | personal mode, enterprise roles | identity |
| evidence lane | One bounded observation source such as backend, Termux, desktop browser, or mobile browser used for runtime verification. | runtime lane | validation |
| fresh preview | A restore preview recent enough to satisfy write-safety guards before a destructive restore. | — | recovery |
| mapped presentation | A user-facing representation that differs textually from backend values but is explicitly allowlisted as semantically equivalent. | semantic presentation mapping | parity |
| OIDC | Optional OIDC is not implemented. A separately approved protected secret-storage capability is required before an OIDC integration can be added safely. | OpenID Connect, single sign-on | identity |
| operational health | Current runtime ability of a subsystem to serve reads, accept safe writes, recover, and maintain required connectivity independently of semantic parity. | runtime health | operations |
| prepared projection | A bounded read model derived from authoritative state for fast UI/API reads; it may become stale without replacing durable authority. | prepared state | projections |
| promoted runtime evidence | Sanitized runtime evidence explicitly bound to a release and source commit and accepted through the promotion gate. | runtime verification baseline | validation |
| rejoin | An explicit device enrollment path used after identity ownership changes; it is not an automatic overwrite. | — | devices |
| release binding | The verified association among release tag, source commit, runtime evidence, and release metadata. | — | release |
| repair | An explicit recovery action that preserves identity and backend ownership rather than silently mutating enrolled state. | — | devices |
| Rules continuation | An Enterprise device removal may require a passkey-stepped-up independent Owner or Admin approval. Approval never executes the action: the initiator must explicitly retry and the one-use continuation is consumed atomically. Temporary catalog-install exceptions are exact app, device, identity, and revision scoped, expire within 60 minutes, and can be revoked. | independent approval, temporary exception | rules |
| semantic parity | Agreement of intended meaning across canonical backend, API, runtime, and presentation lanes under declared comparators. | runtime parity | parity |
| trust boundary | An architecture boundary where trust level, credentials, validation, or execution ownership changes. | — | security |
| typed Safety Rules revision | Safety Rules accept only approved typed templates and bounded parameters. Each immutable candidate has a complete manifest, is activated by the supervisor with active and known-good pointers, and fails closed when the proved OPA-loaded revision is uncertain or mismatched. | policy revision, OPA candidate | rules |
