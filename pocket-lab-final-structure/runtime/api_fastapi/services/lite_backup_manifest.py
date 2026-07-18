from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .lite_backup_policy import backup_layout
from . import lite_storage_faults


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    lite_storage_faults.raise_if_storage_fault("backup_output_write")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def canonical_checksum(payload: dict[str, Any]) -> str:
    data = {k: v for k, v in payload.items() if k != "manifest_checksum"}
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def manifest_path(backup_id: str) -> Path:
    return backup_layout().manifests / f"{backup_id}.json"


def receipt_path(backup_id: str) -> Path:
    return backup_layout().receipts / f"{backup_id}.json"


def write_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    backup_id = str(manifest.get("backup_id") or "").strip()
    if not backup_id:
        raise ValueError("backup_id is required")
    manifest = dict(manifest)
    manifest["manifest_checksum"] = canonical_checksum(manifest)
    _write_json(manifest_path(backup_id), manifest)
    return manifest


def write_receipt(backup_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.setdefault("backup_id", backup_id)
    _write_json(receipt_path(backup_id), payload)
    return payload


def read_manifest(backup_id: str) -> dict[str, Any] | None:
    backup_id = str(backup_id or "").strip()
    if not backup_id:
        return None
    payload = _read_json(manifest_path(backup_id), None)
    return payload if isinstance(payload, dict) else None


def read_receipt(backup_id: str) -> dict[str, Any] | None:
    backup_id = str(backup_id or "").strip()
    if not backup_id:
        return None
    payload = _read_json(receipt_path(backup_id), None)
    return payload if isinstance(payload, dict) else None


def list_manifests(limit: int = 25) -> list[dict[str, Any]]:
    layout = backup_layout()
    layout.ensure()
    items: list[dict[str, Any]] = []
    max_items = max(1, min(limit, 200))
    for path in sorted(
        layout.manifests.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        payload = _read_json(path, {})
        if isinstance(payload, dict) and payload.get("backup_id"):
            items.append(payload)
        if len(items) >= max_items:
            break
    return items


def latest_manifest() -> dict[str, Any] | None:
    items = list_manifests(limit=1)
    return items[0] if items else None


def resolve_backup_id(backup_id: str) -> str | None:
    value = str(backup_id or "").strip()
    if value == "latest":
        latest = latest_manifest()
        return str(latest.get("backup_id")) if latest else None
    return value or None



def no_backup_payload(*, backup_id: str = "latest", kind: str = "backup") -> dict[str, Any]:
    label = "Backup receipt" if kind == "receipt" else "Backup"
    return {
        "status": "not_created",
        "backup_id": backup_id,
        "summary": f"{label} has not been created yet. Run Backup Now first, then refresh this endpoint.",
        "latest_backup_available": False,
        "retry_after_seconds": 2,
    }

def api_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "backup_id": manifest.get("backup_id"),
        "created_at": manifest.get("created_at"),
        "engine": manifest.get("engine"),
        "repository": manifest.get("repository"),
        "snapshot_id": manifest.get("snapshot_id"),
        "included_sets": manifest.get("included_sets", []),
        "included_file_count": len(manifest.get("included_files") or []),
        "excluded_sensitive_items": manifest.get("excluded_sensitive_items", []),
        "verification_status": manifest.get("verification_status", "not_verified"),
        "verified_at": manifest.get("verified_at"),
        "risk_level": manifest.get("risk_level", "low"),
        "manifest_checksum": manifest.get("manifest_checksum"),
        "evidence_references": manifest.get("evidence_references", []),
        "summary": manifest.get("summary"),
        "verification": manifest.get("verification"),
        "database_backup": manifest.get("database_backup"),
    }


def api_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "backup_id",
        "created_at",
        "status",
        "summary",
        "engine",
        "snapshot_id",
        "manifest_checksum",
        "evidence_saved",
        "evidence_references",
        "repository",
        "included_sets",
        "excluded_sensitive_items",
        "verification_status",
        "verified_at",
        "verification_checks",
    }
    return {k: v for k, v in receipt.items() if k in allowed}
