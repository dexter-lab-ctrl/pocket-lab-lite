# Result-status reference

Status is attached to the correct layer. A tool launch, scenario invariant,
and aggregate qualification can have different outcomes.

| Status | Meaning | Use when |
| --- | --- | --- |
| `PASS` | The registered unit ran, its expected invariant held, and evidence is complete and sanitized. | Tool, scenario, fault invariant, or suite is proven. |
| `FAIL` | The registered unit ran and an expected invariant or policy threshold did not hold. | A real control failure or disqualifying finding is observed. |
| `PARTIAL` | Some bounded work/evidence completed, but interruption, resource stop, parser loss, or incomplete coverage prevents a complete result. | Never silently promote to PASS. |
| `BLOCKED` | A precondition or infrastructure gate prevented safe execution. | Readiness, qualification, policy, resource, or target admission failed before proof. |
| `CANCELLED` | An authorized cancellation stopped the run and preserved its terminal evidence. | Only when supported by the current status model. |
| `MISSING` | Required tool, receipt, artifact, or implementation is absent. | The requested unit cannot be attempted safely. |
| `UNSUPPORTED` | The current platform or implementation cannot safely provide the registered unit. | Record exact technical limitation. |
| `NOT_APPLICABLE` | The question does not apply to this revision/surface. | Example: no registered signed artifact for Cosign. |
| `HUMAN_REVIEW_REQUIRED` | The threat/control is modeled and documented, but a human ceremony or governance decision is required. | WebAuthn, Owner, Enterprise, exception, or protected-secret review. |
| `STATIC_EVIDENCE_ONLY` | Source, dependency, configuration, or provenance evidence exists without live runtime proof. | Static lane or an out-of-scope runtime path. |

## Result layers

| Layer | What determines status |
| --- | --- |
| Tool execution | discovery, fixed command exit, parser, timeout, receipt, and sanitization |
| Scenario | expected invariant, control decision, evidence and mapped threat |
| Suite | all required scenarios/tools, policy thresholds, resource/deadline state |
| Fault invariant | service restoration/fail-closed behavior, independent of an intentionally denied probe |
| Aggregate qualification | preflight, selected suites, findings, coverage, cleanup, and human-review limits |
| Finding | severity/confidence, normalized identity, baseline delta, and remediation state |

`FAIL` is not the same as “the scanner found a vulnerability”: a finding can
be normalized while the tool execution itself is PASS. Conversely, successful
process launch without a valid invariant is not PASS. A suite can be `PARTIAL`
because a safe tool was unavailable while a completed scenario remains PASS.

## Reporting rule

Every report must explain what was tested, what was not tested, why a unit was
blocked/unsupported/not applicable, and which evidence supports the status.
Use the exact marker `[REDACTED BY SECURITY ASSURANCE POLICY]` for deliberately
removed sensitive values; never replace a missing measurement with zero.
