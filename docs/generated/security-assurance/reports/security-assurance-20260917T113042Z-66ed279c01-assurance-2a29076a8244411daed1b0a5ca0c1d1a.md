# Security Assurance Report — assurance-2a29076a8244411daed1b0a5ca0c1d1a

!!! info "Assurance evidence, not certification"
    This report summarizes bounded Security Assurance evidence. It does not claim that Pocket Lab Lite is certified or universally secure.

## How to Read This Report

This document represents **one specific Security Assurance qualification**. Status, version, finding, coverage, and baseline terms describe evidence in that qualification unless the report explicitly says otherwise.

| Term | Meaning | Does NOT mean |
| --- | --- | --- |
| PASS | The registered check or scenario executed and met its required invariant for this qualification. | The whole product is secure or certified. |
| PARTIAL | Valid evidence was produced, but coverage or the resulting condition is incomplete. | A complete failure or an automatic exploit. |
| FAIL | The registered invariant executed and was not satisfied. | The issue is automatically exploitable without review. |
| BLOCKED | The harness intentionally could not proceed because a safety, admission, resource, dependency, or prerequisite condition prevented execution. | The underlying security control necessarily failed. |
| CANCELLED | The qualification or run was intentionally terminated before completion. | PASS or FAIL. |
| NOT_RUN | The registered suite or tool was not executed as part of this specific qualification. | Broken, unsupported, failed, or a clean scan with zero findings. |
| DEFERRED | Execution is intentionally postponed because the applicable prerequisite or safe executor is not currently available. | PASS. |
| UNAVAILABLE | This particular metadata value was not present in the normalized evidence used by this report. | The whole tool or service was unavailable. |
| NOT_APPLICABLE | The check does not apply to this target, profile, or qualification context. | An applicable control was tested and passed. |
| HUMAN_REVIEW_REQUIRED | The assurance decision requires a human-governed ceremony or contextual review. | Automated PASS. |
| EVIDENCE_PRESENT | Applicable evidence exists for the category. | Every possible weakness in the category was tested. |
| NOT_ASSESSED | No applicable automated evidence was produced for the category. | PASS. |
| NEW | A current finding has no matching finding in the selected baseline. | The current code change necessarily introduced it. |
| EXISTING | The finding matches the selected baseline. | The risk has been accepted or is safe. |
| REGRESSED | Baseline comparison indicates that a known condition became materially worse. | Automatic exploitability. |
| RESOLVED | A prior baseline finding is absent according to the comparison rules. | The condition can never recur. |
| UNCHANGED | The current finding materially matches the prior baseline. | The finding is safe or accepted. |
| runtime-reported | The registry intentionally delegates the tool version to runtime or service evidence instead of pinning a numeric version. | The tool is unversioned or unknown by design. |
| Registered version | The expected version or version policy declared by the hash-matched security/assurance/tools.yaml used by the qualification. | Proof that the same version actually executed. |
| Observed version | The version captured from this qualification's normalized runtime or tool receipt. | The repository's required or pinned version. |
| MATCH | A fixed registered version and an observed version are both present and match after normalization. | A security result by itself. |
| MISMATCH | A fixed registered version and an observed version are both present but do not match. | Automatic exploitability; it is a qualification integrity issue requiring review. |
| NOT_OBSERVED | A fixed registered version exists, but this qualification has no observed version for the tool. | The tool failed; it may simply be NOT_RUN. |
| RUNTIME_VERSION_NOT_CAPTURED | The registry requires runtime-reported version evidence, but this qualification did not capture a usable version value. | The tool itself did not run when run status says otherwise. |
| 0 findings | No normalized findings are associated with the relevant executed evidence set. | A NOT_RUN tool performed a clean scan. |
| Finding | Sanitized normalized security evidence that requires interpretation in context. | A demonstrated exploit. |
| Scenario | A registered Pocket Lab security invariant being assessed. | A scanner product. |
| Tool | A registered evidence source used by a scenario or suite. | The security requirement itself. |
| Scenario coverage | The percentage of registered applicable scenarios with terminal evidence under the report formula. | A security score. |
| Attack-path coverage | The percentage of registered attack paths with applicable non-human-only evidence under the report formula. | The percentage of all real-world attacks prevented. |
| Tool readiness | PASS tools divided by applicable tools that actually participated in the metric; NOT_RUN and DEFERRED are excluded. | The percentage of all registered tools installed everywhere. |
| Sanitized evidence | Evidence normalized and filtered by Pocket Lab publication rules before report generation. | Raw scanner output. |
| Source SHA / Runtime SHA | The exact code revision represented by the qualification evidence. | A later report-publication commit unless it is explicitly the same revision. |

