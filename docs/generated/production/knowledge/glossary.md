---
title: "Glossary"
description: "Canonical Pocket Lab Lite terminology ontology."
generated: true
audience: production
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Glossary

| Term | Definition | Aliases | Domain |
| --- | --- | --- | --- |
| durable authority | The server-side canonical state that survives process restarts and is authoritative over derived projections. | durable source of truth | architecture |
| evidence lane | One bounded observation source such as backend, Termux, desktop browser, or mobile browser used for runtime verification. | runtime lane | validation |
| fresh preview | A restore preview recent enough to satisfy write-safety guards before a destructive restore. | — | recovery |
| mapped presentation | A user-facing representation that differs textually from backend values but is explicitly allowlisted as semantically equivalent. | semantic presentation mapping | parity |
| operational health | Current runtime ability of a subsystem to serve reads, accept safe writes, recover, and maintain required connectivity independently of semantic parity. | runtime health | operations |
| prepared projection | A bounded read model derived from authoritative state for fast UI/API reads; it may become stale without replacing durable authority. | prepared state | projections |
| promoted runtime evidence | Sanitized runtime evidence explicitly bound to a release and source commit and accepted through the promotion gate. | runtime verification baseline | validation |
| rejoin | An explicit device enrollment path used after identity ownership changes; it is not an automatic overwrite. | — | devices |
| release binding | The verified association among release tag, source commit, runtime evidence, and release metadata. | — | release |
| repair | An explicit recovery action that preserves identity and backend ownership rather than silently mutating enrolled state. | — | devices |
| semantic parity | Agreement of intended meaning across canonical backend, API, runtime, and presentation lanes under declared comparators. | runtime parity | parity |
| trust boundary | An architecture boundary where trust level, credentials, validation, or execution ownership changes. | — | security |
