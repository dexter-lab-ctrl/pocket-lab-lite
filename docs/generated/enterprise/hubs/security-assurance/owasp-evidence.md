---
title: "OWASP: Model vs Qualification Evidence"
description: "Secondary OWASP mapping with explicit evidence and uncertainty."
generated: true
audience: development
page_type: reference
confidence: generated
---

# OWASP: Model vs Qualification Evidence

OWASP Top 10 is a secondary classification lens. TESTED appears only with applicable registered scenario evidence. NOT_ASSESSED and human-review-only gaps are never promoted to PASS.

| OWASP | Evidence state | APs | Scenarios | Latest evidence | Truth boundary |
| --- | --- | --- | --- | --- | --- |
| A01 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, control-plane-ownership, harness-auth-boundary, harness-default-off, policy-readiness, source-boundaries | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A02 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | attack-path-inventory, evidence-redaction, source-boundaries | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A03 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-09, AP-10 | adversarial-negative-auth-probes | adversarial:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A05 | TESTED | AP-01, AP-02, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-11, AP-12 | caddy-proof-strip, evidence-redaction, runtime-readiness, security-projection, source-boundaries | adversarial:PASS, deep:PARTIAL, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A06 | TESTED | AP-04, AP-05, AP-06, AP-08 | security-projection | deep:PARTIAL, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A07 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | adversarial-negative-auth-probes, attack-path-inventory, caddy-proof-strip, harness-auth-boundary, harness-default-off | adversarial:PASS, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A08 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | attack-path-inventory, control-plane-ownership, evidence-redaction, policy-readiness, security-projection, source-boundaries, threat-model-integrity | adversarial:PASS, deep:PARTIAL, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
| A09 | TESTED | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | attack-path-inventory, control-plane-ownership, evidence-redaction, security-projection, threat-model-integrity | adversarial:PASS, deep:PARTIAL, deep:PASS, smoke:PASS, standard:PASS | EVIDENCE_PRESENT does not mean every possible weakness was tested. |
