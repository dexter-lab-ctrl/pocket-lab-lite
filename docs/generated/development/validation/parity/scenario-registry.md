---
title: "Parity Scenario Registry"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Parity Scenario Registry
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Scenario | Fixture | Story | Mocked browser | Live | Status |
| --- | --- | --- | --- | --- | --- |
| recovery-empty | src/test/fixtures/generated/parity/recovery/recovery-empty.json | Empty | tests/e2e/lite-parity.spec.ts#recovery-empty | read-only | ready |
| recovery-backup-running | src/test/fixtures/generated/parity/recovery/recovery-backup-running.json | BackupRunning | tests/e2e/lite-parity.spec.ts#recovery-backup-running | isolated-only | ready |
| recovery-backup-failed | src/test/fixtures/generated/parity/recovery/recovery-backup-failed.json | BackupFailed | tests/e2e/lite-parity.spec.ts#recovery-backup-failed | isolated-only | ready |
| recovery-verification-running | src/test/fixtures/generated/parity/recovery/recovery-verification-running.json | VerificationRunning | tests/e2e/lite-parity.spec.ts#recovery-verification-running | isolated-only | ready |
| recovery-verified | src/test/fixtures/generated/parity/recovery/recovery-verified.json | Verified | tests/e2e/lite-parity.spec.ts#recovery-verified | read-only | ready |
| recovery-verification-failed | src/test/fixtures/generated/parity/recovery/recovery-verification-failed.json | VerificationFailed | tests/e2e/lite-parity.spec.ts#recovery-verification-failed | isolated-only | ready |
| recovery-preview-ready | src/test/fixtures/generated/parity/recovery/recovery-preview-ready.json | PreviewReady | tests/e2e/lite-parity.spec.ts#recovery-preview-ready | read-only | ready |
| recovery-confirmation-required | src/test/fixtures/generated/parity/recovery/recovery-confirmation-required.json | ConfirmationRequired | tests/e2e/lite-parity.spec.ts#recovery-confirmation-required | isolated-only | ready |
| recovery-restore-running | src/test/fixtures/generated/parity/recovery/recovery-restore-running.json | RestoreRunning | tests/e2e/lite-parity.spec.ts#recovery-restore-running | isolated-only | ready |
| recovery-restore-completed | src/test/fixtures/generated/parity/recovery/recovery-restore-completed.json | RestoreCompleted | tests/e2e/lite-parity.spec.ts#recovery-restore-completed | isolated-only | ready |
| recovery-restore-failed | src/test/fixtures/generated/parity/recovery/recovery-restore-failed.json | RestoreFailed | tests/e2e/lite-parity.spec.ts#recovery-restore-failed | isolated-only | ready |
| recovery-rollback-completed | src/test/fixtures/generated/parity/recovery/recovery-rollback-completed.json | RollbackCompleted | tests/e2e/lite-parity.spec.ts#recovery-rollback-completed | isolated-only | ready |
| recovery-projection-stale | src/test/fixtures/generated/parity/recovery/recovery-projection-stale.json | ProjectionStale | tests/e2e/lite-parity.spec.ts#recovery-projection-stale | read-only | ready |
| recovery-backend-unavailable | src/test/fixtures/generated/parity/recovery/recovery-backend-unavailable.json | BackendUnavailable | tests/e2e/lite-parity.spec.ts#recovery-backend-unavailable | isolated-only | ready |
| recovery-offline-snapshot | src/test/fixtures/generated/parity/recovery/recovery-offline-snapshot.json | OfflineSnapshot | tests/e2e/lite-parity.spec.ts#recovery-offline-snapshot | read-only | ready |
