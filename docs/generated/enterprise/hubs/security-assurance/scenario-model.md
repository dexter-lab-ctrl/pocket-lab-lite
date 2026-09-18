---
title: "Scenario → Model"
description: "Registered scenarios joined to model IDs and latest exact-SHA evidence."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Scenario → Model

Registered scenarios are safe invariant definitions. This catalog shows their canonical model relationships and latest bounded results.

<a id="harness-default-off"></a>
## `harness-default-off` — Harness default-off and production fail-closed state

**Purpose / invariant:** Production/default-off state never enables harness, destructive, Owner, or test-bypass authority implicitly.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep |
| Safety class | PASSIVE |
| Execution | configuration_posture |
| STRIDE | Spoofing, Elevation of Privilege |
| OWASP | A07, A01 |
| Attack paths | AP-01, AP-02, AP-03 |
| Controls | CTRL-API-CONTROL, CTRL-EVIDENCE-SANITIZE |
| Tools/evidence sources | — |
| Normalized evidence | Sanitized configuration booleans and startup reason codes only. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="harness-auth-boundary"></a>
## `harness-auth-boundary` — Synthetic Ed25519 session and capability boundary

**Purpose / invariant:** Synthetic assurance authority is purpose-bound, target-bound, runtime-bound, non-Owner, and non-destructive.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | authenticated_admission_posture |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A07, A01 |
| Attack paths | AP-01, AP-02, AP-03, AP-04, AP-09, AP-10 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | — |
| Normalized evidence | Sanitized binding booleans, profile name, target scope, and lifecycle classification. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="caddy-proof-strip"></a>
## `caddy-proof-strip` — Caddy never forwards qualification proof into FastAPI authority

**Purpose / invariant:** Proxy-visible headers never become harness authority and harness routes remain direct-loopback only.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | fixed_caddy_probe |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A07, A01, A05 |
| Attack paths | AP-01, AP-02, AP-07, AP-09 |
| Controls | CTRL-API-CONTROL |
| Tools/evidence sources | nuclei, owasp-zap, schemathesis, testssl.sh |
| Normalized evidence | Status codes, bounded response metadata, marker-presence booleans, and route classifications. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="runtime-readiness"></a>
## `runtime-readiness` — API health/readiness and PM2 readiness distinction

**Purpose / invariant:** Runtime readiness is based on API, message-bus, and worker truth rather than PM2 online alone.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep, adversarial |
| Safety class | PASSIVE |
| Execution | fixed_local_health_probe |
| STRIDE | Denial of Service, Information Disclosure |
| OWASP | A05 |
| Attack paths | AP-07, AP-11, AP-12 |
| Controls | CTRL-API-CONTROL |
| Tools/evidence sources | nmap, testssl.sh |
| Normalized evidence | Boolean readiness checks, status codes, and sanitized failure classes. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="control-plane-ownership"></a>
## `control-plane-ownership` — Assurance execution remains FastAPI to NATS to worker owned

**Purpose / invariant:** Browser clients cannot choose NATS subjects or commands; worker execution remains on the registered subject and domain handler.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep |
| Safety class | PASSIVE |
| Execution | worker_execution_receipt |
| STRIDE | Tampering, Repudiation, Elevation of Privilege |
| OWASP | A01, A08, A09 |
| Attack paths | AP-01, AP-02, AP-04, AP-06 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | — |
| Normalized evidence | Fixed subject/handler booleans and sanitized bus health only. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="evidence-redaction"></a>
## `evidence-redaction` — Assurance evidence contains only normalized sanitized output

**Purpose / invariant:** Secret-like values, credentials, private-key material, cookies, and NATS credential shapes never survive normalized persistence.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep, adversarial |
| Safety class | PASSIVE |
| Execution | redaction_contract |
| STRIDE | Repudiation, Information Disclosure, Tampering |
| OWASP | A02, A05, A08, A09 |
| Attack paths | AP-05, AP-06, AP-08 |
| Controls | CTRL-EVIDENCE-SANITIZE |
| Tools/evidence sources | — |
| Normalized evidence | Canary count, leak count, redaction booleans, and sanitization markers. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="security-projection"></a>
## `security-projection` — Existing Security projection and scanner lifecycle are available

