---
title: "Operational reason codes"
description: "Canonical reason-code encyclopedia with current observations and operator guidance."
generated: true
audience: development
confidence: generated
---

# Operational reason-code encyclopedia

## Active in current promoted health

| Code | Domains | Meaning | Next action |
| --- | --- | --- | --- |
| projection_too_old | recovery | The last committed projection is too old for a safe write. | Capture fresh sanitized runtime evidence and explicitly promote it before claiming current readiness. |
| read_degraded | home | A safe last-known read is shown while refresh is unavailable. | Inspect the owning dependency/readiness evidence and recover through the backend-owned path. |

## Canonical registry

| Code | Domain | Severity | Retryable | Meaning | Operator guidance |
| --- | --- | --- | --- | --- | --- |
| already_tuned | validation | warning | yes | No additional tuning was required. | Correct the prerequisite and retry through the owning backend workflow. |
| authentication_required | identity | warning | yes | A protected write requires an authenticated human session or configured service credential. | Correct the prerequisite and retry through the owning backend workflow. |
| cold_start_validation | validation | warning | yes | Cold-start validation is in progress. | Correct the prerequisite and retry through the owning backend workflow. |
| command_undeliverable | devices | warning | yes | The target agent cannot currently receive the command. | Correct the prerequisite and retry through the owning backend workflow. |
| csrf_required | identity | warning | yes | A human-session write was rejected because its CSRF proof was missing or invalid. | Correct the prerequisite and retry through the owning backend workflow. |
| diagnostics_not_active | validation | warning | yes | Diagnostics are not active. | Correct the prerequisite and retry through the owning backend workflow. |
| disabled | system | warning | yes | The requested capability is disabled. | Correct the prerequisite and retry through the owning backend workflow. |
| duplicate_device | devices | warning | yes | A matching device or invite already exists. | Correct the prerequisite and retry through the owning backend workflow. |
| generation_changed | projections | warning | yes | The source generation changed during work. | Correct the prerequisite and retry through the owning backend workflow. |
| generic_policy_toggle_retired | rules | info | no | The legacy generic Rules toggle endpoint is retired; live OPA policy state is backend-owned. | Review the owning evidence and operator guidance before another action. |
| human_session_required | identity | warning | yes | The requested credential or session lifecycle action requires the signed-in local owner session. | Correct the prerequisite and retry through the owning backend workflow. |
| identity_mismatch | devices | high | no | The local identity does not match the requested enrollment. | Review the owning evidence and operator guidance before another action. |
| identity_setup_rejected | identity | warning | yes | Trusted owner-claim creation was rejected because the supplied setup proof was missing or invalid. | Correct the prerequisite and retry through the owning backend workflow. |
| identity_setup_unavailable | identity | error | yes | Trusted owner-claim creation is unavailable because the server-side setup channel is not enabled. | Correct the prerequisite and retry through the owning backend workflow. |
| insufficient_storage | system | warning | yes | There is not enough safe storage for the operation. | Correct the prerequisite and retry through the owning backend workflow. |
| interrupted | system | warning | yes | The operation was interrupted. | Correct the prerequisite and retry through the owning backend workflow. |
| invalid_domain | projections | warning | yes | The requested projection domain is invalid. | Correct the prerequisite and retry through the owning backend workflow. |
| invite_expired | devices | warning | yes | The device invite is no longer valid. | Correct the prerequisite and retry through the owning backend workflow. |
| invite_identity_mismatch | devices | high | no | The invite identity does not match the enrolled device. | Review the owning evidence and operator guidance before another action. |
| lease_active | projections | warning | yes | Another bounded owner currently holds the lease. | Correct the prerequisite and retry through the owning backend workflow. |
| legacy_multiple_active_runs | system | warning | yes | Legacy state contains multiple active runs. | Correct the prerequisite and retry through the owning backend workflow. |
| legacy_secret_rotation_retired | identity | info | no | The legacy generic secret-rotation endpoint is retired and is not a human password operation. | Review the owning evidence and operator guidance before another action. |
| metadata_only | validation | warning | yes | Only metadata was evaluated. | Correct the prerequisite and retry through the owning backend workflow. |
| no_active_generation | projections | warning | yes | There is no active generation. | Correct the prerequisite and retry through the owning backend workflow. |
| not_found_in_restored_snapshot | system | warning | yes | The record is not present in the restored snapshot. | Correct the prerequisite and retry through the owning backend workflow. |
| payload_too_large | validation | warning | yes | The bounded payload limit was exceeded. | Correct the prerequisite and retry through the owning backend workflow. |
| policy_decision_not_found | rules | warning | no | The requested bounded Safety Rules decision record is no longer available. | Review the owning evidence and operator guidance before another action. |
| policy_unavailable | rules | error | yes | The loopback OPA decision path is unavailable or invalid, so the protected action fails closed before execution. | Correct the prerequisite and retry through the owning backend workflow. |
| projection_too_old | projections | warning | yes | The last committed projection is too old for a safe write. | Capture fresh sanitized runtime evidence and explicitly promote it before claiming current readiness. |
| projection_unavailable | projections | warning | yes | The prepared projection is unavailable. | Correct the prerequisite and retry through the owning backend workflow. |
| protected_server_host | devices | warning | no | The protected server host cannot use this destructive action. | Review the owning evidence and operator guidance before another action. |
| queue_full | projections | warning | yes | The bounded queue cannot accept more work. | Correct the prerequisite and retry through the owning backend workflow. |
| read_degraded | system | warning | yes | A safe last-known read is shown while refresh is unavailable. | Inspect the owning dependency/readiness evidence and recover through the backend-owned path. |
| release_projection_unavailable | release | warning | yes | The release prepared projection is unavailable. | Correct the prerequisite and retry through the owning backend workflow. |
| remote_access_not_ready | devices | warning | yes | Private remote access is not ready. | Verify Tailscale readiness and backend reachability; do not infer remote readiness from UI presentation. |
| service_unavailable | system | warning | yes | A required backend service is unavailable. | Inspect the owning dependency/readiness evidence and recover through the backend-owned path. |
| session_not_found | identity | warning | no | The requested human session is absent, expired, revoked, or no longer active. | Review the owning evidence and operator guidance before another action. |
| shutdown | system | warning | yes | The process is shutting down. | Correct the prerequisite and retry through the owning backend workflow. |
| shutdown_during_mailbox_backpressure | projections | warning | yes | Shutdown occurred while the bounded mailbox was under pressure. | Correct the prerequisite and retry through the owning backend workflow. |
| submit_failed | system | warning | yes | The work request could not be admitted. | Correct the prerequisite and retry through the owning backend workflow. |
| target_not_allowed | validation | warning | no | The requested target is outside the approved scope. | Review the owning evidence and operator guidance before another action. |
| test_bypass_explicit | rules | info | no | An explicitly test-gated policy bypass was used in the isolated test environment; it is not available in production. | Review the owning evidence and operator guidance before another action. |
| unregistered_domain | projections | warning | yes | The requested domain is not registered. | Correct the prerequisite and retry through the owning backend workflow. |
| worker_failed | security | high | yes | The worker reported a terminal failure. | Correct the prerequisite and retry through the owning backend workflow. |
| worker_start_timeout | security | warning | yes | The worker did not start the accepted work within the recovery window. | Correct the prerequisite and retry through the owning backend workflow. |
