# Human review playbook

Some security questions require a person with the relevant authority. A
scenario modeled as `HUMAN_REVIEW_REQUIRED` is complete coverage
classification, not an omitted implementation. The harness must not create a
machine shortcut for a human ceremony.

## Review template

For each human-only item record:

| Field | Required entry |
| --- | --- |
| Scenario | canonical scenario or AP-* ID and name |
| Threat | concrete asset and abuse hypothesis |
| STRIDE / OWASP | applicable categories; no forced mapping |
| AP path | canonical attack-path ID(s) |
| Why human | why a physical ceremony, governance decision, or protected secret review cannot be automated safely |
| Reviewer | role/authority of the human reviewer |
| Evidence | sanitized reports, audit events, policy/release records, and bounded runtime facts |
| Pass criteria | observable conditions that establish the control |
| Fail criteria | observable violation or missing evidence |
| Residual risk | what remains after review and owner of follow-up |

## Current human-review areas

| Area | Classification | Human procedure |
| --- | --- | --- |
| Physical WebAuthn identity ceremony | `HUMAN_REVIEW_REQUIRED` | An authorized identity/security reviewer completes the physical/user ceremony and checks challenge, authenticator, audit, and recovery evidence. |
| Enterprise membership governance | `HUMAN_REVIEW_REQUIRED` | An enterprise administrator verifies membership approval, separation of duties, and audit lineage. |
| Final-Owner privilege governance | `HUMAN_REVIEW_REQUIRED` | A designated owner reviews the final-Owner ceremony and confirms no synthetic assurance principal received Owner authority. |
| Human approval and exception acceptance | `HUMAN_REVIEW_REQUIRED` | The authorized approver checks scope, expiry, rationale, and immutable decision evidence. |
| Protected Gitea runtime-secret ownership/rotation | `HUMAN_REVIEW_REQUIRED` | An operator verifies ownership and rotation responsibility without opening or copying the secret. |
| Destructive Recovery authorization/testing | `HUMAN_REVIEW_REQUIRED` / out of scope | Recovery owners review the supported procedure separately; it is not part of normal Security Assurance qualification. |

The protected Gitea review is non-blocking for the Security Assurance Harness
when current bounded evidence still shows mode `0600`, a protected parent
directory, no frontend/report/log exposure, and an assigned operator owner.
That statement requires evidence from the current environment; never print the
file contents.

## What must never be automated

- physical WebAuthn or user-presence ceremonies;
- final Owner or Enterprise membership decisions;
- human exception/risk acceptance;
- reading or rotating secret material through the harness;
- destructive backup/restore or production-data rollback;
- arbitrary command execution to “prove” a governance control.

## Review checklist

1. Confirm the scenario is present in the canonical threat model and scenario
   registry.
2. Confirm the automated harness did not claim runtime PASS for the human-only
   portion.
3. Inspect sanitized evidence and audit correlation without requesting secret
   values.
4. Record the reviewer role, decision, timestamp, and residual risk in the
   approved governance system.
5. Leave the qualification result as `HUMAN_REVIEW_REQUIRED` when the human
   ceremony has not occurred.

Human governance reviews, Gitea ownership/rotation, and destructive Recovery
are non-blocking follow-ups for this documentation PR when the harness itself
correctly models, reports, and isolates them. They must not be relabeled as
automated assurance.