**Purpose / invariant:** Scanner work remains worker-owned, sequential/resource-bounded, excludes user media, and produces normalized sanitized findings/evidence.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep |
| Safety class | PASSIVE |
| Execution | existing_security_projection |
| STRIDE | Tampering, Repudiation, Denial of Service, Information Disclosure |
| OWASP | A05, A06, A08, A09 |
| Attack paths | AP-04, AP-05, AP-06, AP-08 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-security, lynis, trivy |
| Normalized evidence | Registered tool results, normalized findings, bounded evidence references, baseline delta, and resource metrics. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | security/evidence/security-7f47c76330204ff79378253ab8a54396/summary.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/lynis-normalized.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/sbom.cdx.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/trivy-normalized.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/coverage-summary.json | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | security/evidence/security-c04834011af848478018766c46f1707e/summary.json, security/evidence/security-c04834011af848478018766c46f1707e/lynis-normalized.json, security/evidence/security-c04834011af848478018766c46f1707e/sbom.cdx.json, security/evidence/security-c04834011af848478018766c46f1707e/trivy-normalized.json, security/evidence/security-c04834011af848478018766c46f1707e/coverage-summary.json | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PARTIAL | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | security/evidence/security-015550d9d9e84545b0177341814db796/summary.json, security/evidence/security-015550d9d9e84545b0177341814db796/lynis-normalized.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-pocketlab-source-trivy.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-pocketlab_source-sbom.cdx.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-runtime-config.json, security/evidence/security-015550d9d9e84545b0177341814db796/resource-budget.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-proot-ubuntu-trivy-1.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-proot-ubuntu-trivy-2.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-proot-ubuntu-trivy-3.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-photoprism-trivy.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-photoprism-config-secret.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-photoprism_app_files-sbom.cdx.json, security/evidence/security-015550d9d9e84545b0177341814db796/target-backup-metadata.json, security/evidence/security-015550d9d9e84545b0177341814db796/trivy-normalized.json, security/evidence/security-015550d9d9e84545b0177341814db796/coverage-summary.json | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="policy-readiness"></a>
## `policy-readiness` — OPA loopback readiness and policy revision consistency

**Purpose / invariant:** Policy admission remains loopback-only, browser-hidden, revision-aware, and fail-closed when not ready.

| Field | Value |
| --- | --- |
| Suites | standard, deep |
| Safety class | PASSIVE |
| Execution | existing_opa_status |
| STRIDE | Tampering, Denial of Service, Elevation of Privilege |
| OWASP | A01, A08 |
| Attack paths | AP-11, AP-12, AP-14 |
| Controls | CTRL-POLICY-REVISION-LIFECYCLE |
| Tools/evidence sources | opa |
| Normalized evidence | Ready/degraded status, loopback/browser exposure booleans, and sanitized reason code. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="source-boundaries"></a>
## `source-boundaries` — Canonical source preserves browser, shell, NATS, and user-media boundaries

**Purpose / invariant:** Frontend contains no direct NATS or shell execution surface and checked backend/Caddy evidence boundaries remain present.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | PASSIVE |
| Execution | bounded_source_assertions |
| STRIDE | Tampering, Information Disclosure, Elevation of Privilege |
| OWASP | A01, A02, A05, A08 |
| Attack paths | AP-01, AP-02, AP-04, AP-05, AP-07 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS, CTRL-EVIDENCE-SANITIZE |
| Tools/evidence sources | bandit, semgrep, gitleaks |
| Normalized evidence | File/byte counts, match counts, fixed marker booleans, and no source excerpts. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="adversarial-negative-auth-probes"></a>
## `adversarial-negative-auth-probes` — Fixed malformed authentication and input probes remain denied

**Purpose / invariant:** Every fixed malformed/forged request is rejected without creating authority or intentional persistent mutation.

| Field | Value |
| --- | --- |
| Suites | adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | fixed_negative_auth_probes |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A03, A07 |
| Attack paths | AP-01, AP-02, AP-03, AP-04, AP-09, AP-10 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | — |
| Normalized evidence | Probe ID, fixed method/path identity, status code, rejection boolean, bounded response metadata, and duration. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | sanitized evidence | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |

<a id="threat-model-integrity"></a>
## `threat-model-integrity` — Current canonical threat model is complete and executable statuses are explicit

**Purpose / invariant:** Every current AP path is classified by registered assurance coverage and every reference resolves to canonical source.

