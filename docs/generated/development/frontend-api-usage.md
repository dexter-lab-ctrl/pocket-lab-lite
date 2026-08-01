---
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_contracts.py
source_fingerprint: 800bbf6fc924c59828885057dac0d31434bf29bbe6e1c27f5a2045319f4f8472
schema_revision: 1
validation_status: generated
---

# Frontend API usage

## Unsupported frontend route references
- None

## Backend Lite routes with no detected frontend consumer
- `/api/lite/catalog/remove`
- `/api/lite/diagnostics/runtime/full`
- `/api/lite/fleet/agent/bootstrap-blocked`
- `/api/lite/fleet/agent/bootstrap.env`
- `/api/lite/fleet/agent/bootstrap.sh`
- `/api/lite/fleet/invites/latest`
- `/api/lite/recovery/apps/{app_id}/backup`
- `/api/lite/recovery/apps/{app_id}/backup-to-target`
- `/api/lite/recovery/apps/{app_id}/restore/preview`
- `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`
- `/api/lite/recovery/restore/runs/{restore_id}`
- `/api/lite/security/evidence/{run_id}`
- `/api/lite/security/scan`

The second list is informational: worker callbacks, diagnostics, compatibility aliases, and operator-only endpoints may intentionally have no normal UI consumer.
