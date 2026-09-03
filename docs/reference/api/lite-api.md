---
title: "Lite API reference"
description: "Detailed source-generated FastAPI Lite HTTP operation reference."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 2599f85c02df6f88d77d4588a234274fefa36bb4d20f737af0aca8c3183cbd08
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Lite API reference

FastAPI OpenAPI is authoritative. The browser remains a same-origin client and never executes shell commands or talks directly to NATS.

<a id="get-api-lite-apps-lifecycle"></a>
## GET `/api/lite/apps/lifecycle`

- Operation ID: `get_lite_app_lifecycle_profiles_api_lite_apps_lifecycle_get`
- Summary: Get Lite App Lifecycle Profiles
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-lifecycle-app-id"></a>
## GET `/api/lite/apps/lifecycle/{app_id}`

- Operation ID: `get_lite_app_lifecycle_profile_api_lite_apps_lifecycle__app_id__get`
- Summary: Get Lite App Lifecycle Profile
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-photoprism-storage-mappings"></a>
## GET `/api/lite/apps/photoprism/storage-mappings`

- Operation ID: `get_photoprism_storage_mappings_api_lite_apps_photoprism_storage_mappings_get`
- Summary: Get Photoprism Storage Mappings
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-photoprism-storage-mappings"></a>
## POST `/api/lite/apps/photoprism/storage-mappings`

- Operation ID: `create_photoprism_storage_mapping_api_lite_apps_photoprism_storage_mappings_post`
- Summary: Create Photoprism Storage Mapping
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePhotoPrismStorageMappingRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="delete-api-lite-apps-photoprism-storage-mappings-mapping-id"></a>
## DELETE `/api/lite/apps/photoprism/storage-mappings/{mapping_id}`

- Operation ID: `delete_photoprism_storage_mapping_api_lite_apps_photoprism_storage_mappings__mapping_id__delete`
- Summary: Delete Photoprism Storage Mapping
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| mapping_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-photoprism-storage-preview"></a>
## GET `/api/lite/apps/photoprism/storage-preview`

- Operation ID: `get_photoprism_storage_preview_api_lite_apps_photoprism_storage_preview_get`
- Summary: Get Photoprism Storage Preview
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-action-history"></a>
## GET `/api/lite/apps/{app_id}/action-history`

- Operation ID: `get_lite_app_action_history_api_lite_apps__app_id__action_history_get`
- Summary: Get Lite App Action History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-actions"></a>
## GET `/api/lite/apps/{app_id}/actions`

- Operation ID: `get_lite_app_actions_api_lite_apps__app_id__actions_get`
- Summary: Get Lite App Actions
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-app-id-actions-action-id"></a>
## POST `/api/lite/apps/{app_id}/actions/{action_id}`

- Operation ID: `run_lite_app_action_api_lite_apps__app_id__actions__action_id__post`
- Summary: Run Lite App Action
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |
| action_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppActionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-backup"></a>
## GET `/api/lite/apps/{app_id}/backup`

- Operation ID: `get_lite_app_backup_status_api_lite_apps__app_id__backup_get`
- Summary: Get Lite App Backup Status
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-app-id-backup"></a>
## POST `/api/lite/apps/{app_id}/backup`

- Operation ID: `start_lite_app_backup_api_lite_apps__app_id__backup_post`
- Summary: Start Lite App Backup
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppBackupRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-app-id-backup-storage-device"></a>
## POST `/api/lite/apps/{app_id}/backup/storage-device`

- Operation ID: `start_lite_app_backup_to_storage_device_api_lite_apps__app_id__backup_storage_device_post`
- Summary: Start Lite App Backup To Storage Device
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppActionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-backups"></a>
## GET `/api/lite/apps/{app_id}/backups`

- Operation ID: `list_lite_app_backups_api_lite_apps__app_id__backups_get`
- Summary: List Lite App Backups
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-backups-backup-id-receipt"></a>
## GET `/api/lite/apps/{app_id}/backups/{backup_id}/receipt`

- Operation ID: `get_lite_app_backup_receipt_api_lite_apps__app_id__backups__backup_id__receipt_get`
- Summary: Get Lite App Backup Receipt
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-evidence"></a>
## GET `/api/lite/apps/{app_id}/evidence`

- Operation ID: `get_lite_app_evidence_api_lite_apps__app_id__evidence_get`
- Summary: Get Lite App Evidence
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-app-id-restore-preview"></a>
## POST `/api/lite/apps/{app_id}/restore/preview`

- Operation ID: `start_lite_app_restore_preview_api_lite_apps__app_id__restore_preview_post`
- Summary: Start Lite App Restore Preview
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppRestorePreviewRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-restore-previews-preview-id"></a>
## GET `/api/lite/apps/{app_id}/restore/previews/{preview_id}`

- Operation ID: `get_lite_app_restore_preview_api_lite_apps__app_id__restore_previews__preview_id__get`
- Summary: Get Lite App Restore Preview
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |
| preview_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-update"></a>
## GET `/api/lite/apps/{app_id}/update`

- Operation ID: `get_lite_app_update_status_api_lite_apps__app_id__update_get`
- Summary: Get Lite App Update Status
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-apps-app-id-update-apply"></a>
## POST `/api/lite/apps/{app_id}/update/apply`

- Operation ID: `apply_lite_app_update_api_lite_apps__app_id__update_apply_post`
- Summary: Apply Lite App Update
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppUpdateRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 409 | Successful Response | application/json: `object` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-apps-app-id-update-receipts-operation-id"></a>
## GET `/api/lite/apps/{app_id}/update/receipts/{operation_id}`

- Operation ID: `get_lite_app_update_receipt_api_lite_apps__app_id__update_receipts__operation_id__get`
- Summary: Get Lite App Update Receipt
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |
| operation_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-catalog"></a>
## GET `/api/lite/catalog`

