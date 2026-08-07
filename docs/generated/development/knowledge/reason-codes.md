---
title: "Reason-code encyclopedia"
description: "Canonical reason-code semantics with operational links."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Reason-code encyclopedia

| Code | Domain | Meaning | Severity | Retryable | Terminal | User interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| `already_tuned` | validation | No additional tuning was required. | warning | yes | no | No additional tuning was required. |
| `cold_start_validation` | validation | Cold-start validation is in progress. | warning | yes | no | Cold-start validation is in progress. |
| `command_undeliverable` | devices | The target agent cannot currently receive the command. | warning | yes | no | The target agent cannot currently receive the command. |
| `diagnostics_not_active` | validation | Diagnostics are not active. | warning | yes | no | Diagnostics are not active. |
| `disabled` | system | The requested capability is disabled. | warning | yes | no | The requested capability is disabled. |
| `duplicate_device` | devices | A matching device or invite already exists. | warning | yes | no | A matching device or invite already exists. |
| `generation_changed` | projections | The source generation changed during work. | warning | yes | no | The source generation changed during work. |
| `identity_mismatch` | devices | The local identity does not match the requested enrollment. | high | no | yes | The local identity does not match the requested enrollment. |
| `insufficient_storage` | system | There is not enough safe storage for the operation. | warning | yes | no | There is not enough safe storage for the operation. |
| `interrupted` | system | The operation was interrupted. | warning | yes | no | The operation was interrupted. |
| `invalid_domain` | projections | The requested projection domain is invalid. | warning | yes | no | The requested projection domain is invalid. |
| `invite_expired` | devices | The device invite is no longer valid. | warning | yes | yes | The device invite is no longer valid. |
| `invite_identity_mismatch` | devices | The invite identity does not match the enrolled device. | high | no | yes | The invite identity does not match the enrolled device. |
| `lease_active` | projections | Another bounded owner currently holds the lease. | warning | yes | no | Another bounded owner currently holds the lease. |
| `legacy_multiple_active_runs` | system | Legacy state contains multiple active runs. | warning | yes | no | Legacy state contains multiple active runs. |
| `metadata_only` | validation | Only metadata was evaluated. | warning | yes | no | Only metadata was evaluated. |
| `no_active_generation` | projections | There is no active generation. | warning | yes | no | There is no active generation. |
| `not_found_in_restored_snapshot` | system | The record is not present in the restored snapshot. | warning | yes | no | The record is not present in the restored snapshot. |
| `payload_too_large` | validation | The bounded payload limit was exceeded. | warning | yes | no | The bounded payload limit was exceeded. |
| `projection_too_old` | projections | The last committed projection is too old for a safe write. | warning | yes | no | The last committed projection is too old for a safe write. |
| `projection_unavailable` | projections | The prepared projection is unavailable. | warning | yes | no | The prepared projection is unavailable. |
| `protected_server_host` | devices | The protected server host cannot use this destructive action. | warning | no | no | The protected server host cannot use this destructive action. |
| `queue_full` | projections | The bounded queue cannot accept more work. | warning | yes | no | The bounded queue cannot accept more work. |
| `read_degraded` | system | A safe last-known read is shown while refresh is unavailable. | warning | yes | no | A safe last-known read is shown while refresh is unavailable. |
| `release_projection_unavailable` | release | The release prepared projection is unavailable. | warning | yes | no | The release prepared projection is unavailable. |
| `remote_access_not_ready` | devices | Private remote access is not ready. | warning | yes | no | Private remote access is not ready. |
| `service_unavailable` | system | A required backend service is unavailable. | warning | yes | no | A required backend service is unavailable. |
| `shutdown` | system | The process is shutting down. | warning | yes | no | The process is shutting down. |
| `shutdown_during_mailbox_backpressure` | projections | Shutdown occurred while the bounded mailbox was under pressure. | warning | yes | no | Shutdown occurred while the bounded mailbox was under pressure. |
| `submit_failed` | system | The work request could not be admitted. | warning | yes | no | The work request could not be admitted. |
| `target_not_allowed` | validation | The requested target is outside the approved scope. | warning | no | yes | The requested target is outside the approved scope. |
| `unregistered_domain` | projections | The requested domain is not registered. | warning | yes | no | The requested domain is not registered. |
| `worker_failed` | security | The worker reported a terminal failure. | high | yes | yes | The worker reported a terminal failure. |
| `worker_start_timeout` | security | The worker did not start the accepted work within the recovery window. | warning | yes | yes | The worker did not start the accepted work within the recovery window. |
