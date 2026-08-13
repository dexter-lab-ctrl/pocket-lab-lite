---
title: "Canonical fixtures and schemas"
description: "`generate_contracts.py` exports a Lite-only OpenAPI contract, validates frontend routes, and generates bounded sanitized scenario metadata used by MSW, Storybook, and mocked Playwright."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: dfb263a6195e29ff1381aa1d08a5a5f2cf0ab435319029c6267b6e121c251839
schema_revision: 1
validation_status: generated
---

# Canonical fixtures and schemas

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

`generate_contracts.py` exports a Lite-only OpenAPI contract, validates frontend routes, and generates bounded sanitized scenario metadata used by MSW, Storybook, and mocked Playwright.

## Generated fixture directories

- `src/test/fixtures/generated/apps/app-action-failed.json`
- `src/test/fixtures/generated/apps/app-media-not-ready.json`
- `src/test/fixtures/generated/apps/app-projection-stale.json`
- `src/test/fixtures/generated/apps/app-route-not-ready.json`
- `src/test/fixtures/generated/apps/app-stopped.json`
- `src/test/fixtures/generated/apps/catalog-install-available.json`
- `src/test/fixtures/generated/apps/catalog-installing.json`
- `src/test/fixtures/generated/apps/catalog-ready.json`
- `src/test/fixtures/generated/apps/healthy.json`
- `src/test/fixtures/generated/apps/offline-saved.json`
- `src/test/fixtures/generated/devices/devices-agent-stopped.json`
- `src/test/fixtures/generated/devices/devices-capability-missing.json`
- `src/test/fixtures/generated/devices/devices-capability-pending.json`
- `src/test/fixtures/generated/devices/devices-capability-verified.json`
- `src/test/fixtures/generated/devices/devices-invite-expired.json`
- `src/test/fixtures/generated/devices/devices-invite-mismatch.json`
- `src/test/fixtures/generated/devices/devices-invite-ready.json`
- `src/test/fixtures/generated/devices/devices-offline.json`
- `src/test/fixtures/generated/devices/devices-online.json`
- `src/test/fixtures/generated/devices/devices-protected-host.json`
- `src/test/fixtures/generated/devices/devices-remote-not-ready.json`
- `src/test/fixtures/generated/devices/devices-repairing.json`
- `src/test/fixtures/generated/devices/devices-server-online.json`
- `src/test/fixtures/generated/devices/offline-saved.json`
- `src/test/fixtures/generated/home/api-unavailable.json`
- `src/test/fixtures/generated/home/healthy.json`
- `src/test/fixtures/generated/home/offline-saved.json`
- `src/test/fixtures/generated/home/release-available.json`
- `src/test/fixtures/generated/home/release-current.json`
- `src/test/fixtures/generated/home/release-failed.json`
- `src/test/fixtures/generated/home/review-recommended.json`
- `src/test/fixtures/generated/identity/api-unavailable.json`
- `src/test/fixtures/generated/identity/identity-password-change-required.json`
- `src/test/fixtures/generated/identity/identity-password-configured.json`
- `src/test/fixtures/generated/identity/identity-role-aware-fixture.json`
- `src/test/fixtures/generated/identity/identity-summary.json`
- `src/test/fixtures/generated/identity/slow-response.json`
- `src/test/fixtures/generated/manifest.json`
- `src/test/fixtures/generated/parity/recovery/recovery-backend-unavailable.json`
- `src/test/fixtures/generated/parity/recovery/recovery-backup-failed.json`
- `src/test/fixtures/generated/parity/recovery/recovery-backup-running.json`
- `src/test/fixtures/generated/parity/recovery/recovery-confirmation-required.json`
- `src/test/fixtures/generated/parity/recovery/recovery-empty.json`
- `src/test/fixtures/generated/parity/recovery/recovery-offline-snapshot.json`
- `src/test/fixtures/generated/parity/recovery/recovery-preview-ready.json`
- `src/test/fixtures/generated/parity/recovery/recovery-projection-stale.json`
- `src/test/fixtures/generated/parity/recovery/recovery-restore-completed.json`
- `src/test/fixtures/generated/parity/recovery/recovery-restore-failed.json`
- `src/test/fixtures/generated/parity/recovery/recovery-restore-running.json`
- `src/test/fixtures/generated/parity/recovery/recovery-rollback-completed.json`
- `src/test/fixtures/generated/parity/recovery/recovery-verification-failed.json`
- `src/test/fixtures/generated/parity/recovery/recovery-verification-running.json`
- `src/test/fixtures/generated/parity/recovery/recovery-verified.json`
- `src/test/fixtures/generated/recovery/offline-saved.json`
- `src/test/fixtures/generated/recovery/recovery-backup-failed.json`
- `src/test/fixtures/generated/recovery/recovery-backup-running.json`
- `src/test/fixtures/generated/recovery/recovery-checkpoint-ready.json`
- `src/test/fixtures/generated/recovery/recovery-no-backups.json`
- `src/test/fixtures/generated/recovery/recovery-no-storage-node.json`
- `src/test/fixtures/generated/recovery/recovery-preview-ready.json`
- `src/test/fixtures/generated/recovery/recovery-projection-too-old.json`
- `src/test/fixtures/generated/recovery/recovery-ready.json`
- `src/test/fixtures/generated/recovery/recovery-repository-unavailable.json`
- `src/test/fixtures/generated/recovery/recovery-restore-blocked.json`
- `src/test/fixtures/generated/recovery/recovery-verified.json`
- `src/test/fixtures/generated/rules/api-unavailable.json`
- `src/test/fixtures/generated/rules/rules-approval-required.json`
- `src/test/fixtures/generated/rules/rules-disabled.json`
- `src/test/fixtures/generated/rules/rules-empty.json`
- `src/test/fixtures/generated/rules/rules-enabled.json`
- `src/test/fixtures/generated/rules/rules-execution-pending.json`
- `src/test/fixtures/generated/rules/rules-present.json`
- `src/test/fixtures/generated/rules/rules-validation-error.json`
- `src/test/fixtures/generated/security/offline-saved.json`
- `src/test/fixtures/generated/security/security-action-needed.json`
- `src/test/fixtures/generated/security/security-app-check-healthy.json`
- `src/test/fixtures/generated/security/security-first-run.json`
- `src/test/fixtures/generated/security/security-full-running.json`
- `src/test/fixtures/generated/security/security-profile-stale.json`
- `src/test/fixtures/generated/security/security-progress.json`
- `src/test/fixtures/generated/security/security-quick-healthy.json`
- `src/test/fixtures/generated/security/security-scanner-unavailable.json`
- `src/test/fixtures/generated/security/security-unsupported-app-route.json`
- `src/test/fixtures/generated/security/security-urgent.json`

Identity and Rules fixtures are explicitly partial or fixture-only. No write success is fabricated.