> **Per-qualification scope:** `NOT_RUN` means the registered suite or tool did not execute in this qualification. Another suite may have separate qualification evidence.

> **Zero findings:** `0` findings on a `NOT_RUN` tool does not mean the tool scanned and found nothing; it means this qualification has no normalized findings from an execution that did not occur.

> **Version provenance:** **Registered version** is the expected pin/policy from the hash-matched tool registry; **Observed version** is what this qualification actually captured. They are intentionally separate.

## 1. Executive Security Summary

**What was tested:** the registered **smoke** suite against **local_server_host_only** using the fixed harness and registered toolchain.

**Overall result:** **PASS**. The run recorded 8 scenario results and 1 sanitized normalized findings.

**What needs attention:** Critical/High findings and any FAIL/PARTIAL/BLOCKED scenarios remain visible below. Human-only controls are not converted into PASS by absence of scanner findings.

**Out of scope:** destructive Recovery, unrelated network targets, user media, credential attacks, and arbitrary command execution.

## 2. Qualification Identity

| Field | Value |
| --- | --- |
| Qualification ID | assurance-2a29076a8244411daed1b0a5ca0c1d1a |
| Report ID | security-assurance-20260917T113042Z-66ed279c01-assurance-2a29076a8244411daed1b0a5ca0c1d1a |
| Generation timestamp UTC | 2026-09-17T11:30:50.855600Z |
| Source SHA | 66ed279c018d45cd9b2e577921b9cfc13ca7457f |
| Runtime SHA | 66ed279c018d45cd9b2e577921b9cfc13ca7457f |
| Environment | qualification |
| Target scope | local_server_host_only |
| Profile | security-assurance-runner |
| Suite | smoke |
| Tool registry hash | sha256:38755b7f13c94ff9a37a0eccf4324455d7f05fcddc9c7dfa1b85f3fb8c657687 |
| Scenario registry hash | sha256:92310371d7c8ed9b2ff686ddb6116b471e3ba3c261988d3a66b65c15c68afbc1 |
| Suite registry hash | sha256:407d1c893f8de7579f0fd3193e262da5b8f67c612bcb9d2c76308c3f36afd164 |
| Threat-model hash | sha256:74442eb35bcd488a67b5fc995ca1d6f6f341343bb3f8c3a0663cb89e241a908c |

## 3. Overall Assurance Verdict

**PASS** — this is the harness-native terminal result; no separate security score overrides it.

## 4. Security Confidence / Assurance Metrics

| Metric | Value |
| --- | --- |
| Scenario Coverage Percent | 100.0 |
| Scenario Pass Percent | 100.0 |
| Attack Path Coverage Percent | 71.4 |
| Control Coverage Percent | 100.0 |
| Tool Readiness Percent | 100.0 |
| Evidence Completeness Percent | 100.0 |

Formula: each percentage is completed applicable evidence units divided by registered applicable units; missing/blocked units are never treated as passing

## 5. Finding Counts

| Class | Count |
| --- | --- |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |
| Info | 0 |
| NEW | 1 |
| EXISTING | 0 |
| REGRESSED | 0 |
| RESOLVED | 0 |
| UNCHANGED | 0 |

## 6. Severity Chart

```mermaid
pie showData
    title Sanitized findings by severity
    "Critical" : 0
    "High" : 0
    "Medium" : 0
    "Low" : 1
    "Info" : 0
```

| Severity | Findings |
| --- | --- |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |
| Info | 0 |

## 7. Findings by Tool

| Tool | Finding count |
| --- | --- |
| trivy | 1 |

## 8. Findings by Suite

| Suite | Result |
| --- | --- |
| smoke | PASS |
| standard | NOT_RUN |
| adversarial | NOT_RUN |
| deep | NOT_RUN |

## 9. Complete Finding Register


### assurance-2a29076a8244411daed1b0a5ca0c1d1a-15deb392776f0f7b27d15fb1

