---
title: "Model ↔ Assurance Evidence"
description: "AP, control, scenario, qualification, SHA, finding, and human-review correlation."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Model ↔ Assurance Evidence

Generated join view over canonical IDs and sanitized report JSON. It is not a second threat, scenario, control, or risk database.

<a id="ap-01"></a>
### AP-01 — Browser control-plane bypass

**Trust boundaries:** browser, messaging-execution
**Controls:** CTRL-BROWSER-NATS, CTRL-API-CONTROL
**Scenarios:** harness-default-off, harness-auth-boundary, caddy-proof-strip, control-plane-ownership, source-boundaries, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, browser-origin-control-plane-bypass, cross-origin-session-abuse, websocket-auth-boundary, browser-network-egress-contract, proxy-header-trust-confusion, app-install-authority-boundary, runtime-env-secret-boundary, hidden-route-and-debug-surface
**STRIDE:** Spoofing, Tampering, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-01 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-01#security-atlas)

<a id="ap-02"></a>
### AP-02 — Browser shell execution

**Trust boundaries:** browser, control-api, server-host
**Controls:** CTRL-BROWSER-SHELL, CTRL-API-CONTROL
**Scenarios:** harness-default-off, harness-auth-boundary, caddy-proof-strip, control-plane-ownership, source-boundaries, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, browser-origin-control-plane-bypass, android-termux-host-hardening
**STRIDE:** Tampering, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | EXECUTABLE_NOW | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-02 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-02#security-atlas)

<a id="ap-03"></a>
### AP-03 — Forged managed-device identity

**Trust boundaries:** managed-device, control-api, messaging-execution
**Controls:** CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS
**Scenarios:** harness-default-off, harness-auth-boundary, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, device-invite-replay-and-misbinding
**STRIDE:** Spoofing, Tampering, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-03 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-03#security-atlas)

<a id="ap-04"></a>
### AP-04 — Messaging command tampering or replay

**Trust boundaries:** control-api, messaging-execution, managed-device
**Controls:** CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS
**Scenarios:** harness-auth-boundary, control-plane-ownership, security-projection, source-boundaries, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, malformed-api-state-machine, nats-command-replay-integrity, worker-reconnect-command-integrity, app-install-authority-boundary, rate-limit-and-admission-resilience, duplicate-operation-flood
**STRIDE:** Tampering, Repudiation, Denial of Service

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-04 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-04#security-atlas)

<a id="ap-05"></a>
### AP-05 — Supply-chain artifact compromise

**Trust boundaries:** external-release, server-host, application-container
**Controls:** CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION, CTRL-EVIDENCE-SANITIZE
**Scenarios:** evidence-redaction, security-projection, source-boundaries, threat-model-integrity, attack-path-inventory, service-worker-version-integrity, release-artifact-tamper, dependency-confusion-and-lock-integrity, app-package-provenance, runtime-env-secret-boundary
**STRIDE:** Tampering, Information Disclosure, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-05 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-05#security-atlas)

<a id="ap-06"></a>
### AP-06 — Evidence poisoning

**Trust boundaries:** external-release, durable-state, server-host
**Controls:** CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION
**Scenarios:** control-plane-ownership, evidence-redaction, security-projection, threat-model-integrity, attack-path-inventory, pwa-offline-secret-retention, audit-event-attribution, security-evidence-poisoning, unicode-log-and-ui-injection, runtime-env-secret-boundary
**STRIDE:** Tampering, Repudiation, Information Disclosure

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | assurance-2a29076a8244411daed1b0a5ca0c1d1a-15deb392776f0f7b27d15fb1 | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | assurance-b798f7e3a4c64b8b8c780a6c737b9e23-15deb392776f0f7b27d15fb1 | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | EXECUTABLE_NOW | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | EXECUTABLE_NOW | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | assurance-3d7968589ce447f18454d1caf69a10e3-15deb392776f0f7b27d15fb1 | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-06 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-06#security-atlas)

<a id="ap-07"></a>
### AP-07 — Tailnet/private-network exposure

**Trust boundaries:** private-network, control-api, server-host
**Controls:** CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS
**Scenarios:** caddy-proof-strip, runtime-readiness, source-boundaries, threat-model-integrity, attack-path-inventory, browser-origin-control-plane-bypass, browser-network-egress-contract, tailnet-service-exposure, proxy-header-trust-confusion, worker-reconnect-command-integrity, tls-identity-drift, remote-access-truthfulness, rate-limit-and-admission-resilience, slow-client-resource-exhaustion, android-termux-host-hardening, hidden-route-and-debug-surface
**STRIDE:** Spoofing, Information Disclosure, Denial of Service

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-07 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-07#security-atlas)

<a id="ap-08"></a>
### AP-08 — Recovery state tampering

