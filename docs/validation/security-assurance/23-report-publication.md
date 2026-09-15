# Security Assurance Report Publication

Pocket Lab Lite can transform one completed Runtime Security Assurance qualification into a comprehensive MkDocs report. Publication consumes **only** the existing normalized/sanitized report bundle returned by the Security Assurance API. It never parses raw scanner output as publication source.

A report is assurance evidence, not a certification and not a blanket statement that the system is secure.

## Prerequisites

Use a specific terminal runtime assurance ID of the form:

```text
assurance-<32 lowercase hexadecimal characters>
```

The selected run must be `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or `CANCELLED`, and its sanitized report bundle must contain all required artifacts and fail-closed sanitization markers.

On the DEV PC/approved client, establish an authorized direct-loopback harness session to the runtime that owns the qualification evidence. Report publication is a repository/docs operation and is **not** a Server Phone tracked-source editing workflow.

## Generate / validate the model

```bash
task lite:security:assurance:report:generate \
  QUALIFICATION_ID=<assurance-run-id>
```

This fetches the selected run and its existing sanitized report bundle and verifies terminal state, bounded artifact sizes, required normalized artifacts, qualification identity, and sanitization markers. It does not publish a file.

## Publish into MkDocs

```bash
task lite:security:assurance:report:publish \
  QUALIFICATION_ID=<assurance-run-id>
```

Publication writes:

```text
docs/generated/security-assurance/reports/
  security-assurance-YYYYMMDDTHHMMSSZ-<short-sha>-<qualification-id>.md
  security-assurance-YYYYMMDDTHHMMSSZ-<short-sha>-<qualification-id>.json
  index.md
```

The Markdown is presentation. The companion JSON is the sanitized normalized report model for future dashboards, CI comparison, and automation.

The filename identity is deterministic from the qualification completion timestamp, exact runtime/source revision, and run ID. Re-publishing the same qualification/revision is idempotent. A conflicting report identity fails rather than overwriting another qualification.

## Fail-closed publication sequence

The publisher performs this sequence:

```text
specific qualification ID
→ terminal run check
→ normalized report bundle exists
→ required sanitized markers are safe
→ bounded normalized files only
→ build report model
→ stage Markdown + companion JSON + index
→ existing redaction patterns scan staged files
→ atomic publication only after redaction passes
→ deterministic index
```

A redaction failure publishes nothing. The original runtime evidence is never mutated.

## What the report contains

The report includes:

1. Executive Security Summary
2. Qualification Identity
3. Overall Assurance Verdict
4. Security Confidence / Assurance Metrics
5. Finding Counts
6. Severity Chart and accessible table
7. Findings by Tool
8. Findings by Suite
9. Complete sanitized normalized Finding Register
10. STRIDE Matrix
11. OWASP Top 10 2021 Matrix
12. AP-* Attack-Path Matrix
13. Toolchain Matrix
14. Runtime / Resource Metrics
15. Security Architecture Mermaid diagram
16. Trust Boundaries
17. Controls Validated
18. Human Review Required
19. Out of Scope
20. Remediation Priorities
21. Retest Plan
22. Sanitization Statement

Where previous compatible companion JSON reports exist, the publisher also shows bounded historical trend rows. Reports from a different registry revision are explicitly labeled as a different comparison revision rather than silently treated as equivalent.

## Assurance metrics

The publisher uses transparent evidence ratios only. Examples are executed scenario coverage, scenario PASS ratio, attack-path execution coverage, control coverage, tool readiness, and evidence completeness. Missing or blocked evidence never becomes zero-risk or a healthy-looking certification score.

`UNAVAILABLE` is used for telemetry that is not present. Missing CPU, memory, battery, temperature, storage, retry, or checkpoint telemetry is never converted to zero.

## Sanitization statement

Publication excludes private keys, session/provisioning tokens, passwords, Authorization headers, cookies, CSRF tokens, NATS credentials, Tailscale credentials, Recovery encryption material, raw secret matches, user/PhotoPrism media, and raw scanner output.

The existing `scripts/dev/lite/redaction_check.py` patterns are applied to staged Markdown/JSON/index content before atomic publication.

## Check a published report

```bash
task lite:security:assurance:report:check \
  QUALIFICATION_ID=<assurance-run-id>
```

The check verifies a single matching companion model, Markdown/JSON/index presence, index link, redaction, and finding-count reconciliation.

To rebuild only the deterministic index from already-published sanitized companion files:

```bash
task lite:security:assurance:reports:index
```

## Interpretation rules

A scanner finding is **evidence**, not automatically a demonstrated exploit. A scenario states the Pocket Lab invariant; tools supply evidence. `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, and human/static classifications must be interpreted together with suite completion and coverage.

Critical/High findings remain visible regardless of coverage percentages. Human-only areas such as physical WebAuthn ceremonies, Enterprise membership/final Owner authority, approval ceremonies, and protected runtime-secret ownership/rotation remain explicit human review.
