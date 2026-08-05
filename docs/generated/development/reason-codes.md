---
title: "Reason-code registry"
description: "Canonical cross-domain Lite reason codes and user/audit mappings."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 2c4fcef609a9d4a405042cf4786ae09b9cbe55c94905a965d1b526eeb732f6b0
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Reason-code registry

| Code | Domain | Meaning | Retryable | Terminal | HTTP | Severity | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `already_tuned` | validation | No additional tuning was required. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `cold_start_validation` | validation | Cold-start validation is in progress. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `diagnostics_not_active` | validation | Diagnostics are not active. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `disabled` | system | The requested capability is disabled. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `generation_changed` | projections | The source generation changed during work. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `insufficient_storage` | system | There is not enough safe storage for the operation. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `interrupted` | system | The operation was interrupted. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `invalid_domain` | projections | The requested projection domain is invalid. | yes | no | 400 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `invite_identity_mismatch` | devices | The invite identity does not match the enrolled device. | no | yes | 409 | high | structured reason/failure fields in Lite backend or contracts metadata |
| `lease_active` | projections | Another bounded owner currently holds the lease. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `legacy_multiple_active_runs` | system | Legacy state contains multiple active runs. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `metadata_only` | validation | Only metadata was evaluated. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `no_active_generation` | projections | There is no active generation. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `not_found_in_restored_snapshot` | system | The record is not present in the restored snapshot. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `payload_too_large` | validation | The bounded payload limit was exceeded. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `projection_unavailable` | projections | The prepared projection is unavailable. | yes | no | 503 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `queue_full` | projections | The bounded queue cannot accept more work. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `release_projection_unavailable` | release | The release prepared projection is unavailable. | yes | no | 503 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `shutdown` | system | The process is shutting down. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `shutdown_during_mailbox_backpressure` | projections | Shutdown occurred while the bounded mailbox was under pressure. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `submit_failed` | system | The work request could not be admitted. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `target_not_allowed` | validation | The requested target is outside the approved scope. | no | yes | 400 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `unregistered_domain` | projections | The requested domain is not registered. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `worker_failed` | security | The worker reported a terminal failure. | yes | yes | 200 | high | structured reason/failure fields in Lite backend or contracts metadata |
| `worker_start_timeout` | security | The worker did not start the accepted work within the recovery window. | yes | yes | 503 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `projection_too_old` | projections | The last committed projection is too old for a safe write. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `read_degraded` | system | A safe last-known read is shown while refresh is unavailable. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `identity_mismatch` | devices | The local identity does not match the requested enrollment. | no | yes | 409 | high | structured reason/failure fields in Lite backend or contracts metadata |
| `remote_access_not_ready` | devices | Private remote access is not ready. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `service_unavailable` | system | A required backend service is unavailable. | yes | no | 503 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `command_undeliverable` | devices | The target agent cannot currently receive the command. | yes | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `invite_expired` | devices | The device invite is no longer valid. | yes | yes | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `duplicate_device` | devices | A matching device or invite already exists. | yes | no | 409 | warning | structured reason/failure fields in Lite backend or contracts metadata |
| `protected_server_host` | devices | The protected server host cannot use this destructive action. | no | no | 200 | warning | structured reason/failure fields in Lite backend or contracts metadata |
