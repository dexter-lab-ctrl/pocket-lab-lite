---
title: "Scenario Walkthroughs"
description: "Model-to-assurance walkthroughs for representative attack paths."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Scenario Walkthroughs

These use existing canonical IDs and latest published evidence. PASS is bounded to the exact qualification; it is not permanent proof.

<a id="ap-01"></a>
## AP-01 — Browser control-plane bypass

**Model path:** browser → nats-jetstream → worker

**Boundaries:** browser, messaging-execution

**Controls:** CTRL-BROWSER-NATS, CTRL-API-CONTROL

**Assurance scenarios:** harness-default-off, harness-auth-boundary, caddy-proof-strip, control-plane-ownership, source-boundaries, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, browser-origin-control-plane-bypass, cross-origin-session-abuse, websocket-auth-boundary, browser-network-egress-contract, proxy-header-trust-confusion, app-install-authority-boundary, runtime-env-secret-boundary, hidden-route-and-debug-surface

| Suite | Automation classification | Automated result | Qualification result | Runtime SHA | Human assurance decision | Findings |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| standard | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| adversarial | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| deep | PARTIALLY_EXECUTABLE | PASS | PARTIAL | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |

[Open AP-01 in the Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-01#security-atlas) · [Open full correlation](model-assurance-evidence.md#ap-01)

<a id="ap-02"></a>
## AP-02 — Browser shell execution

**Model path:** browser → lite-api → server-host

**Boundaries:** browser, control-api, server-host

**Controls:** CTRL-BROWSER-SHELL, CTRL-API-CONTROL

**Assurance scenarios:** harness-default-off, harness-auth-boundary, caddy-proof-strip, control-plane-ownership, source-boundaries, adversarial-negative-auth-probes, threat-model-integrity, attack-path-inventory, browser-origin-control-plane-bypass, android-termux-host-hardening

| Suite | Automation classification | Automated result | Qualification result | Runtime SHA | Human assurance decision | Findings |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| standard | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| adversarial | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| deep | EXECUTABLE_NOW | PASS | PARTIAL | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |

[Open AP-02 in the Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-02#security-atlas) · [Open full correlation](model-assurance-evidence.md#ap-02)

<a id="ap-06"></a>
## AP-06 — Evidence poisoning

**Model path:** scanner-evidence → promoted-evidence → documentation

**Boundaries:** external-release, durable-state, server-host

**Controls:** CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION

**Assurance scenarios:** control-plane-ownership, evidence-redaction, security-projection, threat-model-integrity, attack-path-inventory, pwa-offline-secret-retention, audit-event-attribution, security-evidence-poisoning, unicode-log-and-ui-injection, runtime-env-secret-boundary

| Suite | Automation classification | Automated result | Qualification result | Runtime SHA | Human assurance decision | Findings |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | assurance-2a29076a8244411daed1b0a5ca0c1d1a-15deb392776f0f7b27d15fb1 |
| standard | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | assurance-b798f7e3a4c64b8b8c780a6c737b9e23-15deb392776f0f7b27d15fb1 |
| adversarial | EXECUTABLE_NOW | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| deep | EXECUTABLE_NOW | PASS | PARTIAL | 66ed279c01 | HUMAN_REVIEW_REQUIRED | assurance-3d7968589ce447f18454d1caf69a10e3-15deb392776f0f7b27d15fb1 |

[Open AP-06 in the Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-06#security-atlas) · [Open full correlation](model-assurance-evidence.md#ap-06)

<a id="ap-11"></a>
## AP-11 — OPA authorization decision integrity failure

**Model path:** browser → caddy → lite-api

**Boundaries:** browser, control-api

**Controls:** CTRL-API-CONTROL, CTRL-OPA-FAIL-CLOSED

**Assurance scenarios:** runtime-readiness, policy-readiness, threat-model-integrity, attack-path-inventory, csrf-protected-mutation, authorization-resource-boundary, malformed-api-state-machine, recovery-object-authorization, app-install-authority-boundary, rate-limit-and-admission-resilience, slow-client-resource-exhaustion, policy-known-good-recovery

| Suite | Automation classification | Automated result | Qualification result | Runtime SHA | Human assurance decision | Findings |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| standard | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| adversarial | PARTIALLY_EXECUTABLE | PASS | PASS | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |
| deep | PARTIALLY_EXECUTABLE | PASS | PARTIAL | 66ed279c01 | HUMAN_REVIEW_REQUIRED | none |

[Open AP-11 in the Security Atlas](../../threat-model/catalog.md?atlas-attack-path=AP-11#security-atlas) · [Open full correlation](model-assurance-evidence.md#ap-11)

