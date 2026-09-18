---
title: "STRIDE: Model vs Qualification Evidence"
description: "STRIDE threats beside bounded qualification evidence without a security score."
generated: true
audience: development
page_type: reference
confidence: generated
---

# STRIDE: Model vs Qualification Evidence

STRIDE is a modeling lens. Qualification status is evidence for registered invariants. This page intentionally does not compute a security score.

| STRIDE category | Modeled APs | Registered scenarios | Latest automated evidence | Interpretation |
| --- | --- | --- | --- | --- |
| Denial of Service | AP-04, AP-07, AP-08, AP-11, AP-12 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, control-plane-ownership, evidence-redaction, harness-auth-boundary, policy-readiness, runtime-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
| Elevation of Privilege | AP-01, AP-02, AP-03, AP-05, AP-09, AP-10, AP-11, AP-13, AP-14 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, control-plane-ownership, evidence-redaction, harness-auth-boundary, harness-default-off, policy-readiness, runtime-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
| Information Disclosure | AP-05, AP-06, AP-07 | attack-path-inventory, caddy-proof-strip, control-plane-ownership, evidence-redaction, runtime-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
| Repudiation | AP-04, AP-06, AP-08, AP-10, AP-12, AP-13 | adversarial-negative-auth-probes, attack-path-inventory, control-plane-ownership, evidence-redaction, harness-auth-boundary, policy-readiness, runtime-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
| Spoofing | AP-01, AP-03, AP-07, AP-09, AP-13 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, control-plane-ownership, harness-auth-boundary, harness-default-off, runtime-readiness, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
| Tampering | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, control-plane-ownership, evidence-redaction, harness-auth-boundary, harness-default-off, policy-readiness, runtime-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | Human review remains separate where required. |