| Field | Value |
| --- | --- |
| Suites | smoke, standard, deep |
| Safety class | PASSIVE |
| Execution | canonical_threat_model_check |
| STRIDE | Tampering, Repudiation |
| OWASP | A08, A09 |
| Attack paths | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 |
| Controls | CTRL-EVIDENCE-SANITIZE |
| Tools/evidence sources | — |
| Normalized evidence | Registry hashes, canonical IDs, execution defaults, retry policy, and coverage lists. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | sanitized evidence | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="attack-path-inventory"></a>
## `attack-path-inventory` — Every current AP path has a bounded execution classification

**Purpose / invariant:** No current AP path is silently treated as tested; coverage limitations remain explicit.

| Field | Value |
| --- | --- |
| Suites | standard, deep |
| Safety class | PASSIVE |
| Execution | attack_path_inventory |
| STRIDE | Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege |
| OWASP | A01, A02, A07, A08, A09 |
| Attack paths | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 |
| Controls | CTRL-EVIDENCE-SANITIZE |
| Tools/evidence sources | — |
| Normalized evidence | AP ID/name, classification, reason, STRIDE/OWASP mapping, controls, and human-review flag. |

| Suite | Result | Runtime SHA | Qualification | Evidence refs | Report |
| --- | --- | --- | --- | --- | --- |
| standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | sanitized evidence | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| deep | PASS | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | sanitized evidence | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

<a id="browser-origin-control-plane-bypass"></a>
## `browser-origin-control-plane-bypass` — Real browser control-plane ownership

**Purpose / invariant:** Browser JavaScript communicates only through approved same-origin HTTP/WebSocket surfaces and never directly reaches NATS, OPA, shell, or internal service ports.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A05, A07 |
| Attack paths | AP-01, AP-02, AP-07 |
| Controls | CTRL-BROWSER-NATS, CTRL-API-CONTROL, CTRL-BROWSER-SHELL |
| Tools/evidence sources | playwright-runtime, pocketlab-runtime-360, owasp-zap, playwright, mitmdump, tshark |
| Normalized evidence | Sanitized request-count/host-class/port-class metadata only; raw URLs and response bodies are not persisted. |

No published latest-suite result currently contains this scenario.

<a id="cross-origin-session-abuse"></a>
## `cross-origin-session-abuse` — Hostile-origin browser session abuse

**Purpose / invariant:** A hostile origin cannot read protected Pocket Lab API responses or inherit browser authority.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Spoofing, Information Disclosure, Elevation of Privilege |
| OWASP | A01, A07, A05 |
| Attack paths | AP-01, AP-09 |
| Controls | CTRL-HUMAN-SESSION-CSRF, CTRL-API-CONTROL |
| Tools/evidence sources | playwright-runtime, pocketlab-runtime-360, owasp-zap, playwright |
| Normalized evidence | Boolean cross-origin readability, status class, and WebSocket-open result only. |

No published latest-suite result currently contains this scenario.

<a id="csrf-protected-mutation"></a>
## `csrf-protected-mutation` — Cross-site protected mutation resistance

**Purpose / invariant:** Cross-site unauthenticated mutation is rejected and authenticated CSRF coverage is never inferred without a real disposable identity.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A07 |
| Attack paths | AP-09, AP-11 |
| Controls | CTRL-HUMAN-SESSION-CSRF, CTRL-API-CONTROL, CTRL-OPA-FAIL-CLOSED |
| Tools/evidence sources | pocketlab-runtime-360, playwright-runtime, owasp-zap, playwright, hurl |
| Normalized evidence | HTTP status class and explicit authenticated-fixture coverage state. |

No published latest-suite result currently contains this scenario.

<a id="owner-session-lifecycle"></a>
## `owner-session-lifecycle` — Owner session logout and revocation lifecycle

**Purpose / invariant:** HTTP, UI and WebSocket authority disappear promptly after logout or revocation.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Spoofing, Repudiation, Elevation of Privilege |
| OWASP | A01, A07, A09 |
| Attack paths | AP-09, AP-10 |
| Controls | CTRL-HUMAN-SESSION-CSRF, CTRL-WEBAUTHN-ASSURANCE |
| Tools/evidence sources | playwright-runtime, playwright |
| Normalized evidence | Sanitized session-state booleans and rejection classes; no cookies or passkey material. |

No published latest-suite result currently contains this scenario.

<a id="authorization-resource-boundary"></a>
## `authorization-resource-boundary` — Server-side resource authorization boundary