**Trust boundaries:** durable-state, control-api
**Controls:** CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL
**Scenarios:** evidence-redaction, security-projection, threat-model-integrity, attack-path-inventory, malformed-api-state-machine, recovery-object-authorization, backup-confidentiality-integrity, restore-transaction-integrity
**STRIDE:** Tampering, Repudiation, Denial of Service

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-08 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-08#security-atlas)

<a id="ap-09"></a>
### AP-09 — Human identity and WebAuthn assurance misuse

**Trust boundaries:** browser, control-api, durable-state
**Controls:** CTRL-HUMAN-SESSION-CSRF, CTRL-WEBAUTHN-ASSURANCE
**Scenarios:** harness-auth-boundary, caddy-proof-strip, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, cross-origin-session-abuse, csrf-protected-mutation, owner-session-lifecycle, websocket-auth-boundary, pwa-offline-secret-retention, webauthn-challenge-boundary, service-worker-version-integrity, proxy-header-trust-confusion, device-invite-replay-and-misbinding, tls-identity-drift, unicode-log-and-ui-injection, webauthn-origin-rpid-mismatch, cookie-security-posture
**STRIDE:** Spoofing, Tampering, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-09 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-09#security-atlas)

<a id="ap-10"></a>
### AP-10 — Enterprise membership and final-Owner privilege escalation

**Trust boundaries:** browser, control-api, durable-state
**Controls:** CTRL-WEBAUTHN-ASSURANCE, CTRL-ENTERPRISE-ROLE-FINAL-OWNER
**Scenarios:** harness-auth-boundary, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, owner-session-lifecycle, authorization-resource-boundary, webauthn-challenge-boundary, audit-event-attribution, webauthn-origin-rpid-mismatch
**STRIDE:** Tampering, Repudiation, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-10 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-10#security-atlas)

<a id="ap-11"></a>
### AP-11 — OPA authorization decision integrity failure

**Trust boundaries:** browser, control-api
**Controls:** CTRL-API-CONTROL, CTRL-OPA-FAIL-CLOSED
**Scenarios:** runtime-readiness, policy-readiness, threat-model-integrity, attack-path-inventory, csrf-protected-mutation, authorization-resource-boundary, malformed-api-state-machine, recovery-object-authorization, app-install-authority-boundary, rate-limit-and-admission-resilience, slow-client-resource-exhaustion, policy-known-good-recovery
**STRIDE:** Tampering, Elevation of Privilege, Denial of Service

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | PARTIALLY_EXECUTABLE | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-11 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-11#security-atlas)

<a id="ap-12"></a>
### AP-12 — Policy revision activation and recovery integrity

**Trust boundaries:** browser, control-api, durable-state
**Controls:** CTRL-POLICY-REVISION-LIFECYCLE, CTRL-OPA-FAIL-CLOSED
**Scenarios:** runtime-readiness, policy-readiness, threat-model-integrity, attack-path-inventory, malformed-api-state-machine, remote-access-truthfulness, policy-known-good-recovery
**STRIDE:** Tampering, Repudiation, Denial of Service

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | STATIC_EVIDENCE_ONLY | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-12 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-12#security-atlas)

<a id="ap-13"></a>
### AP-13 — Approval and continuation integrity

**Trust boundaries:** browser, control-api, durable-state
**Controls:** CTRL-WEBAUTHN-ASSURANCE, CTRL-INDEPENDENT-APPROVAL-CONTINUATION
**Scenarios:** threat-model-integrity, attack-path-inventory, authorization-resource-boundary, webauthn-challenge-boundary, malformed-api-state-machine, audit-event-attribution, approval-continuation-replay, webauthn-origin-rpid-mismatch, duplicate-operation-flood
**STRIDE:** Spoofing, Tampering, Repudiation, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-13 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-13#security-atlas)

<a id="ap-14"></a>
### AP-14 — Temporary-exception scope and expiry bypass

**Trust boundaries:** browser, control-api, durable-state
**Controls:** CTRL-TEMPORARY-EXCEPTION-SCOPE, CTRL-OPA-FAIL-CLOSED
**Scenarios:** policy-readiness, threat-model-integrity, attack-path-inventory, temporary-exception-scope-bypass
**STRIDE:** Tampering, Elevation of Privilege

| Suite | Runtime SHA | Automation class | Automated result | Qualification | Human decision | Findings | Report |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a.md) |
| standard | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113752Z-66ed279c01-assurance-b798f7e3a4c64b8b8c780a6c737b9e23.md) |
| adversarial | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PASS | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T113934Z-66ed279c01-assurance-de72eb1604ed4b619c498bb2bc40e8b3.md) |
| deep | 66ed279c01 | HUMAN_REVIEW_REQUIRED | PASS | PARTIAL | HUMAN_REVIEW_REQUIRED | none | [open](reports/security-assurance-20260917T115107Z-66ed279c01-assurance-3d7968589ce447f18454d1caf69a10e3.md) |

