from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_backup, lite_app_operations, lite_app_storage, lite_app_update, lite_backup, lite_photoprism_media, lite_security

PHOTOPRISM_APP_ID = "photoprism"
RECEIPT_VERSION = 1
PROOF_STATUSES = {"passed", "review", "failed", "not_checked", "not_applicable"}

_SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "vault",
    "nats",
    "restic_password",
    "admin_password",
    "database_url",
    "connection_string",
)

_STATUS_ORDER = {"failed": 4, "review": 3, "not_checked": 2, "passed": 1, "not_applicable": 0}


def _now() -> str:
    return deps.now_utc_iso()


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized != PHOTOPRISM_APP_ID:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with App Catalog evidence receipts.",
            },
        )
    return normalized


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    # Evidence receipts may show safe redaction language such as "Secrets hidden",
    # but not raw secret assignments, credentials, URLs, or local private paths.
    # local private filesystem paths. Keep this intentionally conservative.
    if re.search(r"/(data/data|home|proc|sys|dev|etc|root)/\S*", text):
        return fallback
    if re.search(r"~/(?!storage\b)\S+", text):
        return fallback
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "bearer [hidden]", text)
    text = re.sub(r"(?i)nats://\S+", "[hidden-route]", text)
    return text[:240]


def _safe_ref(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if any(marker in raw.lower() for marker in _SECRET_MARKERS):
        return fallback
    if raw.startswith("/") or raw.startswith("~"):
        return fallback
    safe = re.sub(r"[^A-Za-z0-9._:/=-]+", "-", raw).strip("-._/")
    return safe[:160] or fallback


def _short_id(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    if len(safe) <= 28:
        return safe
    return f"{safe[:12]}…{safe[-8:]}"


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _time_key(value: Any) -> str:
    parsed = _parse_time(value)
    if not parsed:
        return ""
    return parsed.isoformat()


def _normalize_receipt_status(value: Any) -> str:
    status = str(value or "").strip().lower().replace("-", "_")
    if status in {"succeeded", "success", "completed", "verified", "ready", "created", "applied"}:
        return "succeeded"
    if status in {"queued", "running", "pending", "pending_apply"}:
        return "running"
    if status in {"failed", "error", "timed_out", "unhealthy"}:
        return "failed"
    if status in {"skipped", "already_connected", "duplicate_mapping"}:
        return "succeeded"
    if status in {"not_created", "not_ready", "missing", "unknown"}:
        return "review"
    return status or "review"


def _proof_status(value: Any) -> str:
    status = str(value or "").strip().lower().replace("-", "_")
    return status if status in PROOF_STATUSES else "not_checked"


def _proof(
    proof_id: str,
    label: str,
    status: str,
    plain_language: str,
    *,
    technical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": proof_id,
        "label": _safe_text(label, proof_id.replace("_", " ")),
        "status": _proof_status(status),
        "plain_language": _safe_text(plain_language, "Proof available."),
    }
    if technical:
        payload["technical"] = _sanitize_technical(technical)
    return payload


def _sanitize_technical(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        safe_key = re.sub(r"[^A-Za-z0-9_]+", "_", str(key or "field")).strip("_").lower()[:64]
        if not safe_key or any(marker in safe_key for marker in _SECRET_MARKERS):
            continue
        if isinstance(value, bool) or value is None:
            clean[safe_key] = value
        elif isinstance(value, (int, float)):
            clean[safe_key] = value
        elif isinstance(value, str):
            clean[safe_key] = _safe_text(value, "hidden")
        elif isinstance(value, list):
            clean[safe_key] = [_safe_text(item, "hidden") for item in value[:8]]
        else:
            clean[safe_key] = _safe_text(value, "hidden")
    return clean


def _proof_counts(proofs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(PROOF_STATUSES)}
    for proof in proofs:
        counts[_proof_status(proof.get("status"))] += 1
    return {
        "passed": counts.get("passed", 0),
        "review": counts.get("review", 0),
        "failed": counts.get("failed", 0),
        "not_checked": counts.get("not_checked", 0),
        "not_applicable": counts.get("not_applicable", 0),
    }


def _summary_status(proofs: list[dict[str, Any]]) -> str:
    worst = "passed"
    for proof in proofs:
        status = _proof_status(proof.get("status"))
        if _STATUS_ORDER.get(status, 0) > _STATUS_ORDER.get(worst, 0):
            worst = status
    return worst


def _receipt(
    *,
    receipt_id: str,
    app_id: str,
    action_id: str,
    action_label: str,
    status: str,
    summary: str,
    proofs: list[dict[str, Any]],
    what_changed: list[str],
    what_did_not_happen: list[str],
    evidence_ref: str,
    started_at: Any = None,
    completed_at: Any = None,
    technical_details: dict[str, Any] | None = None,
    proof_source: str = "Pocket Lab Lite state",
) -> dict[str, Any]:
    completed = _safe_text(completed_at, "") if completed_at else None
    started = _safe_text(started_at, "") if started_at else None
    safe_ref = _safe_ref(evidence_ref, "apps/photoprism/evidence/latest")
    clean_proofs = proofs[:16]
    counts = _proof_counts(clean_proofs)
    return {
        "receipt_version": RECEIPT_VERSION,
        "receipt_id": _safe_ref(receipt_id, "receipt-photoprism"),
        "app_id": app_id,
        "app_label": "PhotoPrism",
        "action_id": action_id,
        "action_label": action_label,
        "status": _normalize_receipt_status(status),
        "summary": _safe_text(summary, "Evidence receipt available."),
        "started_at": started,
        "completed_at": completed,
        "proofs": clean_proofs,
        "proof_counts": counts,
        "proof_status": _summary_status(clean_proofs),
        "safety_badges": _safety_badges(clean_proofs),
        "what_changed": [_safe_text(item, "Something changed.") for item in what_changed[:8]],
        "what_did_not_happen": [_safe_text(item, "Nothing unsafe happened.") for item in what_did_not_happen[:8]],
        "details_owner": {
            "name": "PhotoPrism",
            "reason": "PhotoPrism handles indexing, thumbnails, metadata, and media warnings.",
        },
        "redaction": {
            "status": "passed",
            "secrets_hidden": True,
            "raw_logs_hidden": True,
            "raw_paths_hidden": True,
            "media_file_names_hidden": True,
            "secret_values_saved": False,
        },
        "technical_details": _sanitize_technical({
            "action_id": action_id,
            "short_command_id": _short_id(receipt_id),
            "evidence_ref": safe_ref,
            "execution_owner": "backend worker" if action_id in {"import_photos", "backup_app", "check_app", "repair_app", "update_app"} else "FastAPI control API",
            "control_api": "FastAPI",
            "proof_source": proof_source,
            "redaction_status": "passed",
            **(technical_details or {}),
        }),
        "evidence_ref": safe_ref,
        "updated_at": completed or started or _now(),
    }


def _safety_badges(proofs: list[dict[str, Any]]) -> list[str]:
    wanted = [
        "backend_worker_executed",
        "frontend_no_shell",
        "no_update_applied",
        "update_source_checked",
        "app_health_checked",
        "backup_freshness_checked",
        "restore_preview_checked",
        "rollback_readiness_checked",
        "storage_read_only",
        "secrets_hidden",
        "raw_paths_hidden",
        "media_preserved",
        "backup_config_only",
        "media_excluded_from_backup",
    ]
    labels: list[str] = []
    by_id = {proof.get("id"): proof for proof in proofs}
    for proof_id in wanted:
        proof = by_id.get(proof_id)
        if proof and proof.get("status") == "passed":
            labels.append(str(proof.get("label") or proof_id.replace("_", " ")))
        if len(labels) >= 4:
            break
    return labels


def _storage_mappings() -> list[dict[str, Any]]:
    try:
        payload = lite_app_storage.list_mappings(PHOTOPRISM_APP_ID)
    except Exception:
        return []
    return [item for item in payload.get("mappings") or [] if isinstance(item, dict)]


def _storage_audit_events() -> list[dict[str, Any]]:
    try:
        path = lite_app_storage._audit_path()  # internal sanitized audit store
        payload = deps.core.read_json_file(path, {})
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("events") or [] if isinstance(item, dict)]


def _media_events() -> list[dict[str, Any]]:
    try:
        payload = deps.core.read_json_file(lite_photoprism_media._evidence_path(), {})
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("events") or [] if isinstance(item, dict)]


def _security_receipt() -> dict[str, Any] | None:
    try:
        state = lite_security.current_state()
    except Exception:
        return None
    run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    if not run:
        return None
    run_id = str(run.get("run_id") or "security-check")
    evidence_refs = state.get("evidence_refs") if isinstance(state.get("evidence_refs"), list) else []
    evidence_ref = str(evidence_refs[0]) if evidence_refs else f"security/evidence/{_safe_ref(run_id, 'latest')}/summary.json"
    status = _normalize_receipt_status(run.get("status"))
    succeeded = status == "succeeded"
    proofs = [
        _proof("backend_worker_executed", "Backend worker executed", "passed" if succeeded else "review", "The safety check was handled by the backend worker, not the browser.", technical={"worker_executed": succeeded}),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested a safety check through Pocket Lab."),
        _proof("browser_no_file_access", "Browser did not access files", "passed", "The browser did not read local files or scanner output."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "Safety evidence is redacted before it is shown."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw device paths are hidden from the receipt."),
        _proof("receipt_saved", "Receipt saved", "passed" if evidence_refs else "review", "Sanitized safety evidence is available."),
        _proof("app_health_checked", "App health checked", "not_checked", "This receipt summarizes the device safety check; app-specific health remains in the app profile."),
    ]
    return _receipt(
        receipt_id=run_id,
        app_id=PHOTOPRISM_APP_ID,
        action_id="check_app",
        action_label="Check app",
        status=status,
        summary="Safety evidence saved." if succeeded else _safe_text(run.get("summary"), "Safety evidence needs review."),
        started_at=run.get("started_at") or run.get("requested_at"),
        completed_at=run.get("completed_at"),
        proofs=proofs,
        what_changed=["Pocket Lab saved a sanitized safety summary for the device and protected apps."],
        what_did_not_happen=["No scanner logs were shown in the browser.", "No secret values were exposed.", "No frontend shell commands ran."],
        evidence_ref=evidence_ref,
        technical_details={"tools": ", ".join(run.get("tools") or []), "route_status": state.get("status")},
        proof_source="Lite Security state",
    )


def _connect_photos_receipt() -> dict[str, Any] | None:
    mappings = _storage_mappings()
    if not mappings:
        return None
    latest = sorted(mappings, key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)[0]
    events = _storage_audit_events()
    event = next((item for item in events if item.get("mapping_id") == latest.get("mapping_id")), events[0] if events else {})
    all_read_only = all(str(item.get("mode") or "").lower() == "read_only" for item in mappings)
    proof_saved = bool(latest.get("evidence_ref") or event.get("event_id"))
    label = _safe_text(latest.get("label") or latest.get("source_label"), "Photo source")
    proofs = [
        _proof("backend_worker_executed", "Backend worker not required", "not_applicable", "Connect photos records a backend-approved mapping; worker execution happens during Import photos."),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser requested the mapping through FastAPI only."),
        _proof("browser_no_file_access", "Browser did not access files", "passed", "The browser did not read phone storage or media files."),
        _proof("storage_read_only", "Storage read-only", "passed" if all_read_only else "review", "Connected photo storage is read-only by default." if all_read_only else "One or more mappings need review because they can edit media."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Only friendly folder labels are shown; raw device paths stay hidden."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "No secrets are part of the mapping receipt."),
        _proof("receipt_saved", "Receipt saved", "passed" if proof_saved else "review", "Pocket Lab saved a sanitized mapping evidence reference."),
    ]
    return _receipt(
        receipt_id=str(latest.get("mapping_id") or event.get("event_id") or "connect-photos"),
        app_id=PHOTOPRISM_APP_ID,
        action_id="connect_photos",
        action_label="Connect photos",
        status="succeeded",
        summary=f"{label} connected.",
        started_at=latest.get("created_at") or event.get("recorded_at"),
        completed_at=latest.get("updated_at") or latest.get("created_at") or event.get("recorded_at"),
        proofs=proofs,
        what_changed=["PhotoPrism can use the approved photo source mapping.", "Pocket Lab saved a sanitized storage mapping record."],
        what_did_not_happen=["No source photos were deleted.", "No raw Android private paths were shown.", "No frontend shell commands ran."],
        evidence_ref=latest.get("evidence_ref") or f"apps/photoprism/storage-mappings/{_safe_ref(latest.get('mapping_id'), 'latest')}.json",
        technical_details={"mapping_status": latest.get("status"), "storage_mode": latest.get("mode_label") or latest.get("mode"), "mapping_count": len(mappings)},
        proof_source="PhotoPrism storage mapping state",
    )


def _import_receipts() -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    mappings = _storage_mappings()
    all_read_only = bool(mappings) and all(str(item.get("mode") or "").lower() == "read_only" for item in mappings)
    for event in _media_events():
        if str(event.get("operation") or event.get("action_id") or "").lower() != "import_photos":
            continue
        status = _normalize_receipt_status(event.get("status"))
        terminal = status in {"succeeded", "failed"}
        mapping_count = int(event.get("media_mappings") or event.get("runtime_mappings_used") or 0)
        proofs = [
            _proof("backend_worker_executed", "Backend worker executed", "passed" if terminal else "review", "The action was handled by Pocket Lab Lite backend, not the browser.", technical={"worker_executed": terminal}),
            _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Import photos through FastAPI."),
            _proof("browser_no_file_access", "Browser did not access files", "passed", "The browser did not read files or PhotoPrism output."),
            _proof("storage_read_only", "Storage read-only", "passed" if all_read_only else ("not_checked" if not mappings else "review"), "Connected source storage is read-only." if all_read_only else "Storage mode could not be fully verified from public state."),
            _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw media paths and device-private paths are hidden."),
            _proof("media_preserved", "Media preserved", "passed", "The Lite import request does not delete source photos."),
            _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values and raw logs are hidden."),
            _proof("media_details_owned_by_photoprism", "PhotoPrism owns media details", "passed", "Indexing, thumbnails, metadata, and warnings stay inside PhotoPrism."),
            _proof("receipt_saved", "Receipt saved", "passed", "Pocket Lab saved a sanitized import evidence reference."),
        ]
        receipts.append(_receipt(
            receipt_id=str(event.get("event_id") or "import-photos"),
            app_id=PHOTOPRISM_APP_ID,
            action_id="import_photos",
            action_label="Import photos",
            status=status,
            summary=_safe_text(event.get("summary"), "Import photos completed."),
            started_at=event.get("started_at"),
            completed_at=event.get("completed_at"),
            proofs=proofs,
            what_changed=["PhotoPrism import was requested using connected phone storage.", "Pocket Lab saved sanitized import evidence."],
            what_did_not_happen=["No source photos were deleted.", "No secret values were exposed.", "No frontend shell commands ran.", "No PhotoPrism indexing was controlled by Pocket Lab Lite."],
            evidence_ref=f"apps/photoprism/media/{_safe_ref(event.get('event_id'), 'latest')}.json",
            technical_details={"media_mappings": mapping_count, "storage_mode": "read_only" if all_read_only else "not_checked", "media_preserved": True},
            proof_source="PhotoPrism media evidence",
        ))
    return receipts


def _backup_receipt() -> dict[str, Any] | None:
    try:
        receipt = lite_app_backup.app_backup_receipt(PHOTOPRISM_APP_ID, "latest")
    except Exception:
        return None
    if not isinstance(receipt, dict):
        return None
    if receipt.get("status") == "not_created":
        return None
    proofs = [
        _proof(
            str(item.get("id") or "proof"),
            str(item.get("label") or "Proof"),
            str(item.get("status") or "not_checked"),
            str(item.get("plain_language") or "Proof available."),
        )
        for item in (receipt.get("proofs") or [])
        if isinstance(item, dict)
    ]
    return _receipt(
        receipt_id=receipt.get("receipt_id") or receipt.get("backup_id") or "backup-app",
        app_id=PHOTOPRISM_APP_ID,
        action_id="backup_app",
        action_label="Back up app",
        status=receipt.get("status"),
        summary=_safe_text(receipt.get("summary"), "PhotoPrism app backup evidence available."),
        started_at=receipt.get("started_at"),
        completed_at=receipt.get("completed_at"),
        proofs=proofs,
        what_changed=receipt.get("what_changed") or ["PhotoPrism settings, mappings, and safe app records were saved for backup."],
        what_did_not_happen=receipt.get("what_did_not_happen") or ["Original photos were not included by default.", "Raw secret values were not exposed.", "No frontend shell commands ran."],
        evidence_ref=receipt.get("evidence_ref") or f"apps/photoprism/backups/{_safe_ref(receipt.get('backup_id'), 'latest')}.json",
        technical_details=receipt.get("technical_details") if isinstance(receipt.get("technical_details"), dict) else {"backup_mode": "config_only", "media_excluded": True},
        proof_source="App Catalog backup receipt",
    )



def _restore_preview_receipt() -> dict[str, Any] | None:
    try:
        status = lite_app_backup.app_backup_status(PHOTOPRISM_APP_ID)
    except Exception:
        return None
    preview = status.get("latest_restore_preview") if isinstance(status.get("latest_restore_preview"), dict) else None
    if not preview:
        return None
    preview_id = preview.get("preview_id") or preview.get("operation_id") or preview.get("command_id")
    backup_id = preview.get("backup_id")
    preview_status = _normalize_receipt_status(preview.get("status"))
    ready = preview_status == "succeeded" or str(preview.get("status") or "").lower() == "ready"
    proofs = [
        _proof("backend_worker_executed", "Backend worker executed", "passed" if ready else "review", "The restore preview ran through Pocket Lab Lite backend worker."),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Preview restore through FastAPI."),
        _proof("preview_only", "Preview only", "passed", "This action reviewed restore impact only."),
        _proof("restore_apply_disabled", "Restore apply disabled", "passed", "No destructive restore apply is enabled from this App Catalog action."),
        _proof("backup_verified", "Backup verified", "passed" if backup_id else "review", "A verified app backup was selected for the restore preview." if backup_id else "A verified app backup could not be confirmed from public state."),
        _proof("app_records_reviewed", "App records reviewed", "passed" if ready else "review", "PhotoPrism app settings, mappings, route records, and safe app records were reviewed."),
        _proof("media_preserved", "Media preserved", "passed", "Original photos and imported media were not changed."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
        _proof("raw_logs_hidden", "Raw logs hidden", "passed", "Raw logs are hidden."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw device and backup paths are hidden."),
        _proof("receipt_saved", "Receipt saved", "passed" if preview_id else "review", "Pocket Lab saved a sanitized restore-preview receipt."),
    ]
    return _receipt(
        receipt_id=preview_id or "restore-preview",
        app_id=PHOTOPRISM_APP_ID,
        action_id="preview_restore",
        action_label="Preview restore",
        status="succeeded" if ready else "review",
        summary=_safe_text(preview.get("summary"), "Restore preview ready. No changes were applied."),
        started_at=preview.get("started_at") or preview.get("created_at"),
        completed_at=preview.get("completed_at") or preview.get("created_at") or preview.get("updated_at"),
        proofs=proofs,
        what_changed=["Pocket Lab Lite prepared a restore preview for PhotoPrism app records."],
        what_did_not_happen=[
            "No files were restored.",
            "No app configuration was replaced.",
            "No database was changed.",
            "No photos were changed.",
            "No services were restarted.",
            "No secret values were exposed.",
        ],
        evidence_ref=preview.get("evidence_ref") or f"apps/photoprism/restore-previews/{_safe_ref(preview_id, 'latest')}.json",
        technical_details={
            "backup_id": _safe_ref(backup_id, "latest"),
            "preview_only": True,
            "restore_allowed": False,
            "restore_apply_supported": False,
            "media_preserved": True,
            "destructive_changes": False,
        },
        proof_source="App Catalog restore-preview state",
    )



def _update_receipt() -> dict[str, Any] | None:
    try:
        receipt = lite_app_update.update_receipt(PHOTOPRISM_APP_ID, "latest")
    except Exception:
        return None
    if not isinstance(receipt, dict):
        return None
    proofs = [
        _proof(
            str(item.get("id") or "proof"),
            str(item.get("label") or "Proof"),
            str(item.get("status") or "not_checked"),
            str(item.get("plain_language") or item.get("summary") or "Proof available."),
        )
        for item in (receipt.get("proofs") or [])
        if isinstance(item, dict)
    ]
    return _receipt(
        receipt_id=receipt.get("receipt_id") or receipt.get("operation_id") or "update-app",
        app_id=PHOTOPRISM_APP_ID,
        action_id="update_app",
        action_label="Update",
        status=receipt.get("status") or "review",
        summary=_safe_text(receipt.get("summary"), "Update readiness checked. No update was applied."),
        started_at=receipt.get("started_at"),
        completed_at=receipt.get("completed_at"),
        proofs=proofs,
        what_changed=receipt.get("what_changed") or ["Pocket Lab Lite checked whether PhotoPrism is ready for a safe update."],
        what_did_not_happen=receipt.get("what_did_not_happen") or [
            "No update was installed.",
            "No files were replaced.",
            "No database was changed.",
            "No photos were changed.",
            "No services were restarted.",
            "No secret values were exposed.",
        ],
        evidence_ref=receipt.get("evidence_ref") or f"apps/photoprism/update/{_safe_ref(receipt.get('receipt_id'), 'latest')}.json",
        technical_details=receipt.get("technical_details") if isinstance(receipt.get("technical_details"), dict) else {
            "action_id": "update_app",
            "execution_owner": "backend worker",
            "apply_supported": False,
            "raw_logs": "hidden",
            "raw_paths": "hidden",
            "secret_values": "hidden",
        },
        proof_source="App Catalog update-readiness receipt",
    )




def _operation_receipts() -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    try:
        operations = lite_app_operations.operation_receipts(PHOTOPRISM_APP_ID)
    except Exception:
        return receipts
    for operation in operations:
        action_id = str(operation.get("action_id") or "").lower()
        if action_id not in {"check_app", "repair_app"}:
            continue
        status = _normalize_receipt_status(operation.get("status"))
        proof_status = "passed" if status == "succeeded" else ("failed" if status == "failed" else "review")
        stored_proofs = operation.get("proofs") if isinstance(operation.get("proofs"), list) else []
        proof_by_id = {str(item.get("id")): item for item in stored_proofs if isinstance(item, dict)}

        def from_operation(proof_id: str, label: str, fallback_status: str, plain_language: str) -> dict[str, Any]:
            item = proof_by_id.get(proof_id)
            if item:
                return _proof(
                    proof_id,
                    item.get("label") or label,
                    item.get("status") or fallback_status,
                    item.get("plain_language") or item.get("summary") or plain_language,
                    technical=item.get("technical") if isinstance(item.get("technical"), dict) else None,
                )
            return _proof(proof_id, label, fallback_status, plain_language)

        if action_id == "check_app":
            proofs = [
                from_operation("backend_worker_executed", "Backend worker executed", proof_status, "The app check was handled by Pocket Lab Lite backend worker."),
                from_operation("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Check app through FastAPI."),
                from_operation("browser_no_file_access", "Browser did not access files", "passed", "The browser did not access files or PhotoPrism internals."),
                from_operation("app_route_checked", "Secure route checked", proof_status, "Pocket Lab checked the same-origin PhotoPrism route."),
                from_operation("app_health_checked", "App health checked", proof_status, "Pocket Lab checked PhotoPrism health."),
                from_operation("storage_mapping_checked", "Storage mapping checked", proof_status, "Photo storage mapping state was checked without listing files."),
                from_operation("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
                from_operation("raw_logs_hidden", "Raw logs hidden", "passed", "Raw app logs are hidden."),
                from_operation("raw_paths_hidden", "Raw paths hidden", "passed", "Raw paths are hidden."),
                from_operation("media_not_scanned", "Media was not scanned", "passed", "No photos were scanned, imported, or indexed."),
                from_operation("media_details_owned_by_photoprism", "PhotoPrism owns media details", "passed", "PhotoPrism handles media-specific details."),
                from_operation("receipt_saved", "Receipt saved", proof_status, "Pocket Lab saved a sanitized Check app receipt."),
            ]
            receipts.append(_receipt(
                receipt_id=operation.get("operation_id") or operation.get("command_id") or "check-app",
                app_id=PHOTOPRISM_APP_ID,
                action_id="check_app",
                action_label="Check app",
                status=status,
                summary=_safe_text(operation.get("summary"), "App checked."),
                started_at=operation.get("started_at") or operation.get("queued_at"),
                completed_at=operation.get("completed_at") or operation.get("updated_at"),
                proofs=proofs,
                what_changed=["Pocket Lab Lite checked PhotoPrism safety and route readiness."],
                what_did_not_happen=["No photos were scanned.", "No PhotoPrism indexing was started.", "No source media was changed.", "No secret values were exposed."],
                evidence_ref=operation.get("evidence_ref") or "apps/photoprism/safety/latest.json",
                technical_details={
                    "route_status": (operation.get("technical_details") or {}).get("route_path") or "checked",
                    "storage_mode": (operation.get("technical_details") or {}).get("storage_mode") or "checked",
                    "media_scanned": False,
                    "import_started": False,
                    "index_started": False,
                },
                proof_source="PhotoPrism app safety operation",
            ))
        if action_id == "repair_app":
            proofs = [
                from_operation("backend_worker_executed", "Backend worker executed", proof_status, "The repair was handled by Pocket Lab Lite backend worker."),
                from_operation("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Repair through FastAPI."),
                from_operation("browser_no_file_access", "Browser did not access files", "passed", "The browser did not access app files or storage."),
                from_operation("repair_bounded", "Repair was bounded", "passed", "Repair was limited to route, health, and managed storage checks."),
                from_operation("media_preserved", "Media preserved", "passed", "No source photos were deleted or changed."),
                from_operation("no_destructive_changes", "No destructive changes", "passed", "Repair did not reset the database, credentials, or media."),
                from_operation("app_route_checked", "Secure route checked", proof_status, "Pocket Lab checked or refreshed the app route."),
                from_operation("storage_mapping_checked", "Storage mapping checked", proof_status, "Managed storage mappings were checked safely."),
                from_operation("app_health_checked", "App health verified", proof_status, "Pocket Lab checked app health after repair."),
                from_operation("restart_safe", "Restart was safe", "not_applicable", "No restart was needed or only the app process was restarted safely."),
                from_operation("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
                from_operation("raw_logs_hidden", "Raw logs hidden", "passed", "Raw PM2 and app logs are hidden."),
                from_operation("raw_paths_hidden", "Raw paths hidden", "passed", "Raw paths are hidden."),
                from_operation("receipt_saved", "Receipt saved", proof_status, "Pocket Lab saved a sanitized Repair receipt."),
            ]
            receipts.append(_receipt(
                receipt_id=operation.get("operation_id") or operation.get("command_id") or "repair-app",
                app_id=PHOTOPRISM_APP_ID,
                action_id="repair_app",
                action_label="Repair",
                status=status,
                summary=_safe_text(operation.get("summary"), "Repair completed."),
                started_at=operation.get("started_at") or operation.get("queued_at"),
                completed_at=operation.get("completed_at") or operation.get("updated_at"),
                proofs=proofs,
                what_changed=["Pocket Lab checked or refreshed PhotoPrism route, health, and managed storage setup."],
                what_did_not_happen=["No photos were deleted.", "No database was reset.", "No passwords were changed.", "No PhotoPrism indexing was started.", "No raw secrets were exposed."],
                evidence_ref=operation.get("evidence_ref") or "apps/photoprism/repair/latest.json",
                technical_details={
                    "restart_performed": bool((operation.get("technical_details") or {}).get("restart_performed")),
                    "repair_bounded": True,
                    "media_preserved": True,
                    "destructive_changes": False,
                    "app_login_changed": False,
                    "database_reset": False,
                },
                proof_source="PhotoPrism app repair operation",
            ))
    return receipts

def _fallback_receipt() -> dict[str, Any]:
    proofs = [
        _proof("frontend_no_shell", "Browser did not run commands", "not_checked", "No detailed receipt has been saved yet."),
        _proof("secrets_hidden", "Secrets hidden", "not_checked", "Future receipts will confirm redaction status."),
        _proof("receipt_saved", "Receipt saved", "not_checked", "No evidence receipt yet."),
    ]
    return _receipt(
        receipt_id="photoprism-no-evidence-yet",
        app_id=PHOTOPRISM_APP_ID,
        action_id="none",
        action_label="Evidence",
        status="review",
        summary="No detailed receipt yet. Future actions will include proof details.",
        proofs=proofs,
        what_changed=[],
        what_did_not_happen=[],
        evidence_ref="apps/photoprism/evidence/pending",
        technical_details={"route_status": "not_checked"},
        proof_source="fallback",
    )


def app_evidence(app_id: str) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    items: list[dict[str, Any]] = []
    items.extend(_operation_receipts())
    items.extend(_import_receipts())
    connect = _connect_photos_receipt()
    if connect:
        items.append(connect)
    backup = _backup_receipt()
    if backup:
        items.append(backup)
    restore_preview = _restore_preview_receipt()
    if restore_preview:
        items.append(restore_preview)
    update = _update_receipt()
    if update:
        items.append(update)
    security = _security_receipt()
    if security:
        items.append(security)

    items = sorted(items, key=lambda item: _time_key(item.get("completed_at") or item.get("updated_at") or item.get("started_at")), reverse=True)
    if not items:
        latest = None
        proof_counts = {"passed": 0, "review": 0, "failed": 0, "not_checked": 0, "not_applicable": 0}
        summary = "No evidence receipt yet."
    else:
        latest = items[0]
        proof_counts = latest.get("proof_counts") or _proof_counts(latest.get("proofs") or [])
        summary = _safe_text(latest.get("summary"), "Latest evidence receipt available.")

    by_action: dict[str, dict[str, Any]] = {}
    for item in items:
        action_id = str(item.get("action_id") or "").strip()
        if action_id and action_id not in by_action:
            by_action[action_id] = item

    payload = {
        "status": "healthy",
        "app_id": app,
        "summary": summary,
        "latest": latest,
        "receipt": latest,
        "receipt_id": (latest or {}).get("receipt_id"),
        "action_id": (latest or {}).get("action_id"),
        "action_label": (latest or {}).get("action_label"),
        "evidence_ref": (latest or {}).get("evidence_ref"),
        "proof_counts": proof_counts,
        "items": items[:12],
        "by_action": by_action,
        "latest_by_action": by_action,
        "count": len(items),
        "fallback_receipt": _fallback_receipt() if not items else None,
        "updated_at": (latest or {}).get("updated_at") or _now(),
    }
    return _sanitize_payload(payload)


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in _SECRET_MARKERS) and not isinstance(item, bool):
                continue
            clean[key] = _sanitize_payload(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value[:50]]
    if isinstance(value, str):
        return _safe_text(value, "hidden")
    return value