- Operation ID: `get_lite_catalog_api_lite_catalog_get`
- Summary: Get Lite Catalog
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-catalog-install"></a>
## POST `/api/lite/catalog/install`

- Operation ID: `install_lite_catalog_item_api_lite_catalog_install_post`
- Summary: Install Lite Catalog Item
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteCatalogInstallRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-catalog-remove"></a>
## POST `/api/lite/catalog/remove`

- Operation ID: `remove_lite_catalog_item_api_lite_catalog_remove_post`
- Summary: Remove Lite Catalog Item
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteCatalogRemoveRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 501 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-commands-history"></a>
## GET `/api/lite/commands/history`

- Operation ID: `get_lite_command_history_api_lite_commands_history_get`
- Summary: Get Lite Command History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| entity_type | query | no | `string` |
| entity_id | query | no | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-devices-device-id"></a>
## GET `/api/lite/devices/{device_id}`

- Operation ID: `get_lite_device_details_api_lite_devices__device_id__get`
- Summary: Get Lite Device Details
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-devices-device-id-health"></a>
## GET `/api/lite/devices/{device_id}/health`

- Operation ID: `get_lite_device_health_api_lite_devices__device_id__health_get`
- Summary: Get Lite Device Health
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-devices-device-id-health-history"></a>
## GET `/api/lite/devices/{device_id}/health/history`

- Operation ID: `get_lite_device_health_history_api_lite_devices__device_id__health_history_get`
- Summary: Get Lite Device Health History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-devices-device-id-history"></a>
## GET `/api/lite/devices/{device_id}/history`

- Operation ID: `get_lite_device_lifecycle_history_api_lite_devices__device_id__history_get`
- Summary: Get Lite Device Lifecycle History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-devices-device-id-removal-assessment"></a>
## GET `/api/lite/devices/{device_id}/removal-assessment`

- Operation ID: `get_lite_device_removal_assessment_api_lite_devices__device_id__removal_assessment_get`
- Summary: Get Lite Device Removal Assessment
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-diagnostics-frontend-lifecycle"></a>
## POST `/api/lite/diagnostics/frontend-lifecycle`

- Operation ID: `record_frontend_lifecycle_diagnostics_api_lite_diagnostics_frontend_lifecycle_post`
- Summary: Record Frontend Lifecycle Diagnostics
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteLifecycleDiagnosticsRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-diagnostics-frontend-lifecycle-challenge"></a>
## GET `/api/lite/diagnostics/frontend-lifecycle/challenge`

- Operation ID: `get_frontend_lifecycle_diagnostics_challenge_api_lite_diagnostics_frontend_lifecycle_challenge_get`
- Summary: Get Frontend Lifecycle Diagnostics Challenge
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-diagnostics-runtime"></a>
## GET `/api/lite/diagnostics/runtime`

- Operation ID: `get_lite_runtime_diagnostics_api_lite_diagnostics_runtime_get`
- Summary: Get Lite Runtime Diagnostics
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-diagnostics-runtime-full"></a>
## GET `/api/lite/diagnostics/runtime/full`

- Operation ID: `get_lite_runtime_diagnostics_full_api_lite_diagnostics_runtime_full_get`
- Summary: Get Lite Runtime Diagnostics Full
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-access"></a>
## GET `/api/lite/enterprise/access`

- Operation ID: `enterprise_access_api_lite_enterprise_access_get`
- Summary: Enterprise Access
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity"></a>
## GET `/api/lite/enterprise/identity`

- Operation ID: `enterprise_identity_api_lite_enterprise_identity_get`
- Summary: Enterprise Identity
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-enrollment-consume"></a>
## POST `/api/lite/enterprise/identity/enrollment/consume`

- Operation ID: `legacy_person_claim_consume_api_lite_enterprise_identity_enrollment_consume_post`
- Summary: Legacy Person Claim Consume
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-enrollment-passkey-options"></a>
## POST `/api/lite/enterprise/identity/enrollment/passkey/options`

- Operation ID: `legacy_person_claim_passkey_options_api_lite_enterprise_identity_enrollment_passkey_options_post`
- Summary: Legacy Person Claim Passkey Options
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-enrollment-passkey-verify"></a>
## POST `/api/lite/enterprise/identity/enrollment/passkey/verify`

- Operation ID: `legacy_person_claim_passkey_verify_api_lite_enterprise_identity_enrollment_passkey_verify_post`
- Summary: Legacy Person Claim Passkey Verify
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-enrollment-status"></a>
## GET `/api/lite/enterprise/identity/enrollment/status`

- Operation ID: `legacy_person_claim_status_api_lite_enterprise_identity_enrollment_status_get`
- Summary: Legacy Person Claim Status
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-members"></a>
## GET `/api/lite/enterprise/identity/members`

- Operation ID: `enterprise_members_api_lite_enterprise_identity_members_get`
- Summary: Enterprise Members
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="put-api-lite-enterprise-identity-members-human-id"></a>
## PUT `/api/lite/enterprise/identity/members/{human_id}`

- Operation ID: `update_enterprise_member_api_lite_enterprise_identity_members__human_id__put`
- Summary: Update Enterprise Member
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `EnterpriseMembershipRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="put-api-lite-enterprise-identity-mode"></a>
## PUT `/api/lite/enterprise/identity/mode`

- Operation ID: `update_enterprise_mode_api_lite_enterprise_identity_mode_put`
- Summary: Update Enterprise Mode
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `EnterpriseModeRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-mode-preview"></a>
## GET `/api/lite/enterprise/identity/mode/preview`

- Operation ID: `preview_enterprise_mode_api_lite_enterprise_identity_mode_preview_get`
- Summary: Preview Enterprise Mode
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| enabled | query | yes | `boolean` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-passkeys-login-options"></a>
## POST `/api/lite/enterprise/identity/passkeys/login/options`