| Field | Value |
| --- | --- |
| Severity | low |
| Status | open |
| Baseline | NEW |
| Tool | trivy |
| Scenario | security-projection |
| Rule ID | protected_runtime_secret |
| CVE |  |
| CWE |  |
| Package/component | Pocket Lab Lite |
| Asset | gitea/conf/app.runtime.ini |
| Title | Registered Security finding |
| Summary | Protected backend runtime secret found. |
| Security impact | Requires review in context |
| Evidence summary | security/evidence/security-7f47c76330204ff79378253ab8a54396/summary.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/lynis-normalized.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/sbom.cdx.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/trivy-normalized.json, security/evidence/security-7f47c76330204ff79378253ab8a54396/coverage-summary.json |
| STRIDE | Information Disclosure |
| OWASP | A02, A05 |
| AP path | AP-06 |
| Control | CTRL-EVIDENCE-SANITIZE |
| Remediation | Keep this server-side config locked down, exclude it from frontend assets and normal evidence, and rotate it during planned maintenance if exposure is suspected. |
| Retest guidance | Re-run scenario security-projection in suite smoke after remediation. |

## 10. STRIDE Matrix

| Threat | Scenarios | Passed | Failed | Partial | Blocked | Scenario IDs |
| --- | --- | --- | --- | --- | --- | --- |
| Denial of Service | 2 | 2 | 0 | 0 | 0 | runtime-readiness, security-projection |
| Elevation of Privilege | 4 | 4 | 0 | 0 | 0 | harness-default-off, harness-auth-boundary, caddy-proof-strip, control-plane-ownership |
| Information Disclosure | 3 | 3 | 0 | 0 | 0 | runtime-readiness, evidence-redaction, security-projection |
| Repudiation | 4 | 4 | 0 | 0 | 0 | control-plane-ownership, evidence-redaction, security-projection, threat-model-integrity |
| Spoofing | 3 | 3 | 0 | 0 | 0 | harness-default-off, harness-auth-boundary, caddy-proof-strip |
| Tampering | 6 | 6 | 0 | 0 | 0 | harness-auth-boundary, caddy-proof-strip, control-plane-ownership, evidence-redaction, security-projection, threat-model-integrity |

## 11. OWASP Top 10 Matrix

| Category | Applicability | Scenarios | Passing | Result |
| --- | --- | --- | --- | --- |
| A01 Broken Access Control | TESTED | 4 | 4 | EVIDENCE_PRESENT |
| A02 Cryptographic Failures | TESTED | 1 | 1 | EVIDENCE_PRESENT |
| A03 Injection | HUMAN_REVIEW_REQUIRED | 0 | 0 | NOT_ASSESSED |
| A04 Insecure Design | HUMAN_REVIEW_REQUIRED | 0 | 0 | NOT_ASSESSED |
| A05 Security Misconfiguration | TESTED | 4 | 4 | EVIDENCE_PRESENT |
| A06 Vulnerable and Outdated Components | TESTED | 1 | 1 | EVIDENCE_PRESENT |
| A07 Identification and Authentication Failures | TESTED | 3 | 3 | EVIDENCE_PRESENT |
| A08 Software and Data Integrity Failures | TESTED | 4 | 4 | EVIDENCE_PRESENT |
| A09 Security Logging and Monitoring Failures | TESTED | 4 | 4 | EVIDENCE_PRESENT |
| A10 Server-Side Request Forgery | HUMAN_REVIEW_REQUIRED | 0 | 0 | NOT_ASSESSED |

## 12. Attack-Path Matrix

