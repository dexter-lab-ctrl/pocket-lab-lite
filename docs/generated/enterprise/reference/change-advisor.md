---
title: "Change Impact Advisor"
description: "Deterministic source-path change simulation without executing changes."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Change Impact Advisor

This advisor predicts consequences; it never mutates source/runtime. Inputs: source path graph, API/event contracts, test ownership, documentation graph, architecture/trust boundaries, security controls, release contract, runtime/promoted evidence metadata. Algorithm: bounded deterministic prefix/rule intersection; no ML and no runtime mutation.

| Changed path | Potential impacts | Tests/tasks | Generated artifacts | Reviews | Security |
| --- | --- | --- | --- | --- | --- |
| pocket-lab-final-structure/runtime/api_fastapi/ | OpenAPI, API/UI trace, Schemathesis, parity, reason codes, events, docs, release compatibility | lite:api:check, lite:api:schemathesis, lite:api:breaking-changes, lite:docs:check, lite:check | Release Delta, Change Impact | backend/API, security when auth/evidence changes | risk-based |
| src/ | frontend build, API usage, Playwright, accessibility, safe snapshots, documentation | lite:test:frontend, lite:test:e2e:mocked, lite:test:a11y, lite:docs:check | Release Delta, Change Impact | frontend, backend API owner for contract changes | risk-based |
| pocket-lab-final-structure/runtime/agents/ | device commands, heartbeats, supervisor recovery, fleet states, threat model | lite:check, lite:docs:check | Release Delta, Change Impact | device runtime, security | risk-based |
| pocket-lab-final-structure/runtime/workers/ | command execution, NATS consumers, evidence, runbooks, FMEA | lite:check, lite:docs:check | Release Delta, Change Impact | worker runtime, security | risk-based |
| pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/ | Android/Termux bootstrap, identity, Caddy/Tailscale, release, threat model | bash -n, lite:docs:check, lite:check | Release Delta, Change Impact | bootstrap/runtime, security | required |
| contracts/ | generated contracts, knowledge, parity, release delta, documentation | lite:contracts:check, lite:docs:check | Documentation Intelligence, Release Delta, Knowledgebase | contract owner | risk-based |
| scripts/docs/ | generated docs, determinism, page anatomy, MkDocs | lite:docs:sync, lite:docs:check | Documentation Intelligence, Release Delta, Knowledgebase | documentation platform | risk-based |
| security/ | static analysis, controls, threat model, supply-chain evidence | lite:docs:supply-chain:capture, lite:docs:check | Release Delta, Change Impact | security | risk-based |
| .github/workflows/ | release provenance, Scorecard, token permissions, release evidence | lite:release:dry-run, lite:docs:check | Release Delta, Change Impact | release/security | required |