[Open AP-14 in Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-14#security-atlas)

## Controls

| Control | Boundaries | APs | Scenarios | Model posture |
| --- | --- | --- | --- | --- |
| CTRL-API-CONTROL | — | AP-01, AP-02, AP-03, AP-04, AP-07, AP-08, AP-11 | harness-default-off, harness-auth-boundary, caddy-proof-strip, runtime-readiness, control-plane-ownership, source-boundaries, adversarial-negative-auth-probes, browser-origin-control-plane-bypass, cross-origin-session-abuse, csrf-protected-mutation, authorization-resource-boundary, websocket-auth-boundary, browser-network-egress-contract, service-worker-version-integrity, tailnet-service-exposure, proxy-header-trust-confusion, malformed-api-state-machine, device-invite-replay-and-misbinding, nats-command-replay-integrity, worker-reconnect-command-integrity, tls-identity-drift, audit-event-attribution, recovery-object-authorization, app-install-authority-boundary, remote-access-truthfulness, rate-limit-and-admission-resilience, slow-client-resource-exhaustion, unicode-log-and-ui-injection, backup-confidentiality-integrity, restore-transaction-integrity, android-termux-host-hardening, runtime-env-secret-boundary, hidden-route-and-debug-surface, duplicate-operation-flood | source-derived-or-referenced |
| CTRL-BROWSER-NATS | — | AP-01 | browser-origin-control-plane-bypass, browser-network-egress-contract | source-derived-or-referenced |
| CTRL-BROWSER-SHELL | — | AP-02 | browser-origin-control-plane-bypass | source-derived-or-referenced |
| CTRL-ENTERPRISE-ROLE-FINAL-OWNER | control-api, durable-state | AP-10 | authorization-resource-boundary | mitigation-source-derived |
| CTRL-EVIDENCE-SANITIZE | — | AP-05, AP-06, AP-08 | harness-default-off, evidence-redaction, security-projection, source-boundaries, threat-model-integrity, attack-path-inventory, pwa-offline-secret-retention, audit-event-attribution, security-evidence-poisoning, unicode-log-and-ui-injection, backup-confidentiality-integrity, runtime-env-secret-boundary | source-derived-or-referenced |
| CTRL-EXECUTION-OWNERS | — | AP-03, AP-04, AP-07 | harness-auth-boundary, control-plane-ownership, security-projection, source-boundaries, adversarial-negative-auth-probes, tailnet-service-exposure, malformed-api-state-machine, device-invite-replay-and-misbinding, nats-command-replay-integrity, worker-reconnect-command-integrity, app-install-authority-boundary, remote-access-truthfulness, rate-limit-and-admission-resilience, android-termux-host-hardening, duplicate-operation-flood | source-derived-or-referenced |
| CTRL-EXPLICIT-PROMOTION | — | AP-05, AP-06, AP-08 | recovery-object-authorization, release-artifact-tamper, security-evidence-poisoning, backup-confidentiality-integrity, restore-transaction-integrity, app-package-provenance | source-derived-or-referenced |
| CTRL-HUMAN-SESSION-CSRF | — | AP-09 | cross-origin-session-abuse, csrf-protected-mutation, owner-session-lifecycle, websocket-auth-boundary, pwa-offline-secret-retention, service-worker-version-integrity, proxy-header-trust-confusion, unicode-log-and-ui-injection, cookie-security-posture | source-derived-or-referenced |
| CTRL-INDEPENDENT-APPROVAL-CONTINUATION | browser, control-api, durable-state | AP-13 | malformed-api-state-machine, approval-continuation-replay, duplicate-operation-flood | mitigation-source-derived |
| CTRL-OPA-FAIL-CLOSED | — | AP-11, AP-12, AP-14 | csrf-protected-mutation, authorization-resource-boundary, malformed-api-state-machine, rate-limit-and-admission-resilience, temporary-exception-scope-bypass, policy-known-good-recovery | source-derived-or-referenced |
| CTRL-POLICY-REVISION-LIFECYCLE | control-api, durable-state, server-host | AP-12 | policy-readiness, policy-known-good-recovery | mitigation-source-derived |
| CTRL-SUPPLY-CHAIN | — | AP-05 | service-worker-version-integrity, release-artifact-tamper, dependency-confusion-and-lock-integrity, app-package-provenance | source-derived-or-referenced |
| CTRL-TEMPORARY-EXCEPTION-SCOPE | browser, control-api, durable-state | AP-14 | temporary-exception-scope-bypass | mitigation-source-derived |
| CTRL-WEBAUTHN-ASSURANCE | browser, control-api, durable-state | AP-09, AP-10, AP-13 | owner-session-lifecycle, webauthn-challenge-boundary, approval-continuation-replay, webauthn-origin-rpid-mismatch | mitigation-source-derived |