**Purpose / invariant:** Authorization decisions remain server-side and independent of caller-controlled IDs or UI restrictions.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A01, A03 |
| Attack paths | AP-10, AP-11, AP-13 |
| Controls | CTRL-API-CONTROL, CTRL-OPA-FAIL-CLOSED, CTRL-ENTERPRISE-ROLE-FINAL-OWNER |
| Tools/evidence sources | pocketlab-runtime-360, schemathesis, opa, hurl |
| Normalized evidence | Status/reason-code and policy-decision metadata only. |

No published latest-suite result currently contains this scenario.

<a id="websocket-auth-boundary"></a>
## `websocket-auth-boundary` — WebSocket authentication, Origin and revocation boundary

**Purpose / invariant:** Event-stream authority follows the intended browser authorization and Origin policy.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Spoofing, Information Disclosure, Elevation of Privilege |
| OWASP | A01, A07, A05 |
| Attack paths | AP-01, AP-09 |
| Controls | CTRL-HUMAN-SESSION-CSRF, CTRL-API-CONTROL |
| Tools/evidence sources | playwright-runtime, pocketlab-runtime-360, playwright, websocat |
| Normalized evidence | Handshake status and boolean open/reject classification only. |

No published latest-suite result currently contains this scenario.

<a id="pwa-offline-secret-retention"></a>
## `pwa-offline-secret-retention` — PWA storage and offline secret retention

**Purpose / invariant:** Browser persistence does not expose secret-shaped material and logout-specific claims require an authenticated disposable fixture.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Information Disclosure, Tampering, Repudiation |
| OWASP | A02, A07, A05, A09 |
| Attack paths | AP-06, AP-09 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-HUMAN-SESSION-CSRF |
| Tools/evidence sources | playwright-runtime, playwright |
| Normalized evidence | Counts and sanitized key classifications; stored values are never read. |

No published latest-suite result currently contains this scenario.

<a id="browser-network-egress-contract"></a>
## `browser-network-egress-contract` — Browser network egress contract

**Purpose / invariant:** The browser contacts only approved Caddy/same-origin destinations plus the fixed local hostile-origin fixture.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Information Disclosure, Tampering |
| OWASP | A02, A05 |
| Attack paths | AP-01, AP-07 |
| Controls | CTRL-BROWSER-NATS, CTRL-API-CONTROL |
| Tools/evidence sources | playwright-runtime, nmap, playwright, tshark |
| Normalized evidence | Request counts, host class, protocol and forbidden-port count. |

No published latest-suite result currently contains this scenario.

<a id="webauthn-challenge-boundary"></a>
## `webauthn-challenge-boundary` — WebAuthn challenge, RP and origin boundary

**Purpose / invariant:** Passkey assertions remain challenge-, origin-, RP- and session-bound.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A07 |
| Attack paths | AP-09, AP-10, AP-13 |
| Controls | CTRL-WEBAUTHN-ASSURANCE |
| Tools/evidence sources | playwright-runtime |
| Normalized evidence | Outcome/reason-code metadata; no private key or assertion payload persists. |

No published latest-suite result currently contains this scenario.

<a id="service-worker-version-integrity"></a>
## `service-worker-version-integrity` — Service-worker and cached-version integrity

**Purpose / invariant:** Service workers remain same-origin and stale cached code never broadens authority semantics.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_browser_runtime_evidence |
| STRIDE | Tampering, Information Disclosure |
| OWASP | A05, A08 |
| Attack paths | AP-05, AP-09 |
| Controls | CTRL-SUPPLY-CHAIN, CTRL-API-CONTROL, CTRL-HUMAN-SESSION-CSRF |
| Tools/evidence sources | playwright-runtime, playwright |
| Normalized evidence | Service-worker/cache counts and same-origin booleans only. |

No published latest-suite result currently contains this scenario.

<a id="tailnet-service-exposure"></a>
## `tailnet-service-exposure` — Private-network and Tailnet service exposure

**Purpose / invariant:** Only intended services are reachable in their registered scope; OPA/NATS monitor/harness remain internal as designed.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Information Disclosure, Denial of Service, Elevation of Privilege |
| OWASP | A01, A05 |
| Attack paths | AP-07 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, nmap, testssl.sh, httpx, tlsx |
| Normalized evidence | Fixed listener booleans, port labels and readiness classes. |

