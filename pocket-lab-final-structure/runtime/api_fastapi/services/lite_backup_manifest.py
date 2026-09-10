from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from .lite_backup_policy import backup_layout
from . import lite_storage_faults

CURRENT_FORMAT_VERSION = 2
_SAFE_BACKUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_MAX_MANIFEST_SUMMARY_CACHE = 256
_SUMMARY_CACHE_LOCK = threading.RLock()
_SUMMARY_CACHE: dict[
    str, tuple[tuple[int, int, int], tuple[int, str], dict[str, Any]]
] = {}


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
    if not _SAFE_BACKUP_ID.fullmatch(str(backup_id or "").strip()):
        raise ValueError("invalid backup id")
    return backup_layout().manifests / f"{backup_id}.json"


def receipt_path(backup_id: str) -> Path:
    if not _SAFE_BACKUP_ID.fullmatch(str(backup_id or "").strip()):
        raise ValueError("invalid backup id")
    return backup_layout().receipts / f"{backup_id}.json"


def write_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    backup_id = str(manifest.get("backup_id") or "").strip()
    if not backup_id:
        raise ValueError("backup_id is required")
    manifest = dict(manifest)
    manifest["manifest_checksum"] = canonical_checksum(manifest)
    path = manifest_path(backup_id)
    _write_json(path, manifest)
    with _SUMMARY_CACHE_LOCK:
        _SUMMARY_CACHE.pop(str(path), None)
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


def _manifest_sort_key(path: Path, payload: dict[str, Any]) -> tuple[int, str]:
    backup_id = str(payload.get("backup_id") or path.stem)
    created_at = str(payload.get("created_at") or "").strip()
    if created_at:
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1_000_000), backup_id
        except ValueError:
            pass
    return path.stat().st_mtime_ns // 1_000, backup_id


