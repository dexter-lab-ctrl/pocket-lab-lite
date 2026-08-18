---
title: "Evidence Manifest and Traceability Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Evidence Manifest and Traceability Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Evidence traceability is generated from the same canonical domain, scenario, comparator, and gate registries. Raw API, browser, and Termux observations stay under `.pocketlab-dev/validation/parity` and are not tracked. The comparison step produces a sanitized normalized semantic result. `lite:evidence:runtime:promote` independently revalidates the raw allowlisted observations, recomputes their comparisons, binds the evidence hashes to a release tag and source commit, and writes only the promoted baseline under `contracts/parity`. Ordinary documentation generation consumes only that promoted baseline. A mismatch remains valid drift evidence; missing, stale, failed, or unavailable capture is classified separately and is not called drift.

| Scenario | Backend | API | Selector | UI | Story | Browser | Runtime |
| --- | --- | --- | --- | --- | --- | --- | --- |
| recovery-empty | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Create your first protected backup, No backup yet | Empty | tests/e2e/lite-parity.spec.ts#recovery-empty | unvalidated-runtime |
| recovery-backup-running | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Backup protection is working, Backup or restore activity | BackupRunning | tests/e2e/lite-parity.spec.ts#recovery-backup-running | unvalidated-runtime |
| recovery-backup-failed | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Backup needs attention, Needs attention | BackupFailed | tests/e2e/lite-parity.spec.ts#recovery-backup-failed | unvalidated-runtime |
| recovery-verification-running | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Backup verification is running, Backup or restore activity | VerificationRunning | tests/e2e/lite-parity.spec.ts#recovery-verification-running | unvalidated-runtime |
| recovery-verified | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Backup protection is ready, Verified | Verified | tests/e2e/lite-parity.spec.ts#recovery-verified | unvalidated-runtime |
| recovery-verification-failed | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Verify your latest backup, Needs verification | VerificationFailed | tests/e2e/lite-parity.spec.ts#recovery-verification-failed | unvalidated-runtime |
| recovery-preview-ready | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Restore preview ready, Preview ready | PreviewReady | tests/e2e/lite-parity.spec.ts#recovery-preview-ready | unvalidated-runtime |
| recovery-confirmation-required | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Confirmation required, Restore backup | ConfirmationRequired | tests/e2e/lite-parity.spec.ts#recovery-confirmation-required | unvalidated-runtime |
| recovery-restore-running | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Backup or restore activity, Working | RestoreRunning | tests/e2e/lite-parity.spec.ts#recovery-restore-running | unvalidated-runtime |
| recovery-restore-completed | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Restore completed safely, Restored | RestoreCompleted | tests/e2e/lite-parity.spec.ts#recovery-restore-completed | unvalidated-runtime |
| recovery-restore-failed | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Restore needs attention, Needs attention | RestoreFailed | tests/e2e/lite-parity.spec.ts#recovery-restore-failed | unvalidated-runtime |
| recovery-rollback-completed | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Rollback completed, Checkpoint | RollbackCompleted | tests/e2e/lite-parity.spec.ts#recovery-rollback-completed | unvalidated-runtime |
| recovery-projection-stale | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Showing saved state, saved | ProjectionStale | tests/e2e/lite-parity.spec.ts#recovery-projection-stale | unvalidated-runtime |
| recovery-backend-unavailable | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Recovery, unavailable | BackendUnavailable | tests/e2e/lite-parity.spec.ts#recovery-backend-unavailable | unvalidated-runtime |
| recovery-offline-snapshot | sanitized deterministic recovery authority fixture | recovery-summary | selectRecoveryScreenView | Showing saved state, Backup protection is ready | OfflineSnapshot | tests/e2e/lite-parity.spec.ts#recovery-offline-snapshot | unvalidated-runtime |