No published latest-suite result currently contains this scenario.

<a id="proxy-header-trust-confusion"></a>
## `proxy-header-trust-confusion` — Reverse-proxy header trust confusion

**Purpose / invariant:** Proxy metadata never becomes application identity or qualification authority.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A05, A07 |
| Attack paths | AP-01, AP-07, AP-09 |
| Controls | CTRL-API-CONTROL, CTRL-HUMAN-SESSION-CSRF |
| Tools/evidence sources | pocketlab-runtime-360, owasp-zap, nuclei, hurl, mitmdump |
| Normalized evidence | HTTP status class and marker-acceptance booleans. |

No published latest-suite result currently contains this scenario.

<a id="malformed-api-state-machine"></a>
## `malformed-api-state-machine` — Malformed and invalid API state-machine sequences

**Purpose / invariant:** Multi-step APIs reject invalid state transitions and replay without arbitrary mutation targets.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service, Elevation of Privilege |
| OWASP | A01, A04, A05, A03, A08 |
| Attack paths | AP-04, AP-11, AP-08, AP-12, AP-13 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS, CTRL-OPA-FAIL-CLOSED, CTRL-INDEPENDENT-APPROVAL-CONTINUATION |
| Tools/evidence sources | pocketlab-runtime-360, schemathesis, owasp-zap, hurl |
| Normalized evidence | Status/reason-code and idempotency metadata only. |

No published latest-suite result currently contains this scenario.

<a id="device-invite-replay-and-misbinding"></a>
## `device-invite-replay-and-misbinding` — Device invite replay and identity misbinding

**Purpose / invariant:** Invites are one-time and identity-bound; mismatch causes no env overwrite or PM2 restart.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Tampering, Elevation of Privilege |
| OWASP | A01, A07 |
| Attack paths | AP-03, AP-09 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, hurl |
| Normalized evidence | Reason codes, mutation booleans and audit-event identifiers; no invite token persists. |

No published latest-suite result currently contains this scenario.

<a id="nats-command-replay-integrity"></a>
## `nats-command-replay-integrity` — NATS command replay and target integrity

**Purpose / invariant:** Duplicate delivery is idempotent/target-bound and callers never select NATS subjects or envelopes.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service |
| OWASP | A01, A08, A09 |
| Attack paths | AP-04 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, nats-cli, hurl |
| Normalized evidence | Operation IDs, delivery counts and sanitized reason codes only. |

No published latest-suite result currently contains this scenario.

<a id="worker-reconnect-command-integrity"></a>
## `worker-reconnect-command-integrity` — Worker reconnect and command delivery integrity

**Purpose / invariant:** Commands are not lost, duplicated or reordered across worker reconnect; acknowledgements remain truthful.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service |
| OWASP | A08, A09 |
| Attack paths | AP-04, AP-07 |
| Controls | CTRL-EXECUTION-OWNERS, CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360 |
| Normalized evidence | Sanitized command IDs/counts and reconnect classifications only. |

No published latest-suite result currently contains this scenario.

<a id="tls-identity-drift"></a>
## `tls-identity-drift` — TLS identity and transport posture drift

**Purpose / invariant:** The runtime presents the intended certificate identity and approved transport posture.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Information Disclosure |
| OWASP | A02, A05 |
| Attack paths | AP-07, AP-09 |
| Controls | CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, testssl.sh, tlsx, httpx |
| Normalized evidence | Protocol/cipher class, identity validation boolean and normalized TLS findings. |

No published latest-suite result currently contains this scenario.

<a id="audit-event-attribution"></a>
## `audit-event-attribution` — Security-sensitive audit attribution

**Purpose / invariant:** Protected operations remain attributable without leaking credentials or raw identity secrets.

| Field | Value |
| --- | --- |
| Suites | standard, deep |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Repudiation, Tampering |
| OWASP | A09 |
| Attack paths | AP-06, AP-10, AP-13 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360 |
| Normalized evidence | Audit event type, actor class, target class and operation correlation only. |

No published latest-suite result currently contains this scenario.

<a id="recovery-object-authorization"></a>
## `recovery-object-authorization` — Recovery object authorization boundary

**Purpose / invariant:** Recovery objects cannot be read or operated across authorization boundaries.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A01, A08 |
| Attack paths | AP-08, AP-11 |
| Controls | CTRL-API-CONTROL, CTRL-EXPLICIT-PROMOTION |
| Tools/evidence sources | pocketlab-runtime-360, schemathesis |
| Normalized evidence | Status/reason-code and object-class metadata only. |

