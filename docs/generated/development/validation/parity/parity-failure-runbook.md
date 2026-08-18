---
title: "Operational Runbook for Parity Failures"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Operational Runbook for Parity Failures
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## Symptoms

A backend/API value is rendered with the wrong meaning, desktop and mobile disagree, an API/Termux observation differs, a selector maps the wrong state family, evidence is stale or incomplete, a capture fails, runtime is unavailable, or generated parity artifacts drift from the canonical model.

## Read-only verification

1. Verify the local API or bounded SSH loopback tunnel without exposing the phone directly.
2. Run deterministic model, schema, selector, fixture, and generated-artifact checks.
3. Capture sanitized read-only API and Termux observations for the affected domains.
4. Run live desktop and mobile Playwright capture with the release tag and source commit bound.
5. Run the semantic comparator and inspect failure attribution before interpreting any mismatch.
6. Treat `drift-detected` as valid evidence; do not rewrite application behavior merely to make documentation pass.
7. Treat `capture-failed`, `stale-evidence`, and `runtime-unavailable` as capture states, not drift.
8. Promote only after the allowlisted observations and recomputed comparisons pass release/source/freshness validation.

## Recovery

Do not edit SQLite, generated baselines, runtime state, or frontend selectors merely to clear a parity report. Repair the owning backend, projection, selector, presentation mapping, capture adapter, or documented accepted limitation according to failure attribution. Destructive or identity-sensitive recovery remains backend-owned and must use existing explicit confirmations.