- Operation ID: `enterprise_passkey_login_options_api_lite_enterprise_identity_passkeys_login_options_post`
- Summary: Enterprise Passkey Login Options
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `HumanPasskeyLoginOptionsRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-passkeys-login-verify"></a>
## POST `/api/lite/enterprise/identity/passkeys/login/verify`

- Operation ID: `enterprise_passkey_login_verify_api_lite_enterprise_identity_passkeys_login_verify_post`
- Summary: Enterprise Passkey Login Verify
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `HumanPasskeyLoginVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-people"></a>
## GET `/api/lite/enterprise/identity/people`

- Operation ID: `enterprise_people_api_lite_enterprise_identity_people_get`
- Summary: Enterprise People
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people"></a>
## POST `/api/lite/enterprise/identity/people`

- Operation ID: `create_enterprise_person_api_lite_enterprise_identity_people_post`
- Summary: Create Enterprise Person
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `PersonCreateRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="delete-api-lite-enterprise-identity-people-human-id"></a>
## DELETE `/api/lite/enterprise/identity/people/{human_id}`

- Operation ID: `remove_enterprise_person_api_lite_enterprise_identity_people__human_id__delete`
- Summary: Remove Enterprise Person
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-people-human-id"></a>
## GET `/api/lite/enterprise/identity/people/{human_id}`

- Operation ID: `enterprise_person_api_lite_enterprise_identity_people__human_id__get`
- Summary: Enterprise Person
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-invite"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/invite`

- Operation ID: `legacy_enterprise_person_invite_api_lite_enterprise_identity_people__human_id__invite_post`
- Summary: Legacy Enterprise Person Invite
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-passkey-options"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/passkey/options`

- Operation ID: `enterprise_person_managed_passkey_options_api_lite_enterprise_identity_people__human_id__passkey_options_post`
- Summary: Enterprise Person Managed Passkey Options
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-passkey-verify"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/passkey/verify`

- Operation ID: `enterprise_person_managed_passkey_verify_api_lite_enterprise_identity_people__human_id__passkey_verify_post`
- Summary: Enterprise Person Managed Passkey Verify
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `PersonPasskeyVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-reactivate"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/reactivate`

- Operation ID: `reactivate_enterprise_person_api_lite_enterprise_identity_people__human_id__reactivate_post`
- Summary: Reactivate Enterprise Person
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-reset-access"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/reset-access`

- Operation ID: `reset_enterprise_person_access_api_lite_enterprise_identity_people__human_id__reset_access_post`
- Summary: Reset Enterprise Person Access
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-identity-people-human-id-suspend"></a>
## POST `/api/lite/enterprise/identity/people/{human_id}/suspend`

- Operation ID: `suspend_enterprise_person_api_lite_enterprise_identity_people__human_id__suspend_post`
- Summary: Suspend Enterprise Person
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| human_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-identity-self"></a>
## GET `/api/lite/enterprise/identity/self`

- Operation ID: `enterprise_identity_self_api_lite_enterprise_identity_self_get`
- Summary: Enterprise Identity Self
- Deprecated: no
- Tags: `lite-enterprise-identity`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-activations"></a>
## POST `/api/lite/enterprise/rules/activations`

- Operation ID: `activate_api_lite_enterprise_rules_activations_post`
- Summary: Activate
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `ActivationRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-activations-operation-id"></a>
## GET `/api/lite/enterprise/rules/activations/{operation_id}`

- Operation ID: `operation_api_lite_enterprise_rules_activations__operation_id__get`
- Summary: Operation
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| operation_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-activations-operation-id-resolve"></a>
## POST `/api/lite/enterprise/rules/activations/{operation_id}/resolve`

- Operation ID: `resolve_activation_api_lite_enterprise_rules_activations__operation_id__resolve_post`
- Summary: Resolve Activation
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| operation_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-analysis"></a>
## GET `/api/lite/enterprise/rules/analysis`

- Operation ID: `analysis_api_lite_enterprise_rules_analysis_get`
- Summary: Analysis
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| revision_id | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-approvals"></a>
## GET `/api/lite/enterprise/rules/approvals`

- Operation ID: `approvals_api_lite_enterprise_rules_approvals_get`
- Summary: Approvals
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-approvals-approval-id"></a>
## GET `/api/lite/enterprise/rules/approvals/{approval_id}`

- Operation ID: `approval_api_lite_enterprise_rules_approvals__approval_id__get`
- Summary: Approval
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| approval_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-approvals-approval-id"></a>
## POST `/api/lite/enterprise/rules/approvals/{approval_id}`

- Operation ID: `transition_approval_api_lite_enterprise_rules_approvals__approval_id__post`
- Summary: Transition Approval
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| approval_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `ApprovalTransitionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-decisions"></a>
## GET `/api/lite/enterprise/rules/decisions`

- Operation ID: `decisions_api_lite_enterprise_rules_decisions_get`
- Summary: Decisions
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| action_id | query | no | `string` |
| allowed | query | no | `boolean` |
| reason_code | query | no | `string` |
| policy_revision | query | no | `string` |
| target_type | query | no | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `integer` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-decisions-decision-id"></a>
## GET `/api/lite/enterprise/rules/decisions/{decision_id}`

- Operation ID: `decision_api_lite_enterprise_rules_decisions__decision_id__get`
- Summary: Decision
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| decision_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-exceptions"></a>
## GET `/api/lite/enterprise/rules/exceptions`

- Operation ID: `exceptions_api_lite_enterprise_rules_exceptions_get`
- Summary: Exceptions
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-exceptions"></a>
## POST `/api/lite/enterprise/rules/exceptions`