No published latest-suite result currently contains this scenario.

<a id="app-install-authority-boundary"></a>
## `app-install-authority-boundary` — App installation control-plane authority

**Purpose / invariant:** Install authority remains FastAPI → policy → NATS/worker owned and callers cannot choose argv/subjects.

| Field | Value |
| --- | --- |
| Suites | standard, deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A01, A08 |
| Attack paths | AP-01, AP-04, AP-11 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, opa |
| Normalized evidence | Admission/reason-code/execution-path metadata only. |

No published latest-suite result currently contains this scenario.

<a id="remote-access-truthfulness"></a>
## `remote-access-truthfulness` — Remote access readiness truthfulness

**Purpose / invariant:** Remote access is shown ready only when all required evidence is actually ready.

| Field | Value |
| --- | --- |
| Suites | standard, deep |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Information Disclosure, Denial of Service |
| OWASP | A05 |
| Attack paths | AP-07, AP-12 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, nmap, playwright, httpx |
| Normalized evidence | Readiness booleans and fixed listener classifications. |

No published latest-suite result currently contains this scenario.

<a id="rate-limit-and-admission-resilience"></a>
## `rate-limit-and-admission-resilience` — Bounded admission and duplicate-operation resilience

**Purpose / invariant:** Low-power runtime remains responsive and server-owned admission/idempotency prevents unbounded duplicate work.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Denial of Service, Repudiation |
| OWASP | A04, A05 |
| Attack paths | AP-04, AP-07, AP-11 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS, CTRL-OPA-FAIL-CLOSED |
| Tools/evidence sources | pocketlab-runtime-360, owasp-zap, k6 |
| Normalized evidence | Request count, max concurrency, status classes and duration only. |

No published latest-suite result currently contains this scenario.

<a id="slow-client-resource-exhaustion"></a>
## `slow-client-resource-exhaustion` — Bounded slow-client resilience

**Purpose / invariant:** Two bounded slow clients do not make the control API unavailable.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Denial of Service |
| OWASP | A05, A04 |
| Attack paths | AP-07, AP-11 |
| Controls | CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, k6 |
| Normalized evidence | Connection count, hold duration and concurrent health status only. |

No published latest-suite result currently contains this scenario.

<a id="release-artifact-tamper"></a>
## `release-artifact-tamper` — Release artifact tamper and provenance detection

**Purpose / invariant:** A modified artifact cannot masquerade as the exact qualified release.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A06, A08 |
| Attack paths | AP-05 |
| Controls | CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION |
| Tools/evidence sources | pocketlab-runtime-360, cosign, syft, grype |
| Normalized evidence | Artifact-presence, digest and signature/provenance status only. |

No published latest-suite result currently contains this scenario.

<a id="dependency-confusion-and-lock-integrity"></a>
## `dependency-confusion-and-lock-integrity` — Dependency lock and resolved graph integrity

**Purpose / invariant:** Installed/qualified dependency evidence stays bound to repository-owned lock inputs.

| Field | Value |
| --- | --- |
| Suites | deep |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Information Disclosure, Elevation of Privilege |
| OWASP | A06, A08 |
| Attack paths | AP-05 |
| Controls | CTRL-SUPPLY-CHAIN |
| Tools/evidence sources | pocketlab-runtime-360, osv-scanner, syft, grype, pip-audit, npm-audit |
| Normalized evidence | Manifest hashes, package identities and normalized advisories only. |

No published latest-suite result currently contains this scenario.

<a id="security-evidence-poisoning"></a>
## `security-evidence-poisoning` — Security evidence poisoning resistance

**Purpose / invariant:** Tool output cannot fabricate PASS, inject raw secrets/markup, or become authoritative outside its schema.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial, standard |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Repudiation, Information Disclosure |
| OWASP | A02, A08, A09 |
| Attack paths | AP-06 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION |
| Tools/evidence sources | pocketlab-runtime-360, gitleaks, semgrep, hurl |
| Normalized evidence | Leak counts, schema/reason codes and normalized finding metadata. |

No published latest-suite result currently contains this scenario.

<a id="unicode-log-and-ui-injection"></a>
## `unicode-log-and-ui-injection` — Unicode, terminal and UI injection resistance

