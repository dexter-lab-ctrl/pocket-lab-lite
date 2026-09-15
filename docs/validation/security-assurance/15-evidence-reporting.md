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