| AP | Threat | Assets/path | Trust boundaries | Controls | Execution | Result |
| --- | --- | --- | --- | --- | --- | --- |
| AP-01 | Browser control-plane bypass | browser, nats-jetstream, worker | browser, messaging-execution | CTRL-BROWSER-NATS, CTRL-API-CONTROL | PARTIALLY_EXECUTABLE | PASS |
| AP-02 | Browser shell execution | browser, lite-api, server-host | browser, control-api, server-host | CTRL-BROWSER-SHELL, CTRL-API-CONTROL | EXECUTABLE_NOW | PASS |
| AP-03 | Forged managed-device identity | managed-device, lite-api, nats-jetstream, node-agent | managed-device, control-api, messaging-execution | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | STATIC_EVIDENCE_ONLY | PASS |
| AP-04 | Messaging command tampering or replay | lite-api, nats-jetstream, worker, node-agent | control-api, messaging-execution, managed-device | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | PARTIALLY_EXECUTABLE | PASS |
| AP-05 | Supply-chain artifact compromise | github-release, release-artifacts, server-host | external-release, server-host, application-container | CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION, CTRL-EVIDENCE-SANITIZE | STATIC_EVIDENCE_ONLY | PASS |
| AP-06 | Evidence poisoning | scanner-evidence, promoted-evidence, documentation | external-release, durable-state, server-host | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION | EXECUTABLE_NOW | PASS |
| AP-07 | Tailnet/private-network exposure | private-network, tailscale, caddy, lite-api | private-network, control-api, server-host | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | PARTIALLY_EXECUTABLE | PASS |
| AP-08 | Recovery state tampering | sqlite, recovery-state, lite-api | durable-state, control-api | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL | STATIC_EVIDENCE_ONLY | PASS |
| AP-09 | Human identity and WebAuthn assurance misuse | browser, caddy, lite-api, sqlite | browser, control-api, durable-state | CTRL-HUMAN-SESSION-CSRF, CTRL-WEBAUTHN-ASSURANCE | HUMAN_REVIEW_REQUIRED | PASS |
| AP-10 | Enterprise membership and final-Owner privilege escalation | browser, caddy, lite-api, sqlite | browser, control-api, durable-state | CTRL-WEBAUTHN-ASSURANCE, CTRL-ENTERPRISE-ROLE-FINAL-OWNER | HUMAN_REVIEW_REQUIRED | PASS |
| AP-11 | OPA authorization decision integrity failure | browser, caddy, lite-api | browser, control-api | CTRL-API-CONTROL, CTRL-OPA-FAIL-CLOSED | PARTIALLY_EXECUTABLE | PASS |
| AP-12 | Policy revision activation and recovery integrity | browser, caddy, lite-api, sqlite | browser, control-api, durable-state | CTRL-POLICY-REVISION-LIFECYCLE, CTRL-OPA-FAIL-CLOSED | STATIC_EVIDENCE_ONLY | PASS |
| AP-13 | Approval and continuation integrity | browser, caddy, lite-api, sqlite | browser, control-api, durable-state | CTRL-WEBAUTHN-ASSURANCE, CTRL-INDEPENDENT-APPROVAL-CONTINUATION | HUMAN_REVIEW_REQUIRED | PASS |
| AP-14 | Temporary-exception scope and expiry bypass | browser, caddy, lite-api, sqlite | browser, control-api, durable-state | CTRL-TEMPORARY-EXCEPTION-SCOPE, CTRL-OPA-FAIL-CLOSED | HUMAN_REVIEW_REQUIRED | PASS |

## 13. Toolchain Matrix

Registered version metadata is loaded only from the `security/assurance/tools.yaml` whose SHA-256 matches the tool-registry hash recorded by this qualification. A registry pin is never substituted for missing observed runtime evidence.

| Tool | Registered version | Observed version | Version state | Version source | Lane | Run status | Findings | Duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pocketlab-security | runtime-reported | UNAVAILABLE | RUNTIME_VERSION_NOT_CAPTURED | repository_revision | server_phone_worker | PASS | 0 | 318491 |
| trivy | runtime-reported | dev | RUNTIME_REPORTED | registered_security_tool_result | server_phone_worker | PASS | 1 | UNAVAILABLE |
| lynis | runtime-reported | 3.1.6 | RUNTIME_REPORTED | registered_security_tool_result | server_phone_worker | PASS | 0 | UNAVAILABLE |
| gitleaks | 8.30.1 | NOT_RUN | NOT_OBSERVED | qualified_tool_receipt | dev_pc_static | NOT_RUN | 0 | UNAVAILABLE |
| opa | runtime-reported | UNAVAILABLE | RUNTIME_VERSION_NOT_CAPTURED | policy_status | server_phone_worker | PASS | 0 | UNAVAILABLE |

## 14. Runtime / Resource Metrics

