# Findings and remediation playbook

The harness reports normalized, sanitized findings rather than raw scanner
transcripts. A scanner observation is evidence for review; it is not by itself
proof that a vulnerability is exploitable.

## Finding record

The current report model carries, where applicable:

`finding_id`, `run_id`, `suite`, `scenario_id`, `tool`, `tool_version`,
`category`, `severity`, `confidence`, `title`, `safe_summary`, `component`,
`asset`, `trust_boundary`, `stride`, `owasp`, `attack_paths`, `controls`,
`cwe`, `cve`, `sanitized_file_reference`, `runtime_target`, timestamps,
`baseline_state`, `status`, `remediation`, and `evidence_refs`.

Raw secrets, credentials, authorization material, user media, and unrestricted
scanner output are excluded. A deliberately removed value is represented as
`[REDACTED BY SECURITY ASSURANCE POLICY]`.

## Severity and delta

Review findings in this order:

| Severity | Review expectation |
| --- | --- |
| Critical | Stop qualification and escalate immediately. Do not accept automatically. |
| High | Reproduce and remediate or obtain explicit security-owner disposition before release review. |
| Medium | Triage, correlate, and either fix or document bounded residual risk. |
| Low | Track and address according to maintenance policy. |
| Info | Preserve as posture or review context; do not inflate into a defect. |

Delta states are `NEW`, `EXISTING`, `RESOLVED`, `REGRESSED`, and `UNCHANGED`.
Compare only compatible revisions, suite definitions, registry hashes, and
runtime identities. A finding that appears in multiple SCA tools is normally
one normalized advisory with corroborating tool references, not several
independent defects.

## Triage distinctions

Record which explanation applies:

- `TRUE_POSITIVE`: the evidence demonstrates a real source, runtime,
  dependency, or configuration defect.
- `FALSE_POSITIVE`: the rule does not apply after checking the code and fixed
  target; preserve the reasoning and tool evidence reference.
- `TEST_ONLY`: the finding exists only in an isolated fixture or test path and
  is not reachable from the deployed surface.
- `NOT_REACHABLE`: the pattern exists, but the registered trust-boundary and
  runtime path cannot reach it.
- `HUMAN_REVIEW_REQUIRED`: the question requires a human ceremony or policy
  decision, not a missing automated scanner.

## Remediation loop

Use this sequence for every genuine defect:

```text
finding
  -> confirm sanitized evidence
  -> reproduce with the fixed registered command/scenario
  -> classify source, runtime, configuration, dependency, or tooling issue
  -> patch and add a regression test on the DEV PC
  -> run focused validation
  -> publish the exact DEV PC SHA
  -> Server Phone consumes that SHA
  -> rerun the failed scenario/tool
  -> rerun the affected suite
  -> compare against the approved baseline
```

The Server Phone is a consumer/qualification target, never the development
workspace. Reviewers must not edit tracked source or apply fixes there.

## Inspect and compare

Use `[DEV PC]` with an already authenticated run ID:

```bash
task lite:security:assurance:report RUN_ID=<run-id>
task lite:security:assurance:compare RUN_ID=<run-id>
```

The run's report and evidence references identify the exact target and
registry/revision binding. Use the fixed tool manager only for the supported
registered suite:

```bash
task lite:security:assurance:tools:run SUITE=standard
```

Do not substitute an arbitrary command, binary, path, scanner flag, target,
template, or environment variable.

## Retest record

For each fix, retain a before/after entry containing:

1. finding ID, severity, confidence, STRIDE, OWASP, AP-* mapping, and
   component;
2. sanitized reproduction command and observed Pocket Lab response;
3. root cause and changed DEV-PC source files;
4. regression test and exact validation command;
5. published SHA consumed by the Server Phone;
6. retest command, result, tool evidence, and residual risk.

Do not claim `RESOLVED` until the compatible runtime or static check has been
rerun at the fixed revision. If a prerequisite prevents the retest, use
`BLOCKED` or `UNVALIDATED`, not a passing finding state.

## Baseline hygiene

Baselines are approved evidence, not a mechanism to hide new findings. Keep
the source revision, runtime identity, suite/profile, tool versions, and
sanitization status with the baseline. A new High or Critical finding must be
visible in the summary even when it is also present in a previous baseline.
