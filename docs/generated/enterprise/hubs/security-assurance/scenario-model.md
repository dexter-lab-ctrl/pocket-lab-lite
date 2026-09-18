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

