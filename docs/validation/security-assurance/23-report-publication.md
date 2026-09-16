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
→ verify canonical registry hashes
→ enrich tool version provenance from the matching tools registry
→ build report model and reader vocabulary
→ stage Markdown + companion JSON + index
→ existing redaction patterns scan staged files
→ atomic publication only after redaction passes
→ deterministic index
```

A redaction failure publishes nothing. The original runtime evidence is never mutated.

## What the report contains

Every newly generated report starts with a **How to Read This Report** section before the numbered evidence sections. It explains the report vocabulary and, for each term, what the term means and what it must **not** be interpreted to mean.

The report then includes:

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
13. Toolchain Matrix with registered and observed version provenance
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

## Tool version provenance

`security/assurance/tools.yaml` is the canonical registry for tool contracts. The report publisher may use its metadata only when the SHA-256 of the current registry exactly matches the tool-registry hash recorded by the selected qualification. This prevents a historical qualification from being silently enriched with a newer registry revision.

The Toolchain Matrix separates these concepts:

- **Registered version** — the expected numeric pin or `runtime-reported` policy from the hash-matched registry.
- **Observed version** — the version actually captured in the selected qualification's normalized tool evidence.
- **Version state** — the relationship between the registered policy and observed evidence.
- **Version source** — the registry-declared source that owns the version evidence, such as a qualified tool receipt, Security tool result, or policy status.

For a fixed pin, examples are:

```text
Registered version: 1.9.4
Observed version: bandit 1.9.4
Version state: MATCH
```

If that tool did not run in this qualification:

```text
Registered version: 1.9.4
Observed version: NOT_RUN
Version state: NOT_OBSERVED
```

The registry pin is still visible, but it is **not** represented as though it executed.

If a fixed pinned tool executes with another version, the report records `MISMATCH` instead of hiding the discrepancy.

### What `runtime-reported` means

`runtime-reported` is a deliberate registry policy, not a missing version. It means the authoritative version should come from the actual runtime/service/tool evidence instead of being fixed as a numeric `version_pin` in `tools.yaml`.

Examples include worker-owned Security tools and services such as Trivy, Lynis, OPA, or Pocket Lab's own Security projection when their registry entry delegates version authority to runtime evidence.

For runtime-reported tools:

- an observed version produces `RUNTIME_REPORTED`;
- missing observed version metadata produces `RUNTIME_VERSION_NOT_CAPTURED`;
- the report never invents a numeric version from another source.

`RUNTIME_VERSION_NOT_CAPTURED` does **not** mean the tool failed or was unavailable if its run status is `PASS` or `PARTIAL`; it means the version field itself was absent from the normalized evidence.

If the qualification's recorded tool-registry hash does not match the current canonical registry, the publisher does not mix revisions. Registry-derived version fields remain unavailable and `REGISTRY_METADATA_UNAVAILABLE` makes that provenance gap explicit.

## How to interpret report vocabulary

The generated reader guide includes, at minimum, these semantics:

- `PASS` — the registered invariant executed and was satisfied for this qualification. It is not a product-wide certification.
- `PARTIAL` — valid evidence exists, but coverage or the resulting condition is incomplete. It is not automatically a complete failure.
- `FAIL` — the registered invariant executed and was not satisfied. It is not automatically a demonstrated exploit.
- `BLOCKED` — execution did not proceed because a safety, admission, resource, dependency, or prerequisite gate prevented it. This is not automatically a failed security control.
- `CANCELLED` — the run was intentionally terminated before completion.
- `NOT_RUN` — the registered suite/tool was not executed **in this qualification**. It does not mean broken, unsupported, failed, or “scanned and found nothing.”
- `DEFERRED` — execution is intentionally postponed because an applicable prerequisite or safe executor is not currently available. It is not PASS.
- `UNAVAILABLE` — that particular metadata field was not present in normalized evidence. It does not mean the whole tool or service was unavailable.
- `NOT_APPLICABLE` — the check does not apply to this target/profile/context.
- `HUMAN_REVIEW_REQUIRED` — a human-governed ceremony or contextual decision is required; absence of scanner findings cannot convert it to automated PASS.
- `EVIDENCE_PRESENT` — applicable evidence exists for an OWASP/category projection; it does not mean every possible weakness in the category was tested.
- `NOT_ASSESSED` — no applicable automated evidence was produced; it is not PASS.
- `NEW` — the current finding has no matching selected baseline record; it does not prove the current code change introduced it.
- `EXISTING` — the finding matches the selected baseline; it does not imply risk acceptance.
- `REGRESSED` — the baseline comparison became materially worse; it does not by itself demonstrate exploitability.
- `RESOLVED` — a prior baseline finding is absent according to the comparison rules; recurrence remains possible.
- `UNCHANGED` — the finding materially matches the prior baseline; this does not mean safe or accepted.
- `0 findings` — no normalized findings are associated with the relevant executed evidence set. When a tool is `NOT_RUN`, zero findings must never be read as a clean scan.
- `Finding` — sanitized normalized security evidence requiring interpretation, not automatically a demonstrated exploit.
- `Scenario` — a registered Pocket Lab security invariant.
- `Tool` — a registered evidence source used to assess scenarios/suites.
- `Scenario coverage`, `Attack-path coverage`, and `Tool readiness` — transparent evidence ratios, not security scores.
- `Sanitized evidence` — normalized and filtered evidence, not raw scanner output.
- `Source SHA / Runtime SHA` — the exact revision represented by the qualification, not necessarily a later report-publication commit.

The generated report also calls out three common traps explicitly:

> `NOT_RUN` is per-qualification. Another suite may have separate qualification evidence.

> `0` findings for a `NOT_RUN` tool does not mean the tool scanned and found nothing.

> A registered/pinned version describes the expected tool contract; an observed version describes what this qualification actually captured.

## Assurance metrics

The publisher uses transparent evidence ratios only. Examples are executed scenario coverage, scenario PASS ratio, attack-path execution coverage, control coverage, tool readiness, and evidence completeness. Missing or blocked evidence never becomes zero-risk or a healthy-looking certification score.

`NOT_RUN` and `DEFERRED` tools are excluded from the current tool-readiness denominator. Therefore tool readiness does not represent “percentage of every registered tool installed everywhere.”

`UNAVAILABLE` is used for telemetry or metadata that is not present. Missing CPU, memory, battery, temperature, storage, retry, checkpoint, version, or per-tool-duration telemetry is never converted to zero.

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

A scanner finding is **evidence**, not automatically a demonstrated exploit. A scenario states the Pocket Lab invariant; tools supply evidence. `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, `NOT_RUN`, `UNAVAILABLE`, version provenance, and human/static classifications must be interpreted together with suite completion and coverage.

Critical/High findings remain visible regardless of coverage percentages. Human-only areas such as physical WebAuthn ceremonies, Enterprise membership/final Owner authority, approval ceremonies, and protected runtime-secret ownership/rotation remain explicit human review.