**Purpose / invariant:** Untrusted names/evidence cannot create executable HTML or misleading terminal/audit records.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial, standard |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Repudiation, Information Disclosure |
| OWASP | A03, A09 |
| Attack paths | AP-06, AP-09 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-API-CONTROL, CTRL-HUMAN-SESSION-CSRF |
| Tools/evidence sources | playwright-runtime, pocketlab-runtime-360, semgrep, playwright |
| Normalized evidence | Escaping booleans and sanitized render classification only. |

No published latest-suite result currently contains this scenario.

<a id="backup-confidentiality-integrity"></a>
## `backup-confidentiality-integrity` — Backup confidentiality and integrity

**Purpose / invariant:** Backup contents remain confidential and tampering is detected before restore admission.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Information Disclosure, Tampering, Repudiation |
| OWASP | A02, A08, A01 |
| Attack paths | AP-08 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, hurl |
| Normalized evidence | Integrity/auth booleans and reason codes; no backup payload persisted. |

No published latest-suite result currently contains this scenario.

<a id="restore-transaction-integrity"></a>
## `restore-transaction-integrity` — Restore transaction and interruption integrity

**Purpose / invariant:** Interrupted restore cannot expose partially trusted active state and recovery remains deterministic.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service |
| OWASP | A08, A09, A01 |
| Attack paths | AP-08 |
| Controls | CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, hurl |
| Normalized evidence | Checkpoint/journal/status metadata only. |

No published latest-suite result currently contains this scenario.

<a id="app-package-provenance"></a>
## `app-package-provenance` — App package and catalog provenance

**Purpose / invariant:** App installation input is distinguishable from tampered/unqualified artifacts.

| Field | Value |
| --- | --- |
| Suites | deep |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A06, A08 |
| Attack paths | AP-05 |
| Controls | CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION |
| Tools/evidence sources | pocketlab-runtime-360, cosign, syft, trivy |
| Normalized evidence | Registered artifact IDs, digests, SBOM/signature status only. |

No published latest-suite result currently contains this scenario.

<a id="android-termux-host-hardening"></a>
## `android-termux-host-hardening` — Android/Termux runtime host hardening

**Purpose / invariant:** Runtime files/services/listeners preserve least exposure and known hardening posture for Termux constraints.

| Field | Value |
| --- | --- |
| Suites | deep |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Information Disclosure, Elevation of Privilege, Denial of Service |
| OWASP | A05, A06 |
| Attack paths | AP-02, AP-07 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS |
| Tools/evidence sources | pocketlab-runtime-360, lynis, trivy, nmap |
| Normalized evidence | Normalized host findings, applicability and listener posture only. |

No published latest-suite result currently contains this scenario.

<a id="runtime-env-secret-boundary"></a>
## `runtime-env-secret-boundary` — Runtime environment and frontend secret boundary

**Purpose / invariant:** Backend secrets never become frontend bundles, generated docs, normalized evidence, or browser-readable config.

| Field | Value |
| --- | --- |
| Suites | deep, standard |
| Safety class | PASSIVE |
| Execution | dev_pc_deep_provenance_evidence |
| STRIDE | Information Disclosure, Tampering |
| OWASP | A02, A05 |
| Attack paths | AP-01, AP-05, AP-06 |
| Controls | CTRL-EVIDENCE-SANITIZE, CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, gitleaks, trivy, playwright |
| Normalized evidence | Finding metadata and redaction booleans only. |

No published latest-suite result currently contains this scenario.

<a id="hidden-route-and-debug-surface"></a>
## `hidden-route-and-debug-surface` — Hidden route and debug surface discovery

**Purpose / invariant:** Unexpected debug/admin/metrics surfaces are not externally reachable.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Information Disclosure, Elevation of Privilege |
| OWASP | A01, A05 |
| Attack paths | AP-01, AP-07 |
| Controls | CTRL-API-CONTROL |
| Tools/evidence sources | pocketlab-runtime-360, nuclei, owasp-zap, katana, httpx, ffuf |
| Normalized evidence | Route labels/status classes and normalized safe-template findings. |

No published latest-suite result currently contains this scenario.

<a id="approval-continuation-replay"></a>
## `approval-continuation-replay` — Approval continuation replay and exact-binding integrity