- Operation ID: `create_exception_api_lite_enterprise_rules_exceptions_post`
- Summary: Create Exception
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `TemporaryExceptionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-exceptions-exception-id-revoke"></a>
## POST `/api/lite/enterprise/rules/exceptions/{exception_id}/revoke`

- Operation ID: `revoke_exception_api_lite_enterprise_rules_exceptions__exception_id__revoke_post`
- Summary: Revoke Exception
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| exception_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-health"></a>
## GET `/api/lite/enterprise/rules/health`

- Operation ID: `health_api_lite_enterprise_rules_health_get`
- Summary: Health
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-revisions"></a>
## GET `/api/lite/enterprise/rules/revisions`

- Operation ID: `revisions_api_lite_enterprise_rules_revisions_get`
- Summary: Revisions
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-revisions"></a>
## POST `/api/lite/enterprise/rules/revisions`

- Operation ID: `create_revision_api_lite_enterprise_rules_revisions_post`
- Summary: Create Revision
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `RevisionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-revisions-left-revision-id-compare-right-revision-id"></a>
## GET `/api/lite/enterprise/rules/revisions/{left_revision_id}/compare/{right_revision_id}`

- Operation ID: `compare_api_lite_enterprise_rules_revisions__left_revision_id__compare__right_revision_id__get`
- Summary: Compare
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| left_revision_id | path | yes | `string` |
| right_revision_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-revisions-revision-id"></a>
## GET `/api/lite/enterprise/rules/revisions/{revision_id}`

- Operation ID: `revision_api_lite_enterprise_rules_revisions__revision_id__get`
- Summary: Revision
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| revision_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-rollbacks"></a>
## POST `/api/lite/enterprise/rules/rollbacks`

- Operation ID: `rollback_api_lite_enterprise_rules_rollbacks_post`
- Summary: Rollback
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-enterprise-rules-simulations"></a>
## POST `/api/lite/enterprise/rules/simulations`

