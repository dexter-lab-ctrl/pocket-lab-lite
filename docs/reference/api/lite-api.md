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
source_fingerprint: 29f11e8b47428ef753f23cde822263398a11a5fdfef5275c21632126a49cd545
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
| 202 | Successful Response | application/json: `object` |
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
| 202 | Successful Response | application/json: `object` |
| 409 | The requested state transition conflicts with current durable state. | application/json: `PocketLabApiError` |
| 422 | Validation Error | application/json: `HTTPValidationError` |
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