| Metric | Value |
| --- | --- |
| Duration ms | 370294 |
| Available memory | 2573426688 |
| Battery percent | 95.0 |
| Temperature C | 38.5 |
| Free storage | 136401416192 |
| System load ratio | UNAVAILABLE |
| Retries | UNAVAILABLE |
| Checkpoint/resume | UNAVAILABLE |

## 15. Security Architecture

```mermaid
flowchart LR
  Client[Approved client] --> Harness[Key-bound harness]
  Harness --> API[FastAPI]
  API --> NATS[NATS / JetStream]
  NATS --> Worker[Worker]
  Worker --> Runtime[Registered runtime scenarios / scanners]
  DevStatic[DEV-PC static lane] --> Evidence[Sanitized normalized evidence]
  DevLive[DEV-PC live-runtime lane] --> Evidence
  Runtime --> Evidence
  Evidence --> Report[MkDocs Security Assurance report]
```

## 16. Trust Boundaries

Browser/Caddy; Caddy/FastAPI; machine/harness; FastAPI/OPA; FastAPI/NATS; NATS/worker; worker/scanner; scanner/evidence; and DEV PC/Server Phone are explicit review boundaries.

## 17. Controls Validated

| Control | Scenarios | Attack paths | Result |
| --- | --- | --- | --- |
| CTRL-API-CONTROL | harness-default-off, harness-auth-boundary, caddy-proof-strip, runtime-readiness, control-plane-ownership | AP-01, AP-02, AP-03, AP-04, AP-06, AP-07, AP-09, AP-10, AP-11, AP-12 | PASS |
| CTRL-EVIDENCE-SANITIZE | harness-default-off, evidence-redaction, security-projection, threat-model-integrity | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-09, AP-10, AP-11, AP-12, AP-13, AP-14 | PASS |
| CTRL-EXECUTION-OWNERS | harness-auth-boundary, control-plane-ownership, security-projection | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-08, AP-09, AP-10 | PASS |

## 18. Human Review Required

Physical WebAuthn ceremonies, Enterprise membership/final Owner authority, approval ceremonies, and protected runtime-secret ownership/rotation remain human-governed where applicable.

| AP | Reason |
| --- | --- |
| AP-03 | Managed-device identity forgery is not performed against enrolled device state. |
| AP-05 | Release and dependency controls are represented by existing Security evidence and source checks. |
| AP-08 | Recovery replacement/restore mutation is excluded from normal assurance. |
| AP-09 | Human WebAuthn ceremonies are not impersonated by the synthetic machine principal. |
| AP-10 | Enterprise membership and final-Owner review remain human-governed. |
| AP-12 | Policy revision activation/recovery is not mutated by this safe profile. |
| AP-13 | Independent approval and requester continuation require human review. |
| AP-14 | Temporary exception issuance and expiry bypass are not attempted. |

## 19. Out of Scope

- Destructive production Recovery or restore execution
- Unrelated LAN or Tailnet hosts and public Internet targets
- User media and PhotoPrism media contents
- Credential attacks or password guessing
- Arbitrary shell execution, caller-selected targets, ports, templates, scanner arguments, or NATS subjects

## 20. Remediation Priorities

| Severity | Finding | Remediation |
| --- | --- | --- |
| low | assurance-2a29076a8244411daed1b0a5ca0c1d1a-15deb392776f0f7b27d15fb1 | Keep this server-side config locked down, exclude it from frontend assets and normal evidence, and rotate it during planned maintenance if exposure is suspected. |

## 21. Retest Plan

| Finding | Scenario | Suite | Expected fixed invariant |
| --- | --- | --- | --- |
| assurance-2a29076a8244411daed1b0a5ca0c1d1a-15deb392776f0f7b27d15fb1 | security-projection | smoke | The registered scenario reaches its expected invariant without the finding recurring. |

## 22. Sanitization Statement

This publication contains normalized sanitized evidence only. It excludes: private keys, session tokens, provisioning tokens, passwords, authorization headers, cookies, CSRF tokens, NATS credentials, Tailscale credentials, Recovery encryption material, raw secret matches, user/PhotoPrism media, raw scanner output.

## Historical Trend (bounded)

| Completed | Result | Critical | High | Medium | Scenario coverage % | Comparison |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-16T17:33:02Z | PARTIAL | 0 | 0 | 0 | 100.0 | compatible |