- Operation ID: `simulate_api_lite_enterprise_rules_simulations_post`
- Summary: Simulate
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `SimulationRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-enterprise-rules-templates"></a>
## GET `/api/lite/enterprise/rules/templates`

- Operation ID: `templates_api_lite_enterprise_rules_templates_get`
- Summary: Templates
- Deprecated: no
- Tags: `lite-enterprise-rules`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-events"></a>
## GET `/api/lite/events`

- Operation ID: `get_lite_revision_events_api_lite_events_get`
- Summary: Get Lite Revision Events
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Server-Sent Events stream. | text/event-stream: `string` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet"></a>
## GET `/api/lite/fleet`

- Operation ID: `get_lite_fleet_api_lite_fleet_get`
- Summary: Get Lite Fleet
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-add-device"></a>
## POST `/api/lite/fleet/add-device`

- Operation ID: `add_lite_device_api_lite_fleet_add_device_post`
- Summary: Add Lite Device
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAddDeviceRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-agent-bootstrap-blocked"></a>
## POST `/api/lite/fleet/agent/bootstrap-blocked`

- Operation ID: `lite_fleet_agent_bootstrap_blocked_api_lite_fleet_agent_bootstrap_blocked_post`
- Summary: Lite Fleet Agent Bootstrap Blocked
- Deprecated: no
- Tags: `fleet`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`object`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-agent-bootstrap-env"></a>
## POST `/api/lite/fleet/agent/bootstrap.env`

- Operation ID: `lite_fleet_agent_bootstrap_env_api_lite_fleet_agent_bootstrap_env_post`
- Summary: Lite Fleet Agent Bootstrap Env
- Deprecated: no
- Tags: `fleet`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`object`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet-agent-bootstrap-sh"></a>
## GET `/api/lite/fleet/agent/bootstrap.sh`

- Operation ID: `lite_fleet_agent_bootstrap_script_api_lite_fleet_agent_bootstrap_sh_get`
- Summary: Lite Fleet Agent Bootstrap Script
- Deprecated: no
- Tags: `fleet`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| role | query | no | `string` |
| token | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Token-gated Pocket Lab Lite bootstrap shell script. | text/x-shellscript: `string` |
| 400 | Bootstrap parameters or invite token are missing or invalid. | application/json: `PocketLabApiError` |
| 403 | The invite or bootstrap request is not authorized. | application/json: `PocketLabApiError` |
| 410 | The invite has expired, was revoked, or was already used. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="put-api-lite-fleet-devices-device-id-display-model"></a>
## PUT `/api/lite/fleet/devices/{device_id}/display-model`

- Operation ID: `update_lite_device_display_model_api_lite_fleet_devices__device_id__display_model_put`
- Summary: Update Lite Device Display Model
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteDeviceDisplayModelRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet-devices-device-id-recovery-history"></a>
## GET `/api/lite/fleet/devices/{device_id}/recovery-history`

- Operation ID: `get_lite_device_recovery_history_api_lite_fleet_devices__device_id__recovery_history_get`
- Summary: Get Lite Device Recovery History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| device_id | path | yes | `string` |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-devices-node-id-restart-agent"></a>
## POST `/api/lite/fleet/devices/{node_id}/restart-agent`

- Operation ID: `restart_lite_fleet_agent_api_lite_fleet_devices__node_id__restart_agent_post`
- Summary: Restart Lite Fleet Agent
- Deprecated: no
- Tags: `fleet`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| node_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`object`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet-devices-node-id-restart-agent-status"></a>
## GET `/api/lite/fleet/devices/{node_id}/restart-agent/status`

- Operation ID: `lite_fleet_agent_restart_status_api_lite_fleet_devices__node_id__restart_agent_status_get`
- Summary: Lite Fleet Agent Restart Status
- Deprecated: no
- Tags: `fleet`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| node_id | path | yes | `string` |
| command_id | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet-health-summary"></a>
## GET `/api/lite/fleet/health-summary`

- Operation ID: `get_lite_fleet_health_summary_api_lite_fleet_health_summary_get`
- Summary: Get Lite Fleet Health Summary
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-fleet-invites-latest"></a>
## GET `/api/lite/fleet/invites/latest`

- Operation ID: `get_latest_lite_fleet_invite_api_lite_fleet_invites_latest_get`
- Summary: Get Latest Lite Fleet Invite
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-invites-invite-id-revoke"></a>
## POST `/api/lite/fleet/invites/{invite_id}/revoke`

- Operation ID: `revoke_lite_fleet_invite_api_lite_fleet_invites__invite_id__revoke_post`
- Summary: Revoke Lite Fleet Invite
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| invite_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteInviteRevokeRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-fleet-remove-device"></a>
## POST `/api/lite/fleet/remove-device`

- Operation ID: `remove_lite_device_api_lite_fleet_remove_device_post`
- Summary: Remove Lite Device
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteRemoveDeviceRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-identity"></a>
## GET `/api/lite/identity`

- Operation ID: `get_lite_identity_api_lite_identity_get`
- Summary: Get Lite Identity
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-login"></a>
## POST `/api/lite/identity/login`

- Operation ID: `login_lite_identity_api_lite_identity_login_post`
- Summary: Login Lite Identity
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteIdentityLoginRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-logout"></a>
## POST `/api/lite/identity/logout`

- Operation ID: `logout_lite_identity_api_lite_identity_logout_post`
- Summary: Logout Lite Identity
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-owner-claim"></a>
## POST `/api/lite/identity/owner-claim`

- Operation ID: `issue_lite_owner_claim_api_lite_identity_owner_claim_post`
- Summary: Issue Lite Owner Claim
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteOwnerClaimIssueRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-owner-claim-consume"></a>
## POST `/api/lite/identity/owner-claim/consume`

- Operation ID: `consume_lite_owner_claim_api_lite_identity_owner_claim_consume_post`
- Summary: Consume Lite Owner Claim
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteOwnerClaimConsumeRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-owner-claim-passkey-options"></a>
## POST `/api/lite/identity/owner-claim/passkey/options`

- Operation ID: `owner_claim_passkey_options_api_lite_identity_owner_claim_passkey_options_post`
- Summary: Owner Claim Passkey Options
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteOwnerClaimPasskeyOptionsRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-owner-claim-passkey-verify"></a>
## POST `/api/lite/identity/owner-claim/passkey/verify`

- Operation ID: `owner_claim_passkey_verify_api_lite_identity_owner_claim_passkey_verify_post`
- Summary: Owner Claim Passkey Verify
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-identity-owner-claim-status"></a>
## GET `/api/lite/identity/owner-claim/status`

- Operation ID: `owner_claim_status_api_lite_identity_owner_claim_status_get`
- Summary: Owner Claim Status
- Deprecated: no
- Tags: `lite-identity-p1`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-passkeys-login-options"></a>
## POST `/api/lite/identity/passkeys/login/options`

- Operation ID: `passkey_login_options_api_lite_identity_passkeys_login_options_post`
- Summary: Passkey Login Options
- Deprecated: no
- Tags: `lite-identity-p1`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-passkeys-login-verify"></a>
## POST `/api/lite/identity/passkeys/login/verify`

- Operation ID: `passkey_login_verify_api_lite_identity_passkeys_login_verify_post`
- Summary: Passkey Login Verify
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-passkeys-registration-options"></a>
## POST `/api/lite/identity/passkeys/registration/options`

- Operation ID: `passkey_registration_options_api_lite_identity_passkeys_registration_options_post`
- Summary: Passkey Registration Options
- Deprecated: no
- Tags: `lite-identity-p1`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-passkeys-registration-verify"></a>
## POST `/api/lite/identity/passkeys/registration/verify`

- Operation ID: `passkey_registration_verify_api_lite_identity_passkeys_registration_verify_post`
- Summary: Passkey Registration Verify
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="delete-api-lite-identity-passkeys-credential-id"></a>
## DELETE `/api/lite/identity/passkeys/{credential_id}`

- Operation ID: `revoke_lite_passkey_api_lite_identity_passkeys__credential_id__delete`
- Summary: Revoke Lite Passkey
- Deprecated: no
- Tags: `lite-identity-p1`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| credential_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="put-api-lite-identity-passkeys-credential-id"></a>
## PUT `/api/lite/identity/passkeys/{credential_id}`

- Operation ID: `rename_lite_passkey_api_lite_identity_passkeys__credential_id__put`
- Summary: Rename Lite Passkey
- Deprecated: no
- Tags: `lite-identity-p1`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| credential_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyRenameRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-password"></a>
## POST `/api/lite/identity/password`

- Operation ID: `change_lite_identity_password_api_lite_identity_password_post`
- Summary: Change Lite Identity Password
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteIdentityPasswordRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-recover"></a>
## POST `/api/lite/identity/recover`

- Operation ID: `recover_lite_identity_api_lite_identity_recover_post`
- Summary: Recover Lite Identity
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteIdentityRecoveryRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-recovery-regenerate"></a>
## POST `/api/lite/identity/recovery/regenerate`

- Operation ID: `regenerate_lite_identity_recovery_api_lite_identity_recovery_regenerate_post`
- Summary: Regenerate Lite Identity Recovery
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-rotate"></a>
## POST `/api/lite/identity/rotate`

- Operation ID: `rotate_lite_identity_api_lite_identity_rotate_post`
- Summary: Rotate Lite Identity
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteIdentityRotateRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 410 | Legacy Identity secret rotation is retired; use the human Identity password flow. | application/json: `object` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-sessions-revoke-others"></a>
## POST `/api/lite/identity/sessions/revoke-others`

- Operation ID: `revoke_other_lite_identity_sessions_api_lite_identity_sessions_revoke_others_post`
- Summary: Revoke Other Lite Identity Sessions
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="delete-api-lite-identity-sessions-session-id"></a>
## DELETE `/api/lite/identity/sessions/{session_id}`

- Operation ID: `revoke_lite_identity_session_api_lite_identity_sessions__session_id__delete`
- Summary: Revoke Lite Identity Session
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| session_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-setup"></a>
## POST `/api/lite/identity/setup`

- Operation ID: `setup_lite_identity_api_lite_identity_setup_post`
- Summary: Setup Lite Identity
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteIdentitySetupRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 201 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-step-up-options"></a>
## POST `/api/lite/identity/step-up/options`

- Operation ID: `passkey_step_up_options_api_lite_identity_step_up_options_post`
- Summary: Passkey Step Up Options
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyStepUpRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-identity-step-up-verify"></a>
## POST `/api/lite/identity/step-up/verify`

- Operation ID: `passkey_step_up_verify_api_lite_identity_step_up_verify_post`
- Summary: Passkey Step Up Verify
- Deprecated: no
- Tags: `lite-identity-p1`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePasskeyStepUpVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-policy"></a>
## GET `/api/lite/policy`

- Operation ID: `get_lite_policy_api_lite_policy_get`
- Summary: Get Lite Policy
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-policy-apply"></a>
## POST `/api/lite/policy/apply`

- Operation ID: `apply_lite_policy_api_lite_policy_apply_post`
- Summary: Apply Lite Policy
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LitePolicyApplyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 410 | Legacy policy mutation is retired; Rules policy activation is repository-owned. | application/json: `object` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-policy-decisions-decision-id"></a>
## GET `/api/lite/policy/decisions/{decision_id}`

- Operation ID: `get_lite_policy_decision_api_lite_policy_decisions__decision_id__get`
- Summary: Get Lite Policy Decision
- Deprecated: no
- Tags: `lite-identity-p1`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| decision_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-policy-templates"></a>
## GET `/api/lite/policy/templates`

- Operation ID: `get_lite_policy_templates_api_lite_policy_templates_get`
- Summary: Get Lite Policy Templates
- Deprecated: no
- Tags: `lite-identity-p1`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery"></a>
## GET `/api/lite/recovery`

- Operation ID: `get_lite_recovery_api_lite_recovery_get`
- Summary: Get Lite Recovery
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-apps"></a>
## GET `/api/lite/recovery/apps`

- Operation ID: `get_lite_recovery_apps_api_lite_recovery_apps_get`
- Summary: Get Lite Recovery Apps
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-apps-app-id"></a>
## GET `/api/lite/recovery/apps/{app_id}`

- Operation ID: `get_lite_recovery_app_api_lite_recovery_apps__app_id__get`
- Summary: Get Lite Recovery App
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-apps-app-id-backup"></a>
## POST `/api/lite/recovery/apps/{app_id}/backup`

- Operation ID: `backup_lite_app_api_lite_recovery_apps__app_id__backup_post`
- Summary: Backup Lite App
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppBackupRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-apps-app-id-backup-targets"></a>
## GET `/api/lite/recovery/apps/{app_id}/backup-targets`

- Operation ID: `get_lite_recovery_app_backup_targets_api_lite_recovery_apps__app_id__backup_targets_get`
- Summary: Get Lite Recovery App Backup Targets
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-apps-app-id-backup-to-target"></a>
## POST `/api/lite/recovery/apps/{app_id}/backup-to-target`

- Operation ID: `backup_lite_app_to_target_api_lite_recovery_apps__app_id__backup_to_target_post`
- Summary: Backup Lite App To Target
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppActionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-apps-app-id-restore"></a>
## POST `/api/lite/recovery/apps/{app_id}/restore`

- Operation ID: `restore_lite_app_api_lite_recovery_apps__app_id__restore_post`
- Summary: Restore Lite App
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppRestoreRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 501 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-apps-app-id-restore-preview"></a>
## POST `/api/lite/recovery/apps/{app_id}/restore/preview`

- Operation ID: `preview_lite_app_restore_api_lite_recovery_apps__app_id__restore_preview_post`
- Summary: Preview Lite App Restore
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteAppRestorePreviewRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-backup"></a>
## POST `/api/lite/recovery/backup`

- Operation ID: `backup_lite_api_lite_recovery_backup_post`
- Summary: Backup Lite
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteBackupRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-backup-targets"></a>
## GET `/api/lite/recovery/backup-targets`

- Operation ID: `get_lite_backup_targets_api_lite_recovery_backup_targets_get`
- Summary: Get Lite Backup Targets
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-backups"></a>
## GET `/api/lite/recovery/backups`

- Operation ID: `list_lite_backups_api_lite_recovery_backups_get`
- Summary: List Lite Backups
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-backups-backup-id"></a>
## GET `/api/lite/recovery/backups/{backup_id}`

- Operation ID: `get_lite_backup_api_lite_recovery_backups__backup_id__get`
- Summary: Get Lite Backup
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-backups-backup-id-verify"></a>
## POST `/api/lite/recovery/backups/{backup_id}/verify`

- Operation ID: `verify_lite_backup_api_lite_recovery_backups__backup_id__verify_post`
- Summary: Verify Lite Backup
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteBackupVerifyRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-database"></a>
## GET `/api/lite/recovery/database`

- Operation ID: `get_lite_database_recovery_api_lite_recovery_database_get`
- Summary: Get Lite Database Recovery
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-database-backup"></a>
## POST `/api/lite/recovery/database/backup`

- Operation ID: `backup_lite_database_api_lite_recovery_database_backup_post`
- Summary: Backup Lite Database
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteDatabaseBackupRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-database-backups"></a>
## GET `/api/lite/recovery/database/backups`

- Operation ID: `list_lite_database_backups_api_lite_recovery_database_backups_get`
- Summary: List Lite Database Backups
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-database-backups-backup-id"></a>
## GET `/api/lite/recovery/database/backups/{backup_id}`

- Operation ID: `get_lite_database_backup_api_lite_recovery_database_backups__backup_id__get`
- Summary: Get Lite Database Backup
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-database-backups-backup-id-preview"></a>
## POST `/api/lite/recovery/database/backups/{backup_id}/preview`

- Operation ID: `preview_lite_database_restore_api_lite_recovery_database_backups__backup_id__preview_post`
- Summary: Preview Lite Database Restore
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-database-backups-backup-id-restore"></a>
## POST `/api/lite/recovery/database/backups/{backup_id}/restore`

- Operation ID: `restore_lite_database_api_lite_recovery_database_backups__backup_id__restore_post`
- Summary: Restore Lite Database
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteDatabaseRestoreRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-database-backups-backup-id-verify"></a>
## POST `/api/lite/recovery/database/backups/{backup_id}/verify`

- Operation ID: `verify_lite_database_backup_api_lite_recovery_database_backups__backup_id__verify_post`
- Summary: Verify Lite Database Backup
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-database-restore-previews-preview-id"></a>
## GET `/api/lite/recovery/database/restore/previews/{preview_id}`

- Operation ID: `get_lite_database_restore_preview_api_lite_recovery_database_restore_previews__preview_id__get`
- Summary: Get Lite Database Restore Preview
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| preview_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-database-restore-restore-id"></a>
## GET `/api/lite/recovery/database/restore/{restore_id}`

- Operation ID: `get_lite_database_restore_run_api_lite_recovery_database_restore__restore_id__get`
- Summary: Get Lite Database Restore Run
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| restore_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-details"></a>
## GET `/api/lite/recovery/details`

- Operation ID: `get_lite_recovery_details_api_lite_recovery_details_get`
- Summary: Get Lite Recovery Details
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-maintenance"></a>
## GET `/api/lite/recovery/maintenance`

- Operation ID: `get_lite_recovery_maintenance_api_lite_recovery_maintenance_get`
- Summary: Get Lite Recovery Maintenance
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-maintenance-checkpoint"></a>
## POST `/api/lite/recovery/maintenance/checkpoint`

- Operation ID: `run_lite_recovery_checkpoint_api_lite_recovery_maintenance_checkpoint_post`
- Summary: Run Lite Recovery Checkpoint
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteCheckpointRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-maintenance-retention"></a>
## POST `/api/lite/recovery/maintenance/retention`

- Operation ID: `run_lite_recovery_retention_api_lite_recovery_maintenance_retention_post`
- Summary: Run Lite Recovery Retention
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteRetentionRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-operations"></a>
## GET `/api/lite/recovery/operations`

- Operation ID: `get_lite_recovery_operation_history_api_lite_recovery_operations_get`
- Summary: Get Lite Recovery Operation History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-receipts-backup-id"></a>
## GET `/api/lite/recovery/receipts/{backup_id}`

- Operation ID: `get_lite_backup_receipt_api_lite_recovery_receipts__backup_id__get`
- Summary: Get Lite Backup Receipt
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| backup_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-restore"></a>
## POST `/api/lite/recovery/restore`

- Operation ID: `restore_lite_api_lite_recovery_restore_post`
- Summary: Restore Lite
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteRestoreRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-restore-checkpoints-checkpoint-id"></a>
## GET `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`

- Operation ID: `get_lite_restore_checkpoint_api_lite_recovery_restore_checkpoints__checkpoint_id__get`
- Summary: Get Lite Restore Checkpoint
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| checkpoint_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-recovery-restore-preview"></a>
## POST `/api/lite/recovery/restore/preview`

- Operation ID: `preview_lite_restore_api_lite_recovery_restore_preview_post`
- Summary: Preview Lite Restore
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | `LiteRestorePreviewRequest` | yes |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-restore-previews-preview-id"></a>
## GET `/api/lite/recovery/restore/previews/{preview_id}`

- Operation ID: `get_lite_restore_preview_api_lite_recovery_restore_previews__preview_id__get`
- Summary: Get Lite Restore Preview
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| preview_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-restore-runs-restore-id"></a>
## GET `/api/lite/recovery/restore/runs/{restore_id}`

- Operation ID: `get_lite_restore_run_api_lite_recovery_restore_runs__restore_id__get`
- Summary: Get Lite Restore Run
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| restore_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-recovery-summary"></a>
## GET `/api/lite/recovery/summary`

- Operation ID: `get_lite_recovery_summary_api_lite_recovery_summary_get`
- Summary: Get Lite Recovery Summary
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-release"></a>
## GET `/api/lite/release`

- Operation ID: `release_status_api_lite_release_get`
- Summary: Release Status
- Deprecated: no
- Tags: `release`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-release-apply"></a>
## POST `/api/lite/release/apply`

- Operation ID: `release_apply_api_lite_release_apply_post`
- Summary: Release Apply
- Deprecated: no
- Tags: `release`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-release-check"></a>
## POST `/api/lite/release/check`

- Operation ID: `release_check_api_lite_release_check_post`
- Summary: Release Check
- Deprecated: no
- Tags: `release`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-remote-access-readiness"></a>
## GET `/api/lite/remote-access/readiness`

- Operation ID: `get_lite_remote_access_readiness_api_lite_remote_access_readiness_get`
- Summary: Get Lite Remote Access Readiness
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-revisions"></a>
## GET `/api/lite/revisions`

- Operation ID: `get_lite_domain_revisions_api_lite_revisions_get`
- Summary: Get Lite Domain Revisions
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security"></a>
## GET `/api/lite/security`

- Operation ID: `get_lite_security_api_lite_security_get`
- Summary: Get Lite Security
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-apps"></a>
## GET `/api/lite/security/apps`

- Operation ID: `get_lite_security_apps_api_lite_security_apps_get`
- Summary: Get Lite Security Apps
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-apps-app-id"></a>
## GET `/api/lite/security/apps/{app_id}`

- Operation ID: `get_lite_security_app_api_lite_security_apps__app_id__get`
- Summary: Get Lite Security App
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-security-apps-app-id-check"></a>
## POST `/api/lite/security/apps/{app_id}/check`

- Operation ID: `check_lite_security_app_api_lite_security_apps__app_id__check_post`
- Summary: Check Lite Security App
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| app_id | path | yes | `string` |

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`LiteAppSecurityCheckRequest`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-security-check"></a>
## POST `/api/lite/security/check`

- Operation ID: `check_lite_security_api_lite_security_check_post`
- Summary: Check Lite Security
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`LiteSecurityScanRequest`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-details-run-id"></a>
## GET `/api/lite/security/details/{run_id}`

- Operation ID: `get_lite_security_details_api_lite_security_details__run_id__get`
- Summary: Get Lite Security Details
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| run_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-events"></a>
## GET `/api/lite/security/events`

- Operation ID: `get_lite_security_events_api_lite_security_events_get`
- Summary: Get Lite Security Events
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Server-Sent Events stream. | text/event-stream: `string` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-evidence-run-id"></a>
## GET `/api/lite/security/evidence/{run_id}`

- Operation ID: `get_lite_security_evidence_api_lite_security_evidence__run_id__get`
- Summary: Get Lite Security Evidence
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| run_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-evidence-run-id-summary"></a>
## GET `/api/lite/security/evidence/{run_id}/summary`

- Operation ID: `get_lite_security_evidence_summary_api_lite_security_evidence__run_id__summary_get`
- Summary: Get Lite Security Evidence Summary
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| run_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-freshness"></a>
## GET `/api/lite/security/freshness`

- Operation ID: `get_lite_security_freshness_api_lite_security_freshness_get`
- Summary: Get Lite Security Freshness
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-history"></a>
## GET `/api/lite/security/history`

- Operation ID: `get_lite_security_history_api_lite_security_history_get`
- Summary: Get Lite Security History
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| limit | query | no | `integer` |
| cursor | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The supplied opaque cursor is invalid or stale. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-profiles-profile"></a>
## GET `/api/lite/security/profiles/{profile}`

- Operation ID: `get_lite_security_profile_api_lite_security_profiles__profile__get`
- Summary: Get Lite Security Profile
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| profile | path | yes | `string` |
| app_id | query | no | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 400 | The selected Security profile requires an app identifier or contains invalid parameters. | application/json: `PocketLabApiError` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-progress"></a>
## GET `/api/lite/security/progress`

- Operation ID: `get_lite_security_progress_api_lite_security_progress_get`
- Summary: Get Lite Security Progress
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-runs-run-id"></a>
## GET `/api/lite/security/runs/{run_id}`

- Operation ID: `get_lite_security_run_api_lite_security_runs__run_id__get`
- Summary: Get Lite Security Run
- Deprecated: no
- Tags: `lite`

### Parameters

| Name | Location | Required | Schema |
| --- | --- | --- | --- |
| run_id | path | yes | `string` |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 404 | The requested resource is not available. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="post-api-lite-security-scan"></a>
## POST `/api/lite/security/scan`

- Operation ID: `scan_lite_security_api_lite_security_scan_post`
- Summary: Scan Lite Security
- Deprecated: no
- Tags: `lite`

### Request body

| Content type | Schema | Required |
| --- | --- | --- |
| application/json | anyOf(`LiteSecurityScanRequest`, `null`) | no |

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-security-summary"></a>
## GET `/api/lite/security/summary`

- Operation ID: `get_lite_security_summary_api_lite_security_summary_get`
- Summary: Get Lite Security Summary
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-status"></a>
## GET `/api/lite/status`

- Operation ID: `get_lite_status_api_lite_status_get`
- Summary: Get Lite Status
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-activity-summary"></a>
## GET `/api/lite/system/activity-summary`

- Operation ID: `get_lite_activity_summary_api_lite_system_activity_summary_get`
- Summary: Get Lite Activity Summary
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-agent"></a>
## GET `/api/lite/system/agent`

- Operation ID: `get_lite_system_agent_api_lite_system_agent_get`
- Summary: Get Lite System Agent
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-health"></a>
## GET `/api/lite/system/health`

- Operation ID: `get_lite_system_health_api_lite_system_health_get`
- Summary: Get Lite System Health
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-nats-readiness"></a>
## GET `/api/lite/system/nats-readiness`

- Operation ID: `get_lite_nats_readiness_api_lite_system_nats_readiness_get`
- Summary: Get Lite Nats Readiness
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-processes"></a>
## GET `/api/lite/system/processes`

- Operation ID: `get_lite_system_processes_api_lite_system_processes_get`
- Summary: Get Lite System Processes
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-sqlite-health"></a>
## GET `/api/lite/system/sqlite-health`

- Operation ID: `get_lite_sqlite_health_api_lite_system_sqlite_health_get`
- Summary: Get Lite Sqlite Health
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-storage-pressure"></a>
## GET `/api/lite/system/storage-pressure`

- Operation ID: `get_lite_storage_pressure_api_lite_system_storage_pressure_get`
- Summary: Get Lite Storage Pressure
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-supervisor"></a>
## GET `/api/lite/system/supervisor`

- Operation ID: `get_lite_system_supervisor_api_lite_system_supervisor_get`
- Summary: Get Lite System Supervisor
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-api-lite-system-telemetry-thresholds"></a>
## GET `/api/lite/system/telemetry-thresholds`

- Operation ID: `get_lite_telemetry_thresholds_api_lite_system_telemetry_thresholds_get`
- Summary: Get Lite Telemetry Thresholds
- Deprecated: no
- Tags: `lite`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
| 503 | Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency. | application/json: `PocketLabApiError` |

<a id="get-health"></a>
## GET `/health`

- Operation ID: `health_health_get`
- Summary: Health
- Deprecated: no
- Tags: `health`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |

<a id="get-ready"></a>
## GET `/ready`

- Operation ID: `ready_ready_get`
- Summary: Ready
- Deprecated: no
- Tags: `health`

### Responses

| Status | Description | Schema |
| --- | --- | --- |
| 200 | Successful Response | application/json: `object` |
