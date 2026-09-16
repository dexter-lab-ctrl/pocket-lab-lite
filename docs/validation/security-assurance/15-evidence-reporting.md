# Evidence and reporting playbook

Every assurance run produces bounded, sanitized evidence tied to a source
revision, runtime identity, registry hashes, suite, operation correlation,
and result status. The report is an audit record, not a secret transport.

## Report directory

The worker-owned report uses the run-specific evidence root configured by the
runtime. The current artifact set is:

| Artifact | Contents | Review warning |
| --- | --- | --- |
| `manifest.json` | run, source/runtime, suite, registry and correlation identity | no tokens or private keys |
| `environment.json` | bounded platform, readiness and qualification posture | no secret environment values |
| `toolchain.json` | registered tools, versions/statuses, lane and receipts | no raw installer credentials |
| `findings.json` | normalized findings and delta fields | no raw matches or unrestricted output |
| `threat-coverage.json` | STRIDE/scenario/control coverage | incomplete execution stays visible |
| `owasp-coverage.json` | OWASP Top 10 2021 mappings and classifications | uncovered is not PASS |
| `attack-path-results.json` | AP-* classification and evidence references | human-only paths remain human review |
| `controls.json` | exercised control and invariant results | bounded to registered controls |
| `delta.json` | baseline comparison | only compatible baselines |
| `performance.json` | duration and available resource measurements | unavailable metrics remain unavailable |
| `sanitization.json` | redaction policy/version and check result | failure blocks publication |
| `checksums.json` | checksums for report artifacts | validate before preservation |
| `summary.md` | human-readable conclusion, findings, blockers and residual risk | do not treat prose as sole proof |

The DEV-PC tool manager may emit a smaller static/live-lane artifact set. Its
`manifest.json`, `toolchain.json`, `findings.json`, `delta.json`,
`sanitization.json`, and `checksums.json` remain linked to the same
qualification identity when the unified workflow aggregates them.

## Command-by-command record

The qualification dossier should record every command, including failed and
no-finding commands. For each sequence number include:

| Field | Required content |
| --- | --- |
| Identity | sequence, timestamp, qualification/run ID, environment, source/runtime SHA |
| Execution | lane, working-directory classification, tool/version, installation receipt, sanitized argv |
| Target | fixed Pocket Lab target and route/port identity; never an arbitrary target |
| Intent | purpose, safety class, STRIDE, OWASP category, AP-* mapping |
| Outcome | expected result, exit code, duration, tool status, finding count and severity |
| Pocket Lab reaction | HTTP status/reason, operation/run ID, correlation, policy decision, checkpoint, audit/evidence state |
| Output | sanitized stdout/stderr summaries, parser result and redaction result |
| Follow-up | evidence references, remediation, retest command/output, final status |

The command itself must be copied from the current task, CLI, adapter, or
registered API contract. Never paste a provisioning token, session token,
Authorization header, private key, raw signature, secret match, or user-media
content into the dossier.

## Evidence review procedure

1. Verify `manifest.json` matches the reviewed/published source SHA and the
   runtime SHA.
2. Verify the suite and registry hashes before interpreting findings.
3. Validate `checksums.json` and inspect `sanitization.json`.
4. Read `summary.md`, then correlate each conclusion to structured artifacts.
5. For every finding, follow `evidence_refs` to bounded tool/scenario output.
6. Confirm `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or `HUMAN_REVIEW_REQUIRED` is
   supported by the underlying result rather than by process launch alone.
7. Preserve the sanitized report according to repository retention policy.

## MkDocs publication

A completed normalized report can be transformed into a first-class MkDocs
Security Assurance report without reading raw scanner output:

```bash
task lite:security:assurance:report:generate \
  QUALIFICATION_ID=<assurance-run-id>

task lite:security:assurance:report:publish \
  QUALIFICATION_ID=<assurance-run-id>

task lite:security:assurance:report:check \
  QUALIFICATION_ID=<assurance-run-id>
```

The publisher requires a specific terminal qualification ID; there is no
implicit `latest` selection. It reads the existing sanitized report endpoint,
requires the complete normalized artifact set and fail-closed sanitization
markers, enforces bounded file/bundle sizes, stages output in a temporary
directory, applies the existing redaction patterns, and atomically publishes
only after redaction succeeds.

Published files live under:

```text
docs/generated/security-assurance/reports/
```

Each report gets a deterministic identity:

```text
security-assurance-YYYYMMDDTHHMMSSZ-<short-runtime-sha>-<qualification-id>.md
```

A sanitized companion JSON file with the same stem supports future dashboards,
CI comparisons, and automation. `index.md` is rebuilt deterministically from
those companion files. Re-publishing the same qualification/revision is
idempotent; a conflicting identity is rejected rather than overwritten.

The generated Markdown includes every sanitized normalized finding, harness
verdict, transparent evidence metrics, severity/tool/suite counts, STRIDE,
OWASP Top 10 2021 and AP-* matrices, toolchain and runtime/resource tables,
architecture/trust-boundary summaries, human-review/out-of-scope statements,
remediation priorities, retest guidance, and the sanitization statement.
Where previous compatible reports exist, a bounded trend table is added;
different registry revisions are labeled rather than silently compared as
equivalent.

See [23 — Security Assurance Report Publication](23-report-publication.md) for
the complete operating procedure and interpretation rules.

## Scenario and tool semantics

A **scenario** is the Pocket Lab security invariant. A **tool** is an evidence
source. A scanner alert is not automatically a demonstrated exploit. When a
fixed executor already covers multiple related negative cases, the scenario
registry records those as machine-readable `coverage_cases` rather than
creating duplicate top-level scenarios that rerun the same executor.

Contributor procedures are in [20 — Adding a Scenario](20-adding-scenario.md)
and [21 — Adding a Tool](21-adding-tool.md).

## Historical lineage

The former large qualification dossier is preserved at
`../evidence-history/runtime-security-assurance-qualification.md`. It records
historical SHAs, run IDs, blockers, and prior command forms. It is not a
current operating procedure. Use the [command completeness mapping](../reference/command-completeness.md)
to understand whether a historical command is supported, superseded,
historical, or prohibited.

## Evidence safety

The redaction contract applies before persistence, display, aggregation, and
PR publication. The literal marker `[REDACTED BY SECURITY ASSURANCE POLICY]`
means that evidence was intentionally removed; it does not mean the value was
missing from the runtime. Never scan PhotoPrism/user media, Android shared
storage, backup payload contents, or excluded generated/cache paths.