**Purpose / invariant:** Approval remains independent, exact-action-bound and single-use.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Tampering, Repudiation, Elevation of Privilege |
| OWASP | A01, A07, A08, A09 |
| Attack paths | AP-13 |
| Controls | CTRL-WEBAUTHN-ASSURANCE, CTRL-INDEPENDENT-APPROVAL-CONTINUATION |
| Tools/evidence sources | pocketlab-runtime-360, opa, hurl |
| Normalized evidence | Reason codes, actor classes, binding booleans and continuation-use count. |

No published latest-suite result currently contains this scenario.

<a id="temporary-exception-scope-bypass"></a>
## `temporary-exception-scope-bypass` — Temporary exception scope, expiry and revocation

**Purpose / invariant:** Temporary exceptions cannot widen beyond approved action/target/time and fail closed after expiry/revocation.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Elevation of Privilege |
| OWASP | A01, A08, A05 |
| Attack paths | AP-14 |
| Controls | CTRL-TEMPORARY-EXCEPTION-SCOPE, CTRL-OPA-FAIL-CLOSED |
| Tools/evidence sources | pocketlab-runtime-360, opa, hurl |
| Normalized evidence | Scope/time/revocation decision metadata and reason codes only. |

No published latest-suite result currently contains this scenario.

<a id="policy-known-good-recovery"></a>
## `policy-known-good-recovery` — Policy known-good recovery integrity

**Purpose / invariant:** Bad/stale policy cannot become silently authoritative and known-good recovery remains auditable/fail-closed.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service, Elevation of Privilege |
| OWASP | A05, A08, A01 |
| Attack paths | AP-11, AP-12 |
| Controls | CTRL-POLICY-REVISION-LIFECYCLE, CTRL-OPA-FAIL-CLOSED |
| Tools/evidence sources | pocketlab-runtime-360, opa, hurl |
| Normalized evidence | Revision IDs/hashes, readiness and recovery reason codes only. |

No published latest-suite result currently contains this scenario.

<a id="webauthn-origin-rpid-mismatch"></a>
## `webauthn-origin-rpid-mismatch` — WebAuthn origin and RP-ID assurance remains explicit

**Purpose / invariant:** WebAuthn origin/RP-ID binding is never inferred PASS from unrelated browser or password-login evidence.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Elevation of Privilege |
| OWASP | A01, A07 |
| Attack paths | AP-09, AP-10, AP-13 |
| Controls | CTRL-WEBAUTHN-ASSURANCE |
| Tools/evidence sources | playwright |
| Normalized evidence | Scenario status, fixed tool IDs, sanitized finding IDs, bounded runtime metadata, exact source/runtime SHA, and explicit unavailable/partial states. |

No published latest-suite result currently contains this scenario.

<a id="duplicate-operation-flood"></a>
## `duplicate-operation-flood` — Duplicate operations remain idempotent and bounded

**Purpose / invariant:** Duplicate submissions cannot create unbounded parallel work, replay approved continuations, or bypass idempotency.

| Field | Value |
| --- | --- |
| Suites | deep, adversarial |
| Safety class | SAFE_ACTIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Tampering, Repudiation, Denial of Service |
| OWASP | A01, A04, A09 |
| Attack paths | AP-04, AP-13 |
| Controls | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS, CTRL-INDEPENDENT-APPROVAL-CONTINUATION |
| Tools/evidence sources | k6, hurl |
| Normalized evidence | Scenario status, fixed tool IDs, sanitized finding IDs, bounded runtime metadata, exact source/runtime SHA, and explicit unavailable/partial states. |

No published latest-suite result currently contains this scenario.

<a id="cookie-security-posture"></a>
## `cookie-security-posture` — Browser session cookies retain secure scope and lifecycle flags

**Purpose / invariant:** Session-bearing cookies are Secure, HttpOnly where applicable, SameSite-scoped, and not over-broad in path/domain.

| Field | Value |
| --- | --- |
| Suites | standard, deep |
| Safety class | PASSIVE |
| Execution | dev_pc_live_runtime_evidence |
| STRIDE | Spoofing, Information Disclosure |
| OWASP | A02, A07 |
| Attack paths | AP-09 |
| Controls | CTRL-HUMAN-SESSION-CSRF |
| Tools/evidence sources | playwright |
| Normalized evidence | Scenario status, fixed tool IDs, sanitized finding IDs, bounded runtime metadata, exact source/runtime SHA, and explicit unavailable/partial states. |

No published latest-suite result currently contains this scenario.