def _manifest_fingerprint(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    return (
        int(getattr(stat, "st_ino", 0) or 0),
        int(stat.st_size),
        int(getattr(stat, "st_mtime_ns", 0) or 0),
    )


def _compact_app_backup(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = (
        "app_id",
        "app_label",
        "mode",
        "included_sets",
        "excluded_sets",
        "media_included",
    )
    compact = {key: value[key] for key in allowed if key in value}
    return compact if compact.get("app_id") else None


def _compact_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Retain only bounded history metadata, never the full file inventory.

    Full manifests remain the durable restore/verification authority and are
    read by ``read_manifest`` for a selected backup.  Recovery summary and
    history probes only need the public metadata below; retaining
    ``included_files`` for every historical point inflated the Termux worker's
    heap into the PM2 memory ceiling.
    """
    if not payload.get("backup_id"):
        return None
    compact = api_manifest(payload)
    app_backup = _compact_app_backup(payload.get("app_backup"))
    if app_backup is not None:
        compact["app_backup"] = app_backup
    return compact


def _sorted_manifest_records() -> list[tuple[tuple[int, str], dict[str, Any]]]:
    layout = backup_layout()
    layout.ensure()
    records: list[tuple[tuple[int, str], dict[str, Any]]] = []
    seen: set[str] = set()
    for path in layout.manifests.glob("*.json"):
        fingerprint = _manifest_fingerprint(path)
        if fingerprint is None:
            continue
        cache_key = str(path)
        seen.add(cache_key)
        with _SUMMARY_CACHE_LOCK:
            cached = _SUMMARY_CACHE.get(cache_key)
        if cached is not None and cached[0] == fingerprint:
            sort_key, compact = cached[1], cached[2]
        else:
            payload = _read_json(path, {})
            if not isinstance(payload, dict):
                continue
            compact = _compact_manifest(path, payload)
            if compact is None:
                continue
            sort_key = _manifest_sort_key(path, compact)
            with _SUMMARY_CACHE_LOCK:
                _SUMMARY_CACHE[cache_key] = (fingerprint, sort_key, compact)
        # A shallow copy keeps callers from mutating the cached record while
        # avoiding another copy of any large historical inventory (which is
        # intentionally absent from the compact value).
        records.append((sort_key, dict(compact)))
    with _SUMMARY_CACHE_LOCK:
        for key in tuple(_SUMMARY_CACHE):
            if key not in seen:
                _SUMMARY_CACHE.pop(key, None)
        while len(_SUMMARY_CACHE) > _MAX_MANIFEST_SUMMARY_CACHE:
            _SUMMARY_CACHE.pop(next(iter(_SUMMARY_CACHE)), None)
    return sorted(records, key=lambda item: item[0], reverse=True)


def _encode_page_cursor(sort_key: tuple[int, str]) -> str:
    encoded = json.dumps(
        {"created_at_us": sort_key[0], "backup_id": sort_key[1]},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_page_cursor(cursor: str) -> tuple[int, str] | None:
    value = str(cursor or "").strip()
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        created_at_us = int(payload.get("created_at_us"))
        backup_id = str(payload.get("backup_id") or "").strip()
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if created_at_us < 0 or not backup_id:
        return None
    return created_at_us, backup_id


def list_manifests(limit: int = 25) -> list[dict[str, Any]]:
    max_items = max(1, min(limit, 200))
    return [payload for _sort_key, payload in _sorted_manifest_records()[:max_items]]


def list_manifests_page(*, limit: int = 10, cursor: str = "") -> dict[str, Any]:
    max_items = max(1, min(int(limit or 10), 50))
    requested_cursor = str(cursor or "").strip()
    decoded_cursor = _decode_page_cursor(requested_cursor) if requested_cursor else None
    if requested_cursor and decoded_cursor is None:
        return {"items": [], "next_cursor": None, "has_more": False, "cursor_found": False}

    records = _sorted_manifest_records()
    start_index = 0
    cursor_found = not requested_cursor
    if decoded_cursor is not None:
        for index, (sort_key, _payload) in enumerate(records):
            if sort_key == decoded_cursor:
                start_index = index + 1
                cursor_found = True
                break
        if not cursor_found:
            return {"items": [], "next_cursor": None, "has_more": False, "cursor_found": False}

    page_records = records[start_index:start_index + max_items + 1]
    page = page_records[:max_items]
    has_more = len(page_records) > max_items
    return {
        "items": [payload for _sort_key, payload in page],
        "next_cursor": _encode_page_cursor(page[-1][0]) if has_more and page else None,
        "has_more": has_more,
        "cursor_found": cursor_found,
    }


def latest_manifest() -> dict[str, Any] | None:
    items = list_manifests(limit=1)
    return items[0] if items else None


def resolve_backup_id(backup_id: str) -> str | None:
    value = str(backup_id or "").strip()
    if value == "latest":
        latest = latest_manifest()
        return str(latest.get("backup_id")) if latest else None
    return value if _SAFE_BACKUP_ID.fullmatch(value) else None



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
    repository = manifest.get("repository") if isinstance(manifest.get("repository"), dict) else {}
    included_files = manifest.get("included_files") or []

    def included_file_size(item: Any) -> int:
        if not isinstance(item, dict):
            return 0
        try:
            return max(0, int(item.get("size_bytes") or 0))
        except (TypeError, ValueError):
            return 0

    try:
        included_file_count = max(
            0,
            int(manifest.get("included_file_count"))
            if "included_file_count" in manifest and not included_files
            else len(included_files),
        )
    except (TypeError, ValueError):
        included_file_count = len(included_files) if hasattr(included_files, "__len__") else 0
    return {
        "backup_id": manifest.get("backup_id"),
        "created_at": manifest.get("created_at"),
        "completed_at": manifest.get("completed_at"),
        "label": manifest.get("label") or "Pocket Lab Lite restore point",
        "format_version": int(manifest.get("format_version") or 1),
        "status": manifest.get("status") or manifest.get("verification_status") or "unknown",
        "app_version": manifest.get("app_version"),
        "schema_version": manifest.get("schema_version"),
        "include_event_journal": bool(manifest.get("include_event_journal", True)),
        "engine": manifest.get("engine"),
        "repository": {
            "type": repository.get("type") or "local",
            "engine": repository.get("engine") or "restic",
            "encrypted": bool(repository.get("encrypted", True)),
            "location": "Configured encrypted repository",
        },
        "snapshot_id": manifest.get("snapshot_id"),
        "included_sets": manifest.get("included_sets", []),
        "included_file_count": included_file_count,
        "excluded_sensitive_items": manifest.get("excluded_sensitive_items", []),
        "verification_status": manifest.get("verification_status", "not_verified"),
        "restorable": bool(manifest.get("restorable", manifest.get("verification_status") == "verified")),
        "size_bytes": int(manifest.get("size_bytes") or sum(included_file_size(item) for item in included_files)),
        "included_components": manifest.get("included_components") or manifest.get("included_sets", []),
        "excluded_components": manifest.get("excluded_components") or manifest.get("excluded_runtime_items", []),
        "component_results": manifest.get("component_results") or {},
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
    payload = {k: v for k, v in receipt.items() if k in allowed}
    repository = payload.get("repository")
    if isinstance(repository, dict):
        payload["repository"] = {
            "type": repository.get("type") or "local",
            "engine": repository.get("engine") or "restic",
            "encrypted": bool(repository.get("encrypted", True)),
            "location": "Configured encrypted repository",
        }
    return payload
