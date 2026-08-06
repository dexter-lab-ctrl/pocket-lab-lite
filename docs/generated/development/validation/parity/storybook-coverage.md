---
title: "Storybook Coverage Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Storybook Coverage Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Storybook uses the generated scenario registry and deterministic MSW aliases. It proves fixture-driven component states, accessibility intent, and viewport behavior; it does **not** prove backend persistence.

| Scenario | Story export | MSW scenario | A11y | Visual |
| --- | --- | --- | --- | --- |
| recovery-empty | Empty | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-backup-running | BackupRunning | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-backup-failed | BackupFailed | worker-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-verification-running | VerificationRunning | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-verified | Verified | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-verification-failed | VerificationFailed | worker-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-preview-ready | PreviewReady | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-confirmation-required | ConfirmationRequired | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-restore-running | RestoreRunning | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-restore-completed | RestoreCompleted | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-restore-failed | RestoreFailed | worker-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-rollback-completed | RollbackCompleted | healthy | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-projection-stale | ProjectionStale | nats-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-backend-unavailable | BackendUnavailable | nats-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
| recovery-offline-snapshot | OfflineSnapshot | nats-down | tests/e2e/lite-accessibility.spec.ts#recovery | tests/e2e/lite-visual.spec.ts#recovery |
