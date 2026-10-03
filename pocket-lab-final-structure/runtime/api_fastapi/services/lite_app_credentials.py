"""Secret-safe app credential metadata.

This service intentionally stores no credential values.  It records only
registry-bound status needed by Apps/Identity/Recovery.  Secret-value storage is
outside this contract until an approved backend secret primitive is integrated.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from .. import deps
from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_app_registry

_CREDENTIAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
STATUSES = frozenset({"configured", "missing", "needs_rotation", "invalid", "external_manual", "not_required"})
MANAGEMENT = frozenset({"external_or_manual"})


def _definition(app_id: Any):
    return lite_app_registry.app_definition(app_id)


def _declarations(app_id: Any) -> list[dict[str, Any]]:
    definition = _definition(app_id)
    return [dict(item) for item in definition.credentials]


def _public(row: dict[str, Any], declaration: dict[str, Any]) -> dict[str, Any]:
    return {
        "credential_id": declaration["id"],
        "label": declaration.get("label") or "App credential",
        "purpose": declaration.get("purpose") or "",
        "required": bool(declaration.get("required")),
        "management": row.get("management") or declaration.get("management") or "external_or_manual",
        "status": row.get("status") or ("missing" if declaration.get("required") else "external_manual"),
        "last_verified_at": row.get("last_verified_at") or None,
        "updated_at": row.get("updated_at") or None,
        "secret_value_exposed": False,
    }


def credential_status(app_id: Any) -> dict[str, Any]:
    definition = _definition(app_id)
    apply_migrations()
    declarations = _declarations(definition.id)
    with connection() as conn:
        rows = conn.execute(
            "SELECT credential_id,purpose,status,management,last_verified_at,updated_at FROM app_credential_metadata WHERE app_id=?",
            (definition.id,),
        ).fetchall()
    by_id = {str(row["credential_id"]): dict(row) for row in rows}
    credentials = [_public(by_id.get(str(item["id"]), {}), item) for item in declarations]
    required_missing = any(item["required"] and item["status"] in {"missing", "invalid"} for item in credentials)
    needs_rotation = any(item["status"] == "needs_rotation" for item in credentials)
    return {
        "app_id": definition.id,
        "app_label": definition.name,
        "credential_required": any(item["required"] for item in credentials),
        "configured": bool(credentials) and not required_missing,
        "missing": required_missing,
        "needs_rotation": needs_rotation,
        "credentials": credentials,
        "secret_store": "deferred",
        "secret_values_stored_here": False,
        "secret_values_exposed": False,
        "summary": "Credential status needs attention." if required_missing or needs_rotation else "Credential status is available.",
        "updated_at": deps.now_utc_iso(),
    }


def update_metadata(
    app_id: Any,
    *,
    credential_id: Any,
    status: Any,
    management: Any = "external_or_manual",
    last_verified_at: Any = None,
) -> dict[str, Any]:
    definition = _definition(app_id)
    safe_id = str(credential_id or "").strip()
    if not _CREDENTIAL_ID_RE.fullmatch(safe_id):
        raise HTTPException(status_code=422, detail={"status": "credential_id_invalid", "summary": "Choose a registered credential purpose."})
    declaration = next((dict(item) for item in definition.credentials if str(item.get("id") or "") == safe_id), None)
    if declaration is None:
        raise HTTPException(status_code=404, detail={"status": "credential_not_registered", "summary": "That credential purpose is not registered for this app."})
    safe_status = str(status or "").strip().lower()
    if safe_status not in STATUSES:
        raise HTTPException(status_code=422, detail={"status": "credential_status_invalid", "summary": "Choose a supported credential status."})
    safe_management = str(management or "").strip().lower()
    if safe_management not in MANAGEMENT:
        raise HTTPException(status_code=422, detail={"status": "credential_management_invalid", "summary": "Choose a supported credential management mode."})
    verified_at = str(last_verified_at or "").strip()[:40] or None
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO app_credential_metadata(app_id,credential_id,purpose,status,management,last_verified_at,updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(app_id,credential_id) DO UPDATE SET
                     purpose=excluded.purpose,status=excluded.status,management=excluded.management,
                     last_verified_at=excluded.last_verified_at,updated_at=excluded.updated_at""",
                (
                    definition.id,
                    safe_id,
                    str(declaration.get("purpose") or "")[:80],
                    safe_status,
                    safe_management,
                    verified_at,
                    deps.now_utc_iso(),
                ),
            )
    return credential_status(definition.id)
