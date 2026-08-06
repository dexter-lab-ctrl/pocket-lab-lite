---
title: "Test Data and Fixture Governance"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Test Data and Fixture Governance
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Fixtures are synthetic, sanitized, schema-bound, stable-ID driven, and generated from the canonical registry. Timestamps are normalized. Raw runtime captures cannot become fixtures without explicit sanitization and promotion. Deprecated scenarios remain traceable until consumers are removed.

| Scenario | Stable IDs | Fixture | Runtime eligibility |
| --- | --- | --- | --- |
| recovery-empty | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-empty.json | read-only |
| recovery-backup-running | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-backup-running.json | isolated-only |
| recovery-backup-failed | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-backup-failed.json | isolated-only |
| recovery-verification-running | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-verification-running.json | isolated-only |
| recovery-verified | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-verified.json | read-only |
| recovery-verification-failed | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-verification-failed.json | isolated-only |
| recovery-preview-ready | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-preview-ready.json | read-only |
| recovery-confirmation-required | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-confirmation-required.json | isolated-only |
| recovery-restore-running | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-restore-running.json | isolated-only |
| recovery-restore-completed | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-restore-completed.json | isolated-only |
| recovery-restore-failed | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-restore-failed.json | isolated-only |
| recovery-rollback-completed | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-rollback-completed.json | isolated-only |
| recovery-projection-stale | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-projection-stale.json | read-only |
| recovery-backend-unavailable | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-backend-unavailable.json | isolated-only |
| recovery-offline-snapshot | backup_id, preview_id, restore_id, operation_id | src/test/fixtures/generated/parity/recovery/recovery-offline-snapshot.json | read-only |
