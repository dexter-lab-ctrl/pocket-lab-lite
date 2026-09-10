"""Backend-owned encrypted backup location registry.

The browser never supplies or receives a filesystem path.  A location is
selected by an opaque id returned by this module after the backend has
validated a bounded, known storage candidate.  The registry is intentionally
small: it describes repositories, not an Android media browser, and it never
walks shared storage.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Iterable

from .. import deps
from ..db.connection import database_path, connection, begin_immediate
from ..db.migrations import apply_migrations
from .lite_backup_policy import is_excluded_media_path

DEFAULT_LOCATION_ID = "default-private"
CUSTOM_STORAGE_FOLDER = "Pocket Lab Backups"
CUSTOM_LAYOUT_FOLDER = "PocketLab"
MIN_FREE_BYTES_DEFAULT = 64 * 1024 * 1024
_LOCATION_ID_PREFIX = "loc-"


class BackupLocationError(RuntimeError):
    """A safe, user-facing backup location operation failure."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = str(reason_code or "location_unavailable")[:80]
        self.message = str(message or "Backup location is unavailable.")[:240]


def _utc() -> str:
    return deps.now_utc_iso()


def _schema() -> None:
    apply_migrations()


def _default_root() -> Path:
    from .lite_backup_policy import backup_root

    return backup_root().expanduser().resolve(strict=False)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _path_overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _split_paths(value: str) -> Iterable[Path]:
    for raw in str(value or "").split(os.pathsep):
        text = raw.strip()
        if text:
            yield Path(text).expanduser().resolve(strict=False)


def _trusted_storage_roots() -> list[Path]:
    roots: list[Path] = []
    roots.extend(_split_paths(os.environ.get("POCKETLAB_LITE_BACKUP_ALLOWED_ROOTS", "")))
    home = Path.home()
    for candidate in (home / "storage" / "shared", Path("/storage/emulated/0")):
        resolved = candidate.expanduser().resolve(strict=False)
        if resolved.exists() and resolved.is_dir():
            roots.append(resolved)
    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root == Path("/") or not root.is_absolute():
            continue
        key = str(root)
        if key not in seen:
            seen.add(key)
            result.append(root)
    return result


def _candidate_id(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:24]
    return f"{_LOCATION_ID_PREFIX}{digest}"


def _location_id(path: Path) -> str:
    return _candidate_id(path)


def _candidate_specs() -> list[dict[str, Any]]:
    """Return fixed backend candidates without scanning storage."""
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    configured = list(_split_paths(os.environ.get("POCKETLAB_LITE_BACKUP_LOCATION_CANDIDATES", "")))
    for root in _trusted_storage_roots():
        configured.append(root / CUSTOM_STORAGE_FOLDER)
    for path in configured:
        path = path.expanduser().resolve(strict=False)
        if path == _default_root() or path == Path("/"):
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            _validate_custom_root(path, allow_missing=True)
        except BackupLocationError:
            continue
        kind, label, removable = _classify_candidate(path)
        candidates.append(
            {
                "candidate_id": _candidate_id(path),
                "path": path,
                "kind": kind,
                "display_name": label,
                "is_removable": removable,
            }
        )
    return candidates


def _classify_candidate(path: Path) -> tuple[str, str, bool]:
    text = str(path).replace("\\", "/").lower()
    if text.startswith("/storage/emulated/") or "/storage/emulated/" in text:
        return "android_internal", "Android shared storage › Pocket Lab Backups", False
    if text.startswith("/storage/") or "/storage/" in text:
        return "android_removable", "Android removable storage › Pocket Lab Backups", True
    if "storage/shared" in text:
        return "android_internal", "Android shared storage › Pocket Lab Backups", False
    return "configured", "Configured storage › Pocket Lab Backups", False


def _validate_custom_root(path: Path, *, allow_missing: bool) -> Path:
    raw = Path(path).expanduser()
    if "\x00" in str(raw):
        raise BackupLocationError("invalid_path", "The selected backup location is not valid.")
    if not raw.is_absolute() or ".." in raw.parts:
        raise BackupLocationError("path_not_allowed", "Choose a backend-discovered storage location.")
    resolved = raw.resolve(strict=False)
    shared_storage_destination = any(
        resolved.name == CUSTOM_STORAGE_FOLDER and resolved.parent == root
        for root in _trusted_storage_roots()
    )
    if resolved == Path("/") or (is_excluded_media_path(resolved) and not shared_storage_destination):
        raise BackupLocationError("media_or_root_not_allowed", "Android shared media and the filesystem root cannot hold this backup.")
    if raw.is_symlink():
        raise BackupLocationError("symlink_not_allowed", "The selected backup location cannot be a symbolic link.")
    repo_root = _repository_root().resolve(strict=False)
    state_root = deps.settings().state_dir.expanduser().resolve(strict=False)
    db_path = database_path().expanduser().resolve(strict=False)
    if _path_overlaps(resolved, repo_root) or _path_overlaps(resolved, state_root) or _path_overlaps(resolved, db_path.parent):
        raise BackupLocationError("runtime_path_not_allowed", "Pocket Lab runtime and database paths cannot hold a backup repository.")
    default_root = _default_root()
    if _path_overlaps(resolved, default_root):
        raise BackupLocationError("nested_repository_not_allowed", "Backup locations cannot overlap the existing default repository.")

    trusted_roots = _trusted_storage_roots()
    configured_candidates = list(_split_paths(os.environ.get("POCKETLAB_LITE_BACKUP_LOCATION_CANDIDATES", "")))
    trusted_roots.extend(item.parent for item in configured_candidates)
    matched_root: Path | None = None
    for root in trusted_roots:
        root = root.resolve(strict=False)
        if resolved != root and root in resolved.parents:
            relative = resolved.relative_to(root)
            if len(relative.parts) == 1:
                matched_root = root
                break
    if matched_root is None:
        raise BackupLocationError("path_not_allowed", "Choose a backend-discovered storage location.")
    parent = resolved.parent
    if not parent.exists() or not parent.is_dir():
        if not allow_missing:
            raise BackupLocationError("parent_missing", "The selected storage location is not available.")
    if resolved.exists() and not resolved.is_dir():
        raise BackupLocationError("not_a_directory", "The selected backup location is not a directory.")
    return resolved


def _ensure_default(conn: Any) -> None:
    now = _utc()
    root = _default_root()
    conn.execute(
        """
        INSERT INTO recovery_backup_locations(
            location_id, kind, display_name, root_path, canonical_root,
            repository_id, repository_fingerprint, is_default, is_selected,
            is_removable, is_forgotten, status, reason_code, created_at, updated_at
        ) VALUES (?, 'private_default', 'Pocket Lab private backup folder', ?, ?, ?, '', 1, 0, 0, 0, 'checking', '', ?, ?)
        ON CONFLICT(location_id) DO UPDATE SET
            root_path=excluded.root_path,
            canonical_root=excluded.canonical_root,
            updated_at=excluded.updated_at,
            is_forgotten=0
        """,
        (DEFAULT_LOCATION_ID, str(root), str(root), "restic:default-private", now, now),
    )
    selected = conn.execute(
        "SELECT 1 FROM recovery_backup_locations WHERE is_selected = 1 AND is_forgotten = 0 LIMIT 1"
    ).fetchone()
    if not selected:
        conn.execute(
            "UPDATE recovery_backup_locations SET is_selected = CASE WHEN location_id = ? THEN 1 ELSE 0 END, updated_at = ?",
            (DEFAULT_LOCATION_ID, now),
        )


def _default_row(*, selected: bool = True) -> dict[str, Any]:
    now = _utc()
    root = _default_root()
    return {
        "location_id": DEFAULT_LOCATION_ID,
        "kind": "private_default",
        "display_name": "Pocket Lab private backup folder",
        "root_path": str(root),
        "canonical_root": str(root),
        "repository_id": "restic:default-private",
        "repository_fingerprint": "",
        "is_default": 1,
        "is_selected": 1 if selected else 0,
        "is_removable": 0,
        "is_forgotten": 0,
        "status": "checking",
        "reason_code": "",
        "free_bytes": None,
        "capacity_bytes": None,
        "repository_present": 0,
        "last_checked_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _read_rows(*, include_forgotten: bool = False) -> list[dict[str, Any]]:
    _schema()
    with connection() as conn:
        clause = "" if include_forgotten else " WHERE is_forgotten = 0"
        rows = [dict(item) for item in conn.execute(
            f"SELECT * FROM recovery_backup_locations{clause} ORDER BY is_default DESC, display_name ASC"
        ).fetchall()]
    if not any(str(item.get("location_id") or "") == DEFAULT_LOCATION_ID for item in rows):
        rows.insert(0, _default_row(selected=not any(bool(item.get("is_selected")) for item in rows)))
    elif not any(bool(item.get("is_selected")) and not bool(item.get("is_forgotten")) for item in rows):
        for item in rows:
            if str(item.get("location_id") or "") == DEFAULT_LOCATION_ID:
                item["is_selected"] = 1
                break
    return rows


def _row(location_id: str) -> dict[str, Any] | None:
    value = str(location_id or "")
    return next((item for item in _read_rows(include_forgotten=True) if str(item.get("location_id") or "") == value), None)


def _all_rows(*, include_forgotten: bool = False) -> list[dict[str, Any]]:
    return _read_rows(include_forgotten=include_forgotten)


def _custom_root(row: dict[str, Any]) -> Path:
    """Resolve a registered custom root without permitting symlink escapes."""
    raw = Path(str(row.get("root_path") or "")).expanduser()
    resolved = _validate_custom_root(raw, allow_missing=True)
    if resolved != raw:
        raise BackupLocationError("symlink_not_allowed", "The selected backup location cannot be a symbolic link.")
    return resolved


def _reject_symlink_path(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise BackupLocationError("storage_unavailable", "The selected backup location is unavailable.") from exc
    if path.is_symlink() or resolved != path:
        raise BackupLocationError("symlink_not_allowed", "The selected backup location cannot be a symbolic link.")
    return path


def _ensure_custom_root(row: dict[str, Any]) -> None:
    root = _custom_root(row)
    if root.exists():
        if not root.is_dir():
            raise BackupLocationError("not_a_directory", "The selected backup location is not a directory.")
        return
    _validate_custom_root(root, allow_missing=False)
    root.mkdir(parents=False, exist_ok=True)
    _reject_symlink_path(root)
    layout_root = _reject_symlink_path(root / CUSTOM_LAYOUT_FOLDER)
    layout_root.mkdir(parents=False, exist_ok=True)
    _reject_symlink_path(layout_root)


def layout_for_location(location_id: str | None = None, *, allow_forgotten: bool = False):
    """Build a repository layout for an opaque location id.

    The default layout remains byte-for-byte compatible with the historical
    location.  Custom repositories use a private ``PocketLab`` child folder;
    the shared default password file remains the backend-owned credential so
    credentials are not copied into Android storage.
    """
    from .lite_backup_policy import LiteBackupLayout, backup_layout

    selected = str(location_id or DEFAULT_LOCATION_ID).strip() or DEFAULT_LOCATION_ID
    row = _row(selected)
    if not row:
        raise BackupLocationError("location_not_found", "The selected backup location is no longer registered.")
    if bool(row.get("is_forgotten")) and not allow_forgotten:
        raise BackupLocationError("location_forgotten", "Discover this backup location again before using it.")
    if selected == DEFAULT_LOCATION_ID or bool(row.get("is_default")):
        return backup_layout()
    root = _reject_symlink_path(_custom_root(row) / CUSTOM_LAYOUT_FOLDER)
    default = backup_layout()
    return LiteBackupLayout(
        root=root,
        repository=root / "restic-repo",
        manifests=root / "manifests",
        receipts=root / "receipts",
        restore_previews=root / "restore-previews",
        restore_checkpoints=root / "restore-checkpoints",
        restore_runs=root / "restore-runs",
        staging=root / ".staging",
        password_file=default.password_file,
    )


def selected_location_id() -> str:
    rows = _all_rows()
    for item in rows:
        if bool(item.get("is_selected")):
            return str(item.get("location_id"))
    return DEFAULT_LOCATION_ID


def location_metadata(location_id: str | None = None) -> dict[str, Any]:
    selected = str(location_id or DEFAULT_LOCATION_ID).strip() or DEFAULT_LOCATION_ID
    row = _row(selected)
    if not row:
        if selected == DEFAULT_LOCATION_ID:
            return {
                "location_id": DEFAULT_LOCATION_ID,
                "display_name": "Pocket Lab private backup folder",
                "kind": "private_default",
                "repository_id": "restic:default-private",
                "repository_fingerprint": "",
            }
        raise BackupLocationError("location_not_found", "The selected backup location is no longer registered.")
    return {
        "location_id": str(row.get("location_id")),
        "display_name": str(row.get("display_name") or "Configured backup location")[:120],
        "kind": str(row.get("kind") or "configured"),
        "repository_id": str(row.get("repository_id") or "")[:120],
        "repository_fingerprint": str(row.get("repository_fingerprint") or "")[:64],
        "is_default": bool(row.get("is_default")),
    }


def repository_fingerprint(location_id: str | None = None, layout: Any | None = None) -> str:
    selected = str(location_id or DEFAULT_LOCATION_ID).strip() or DEFAULT_LOCATION_ID
    current = layout or layout_for_location(selected)
    config = current.repository / "config"
    try:
        return hashlib.sha256(config.read_bytes()).hexdigest()[:32]
    except OSError:
        return str(location_metadata(selected).get("repository_fingerprint") or hashlib.sha256(
            str(location_metadata(selected).get("repository_id") or selected).encode("utf-8")
        ).hexdigest()[:32])


def _minimum_free_bytes() -> int:
    raw = os.environ.get("POCKETLAB_LITE_BACKUP_MIN_FREE_BYTES", str(MIN_FREE_BYTES_DEFAULT))
    try:
        return max(1, min(int(raw), 1 << 50))
    except ValueError:
        return MIN_FREE_BYTES_DEFAULT


def _health_for_row(row: dict[str, Any]) -> dict[str, Any]:
    location_id = str(row.get("location_id") or "")
    is_default = bool(row.get("is_default"))
    try:
        root = _default_root() if is_default else _custom_root(row)
    except BackupLocationError as exc:
        return {
            "status": "unavailable",
            "reason_code": exc.reason_code,
            "available": False,
            "writable": False,
            "repository_present": False,
            "repository_fingerprint": "",
            "free_bytes": None,
            "capacity_bytes": None,
            "checked_at": _utc(),
            "layout": None,
        }
    root_exists = root.exists()
    if not is_default and not root_exists and row.get("last_checked_at"):
        return {
            "status": "missing",
            "reason_code": "storage_unavailable",
            "available": False,
            "writable": False,
            "repository_present": False,
            "repository_fingerprint": "",
            "free_bytes": None,
            "capacity_bytes": None,
            "checked_at": _utc(),
            "layout": None,
        }
    probe = root if root_exists else root.parent
    free_bytes: int | None = None
    capacity_bytes: int | None = None
    if probe.exists() and probe.is_dir():
        try:
            usage = shutil.disk_usage(probe)
            free_bytes = int(usage.free)
            capacity_bytes = int(usage.total)
        except OSError:
            pass
    writable = bool(probe.exists() and probe.is_dir())
    if writable:
        try:
            writable = bool(os.access(probe, os.W_OK) and (probe.stat().st_mode & 0o222))
        except OSError:
            writable = False
    layout = None
    repository_present = False
    current_fingerprint = ""
    layout_error: BackupLocationError | None = None
    try:
        layout = layout_for_location(location_id)
        repository_present = bool((layout.repository / "config").is_file())
        if repository_present:
            current_fingerprint = hashlib.sha256((layout.repository / "config").read_bytes()).hexdigest()[:32]
    except BackupLocationError as exc:
        layout_error = exc
    if layout_error:
        status, reason, available = "unavailable", layout_error.reason_code, False
    elif not probe.exists() or not probe.is_dir():
        status, reason = "missing", "storage_unavailable"
        available = False
    elif not writable:
        status, reason = "read_only", "storage_not_writable"
        available = False
    elif free_bytes is not None and free_bytes < _minimum_free_bytes():
        status, reason = "low_space", "low_free_space"
        available = False
    elif repository_present:
        status, reason = "ready", "repository_ready"
        available = True
    else:
        status, reason = "available", "repository_not_initialized"
        available = True
    if is_default and status == "missing":
        # The legacy default is created lazily by the backup worker.  It is a
        # valid selection even when the folder has not been initialized yet.
        status, reason, available = "available", "will_create", True
    return {
        "status": status,
        "reason_code": reason,
        "available": available,
        "writable": writable,
        "repository_present": repository_present,
        "repository_fingerprint": current_fingerprint,
        "free_bytes": free_bytes,
        "capacity_bytes": capacity_bytes,
        "checked_at": _utc(),
        "layout": layout,
    }


def _update_health(row: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    now = str(health.get("checked_at") or _utc())
    with connection() as conn:
        conn.execute(
            """
            UPDATE recovery_backup_locations
            SET status = ?, reason_code = ?, free_bytes = ?, capacity_bytes = ?,
                repository_present = ?, repository_fingerprint = ?,
                last_checked_at = ?, updated_at = ?
            WHERE location_id = ?
            """,
            (
                health.get("status"),
                health.get("reason_code") or "",
                health.get("free_bytes"),
                health.get("capacity_bytes"),
                1 if health.get("repository_present") else 0,
                health.get("repository_fingerprint") or str(row.get("repository_fingerprint") or ""),
                now,
                now,
                row.get("location_id"),
            ),
        )
        refreshed = conn.execute(
            "SELECT * FROM recovery_backup_locations WHERE location_id = ?",
            (row.get("location_id"),),
        ).fetchone()
    return dict(refreshed) if refreshed else row


def _public(row: dict[str, Any], *, health: dict[str, Any] | None = None) -> dict[str, Any]:
    current = health or _health_for_row(row)
    return {
        "location_id": str(row.get("location_id") or ""),
        "kind": str(row.get("kind") or "configured"),
        "display_name": str(row.get("display_name") or "Configured backup location")[:120],
        "is_default": bool(row.get("is_default")),
        "is_selected": bool(row.get("is_selected")),
        "is_removable": bool(row.get("is_removable")),
        "status": current.get("status") or row.get("status") or "checking",
        "reason_code": current.get("reason_code") or row.get("reason_code") or "",
        "available": bool(current.get("available")),
        "writable": bool(current.get("writable")),
        "repository_present": bool(current.get("repository_present")),
        "repository_id": str(row.get("repository_id") or "")[:120],
        "repository_fingerprint": str(current.get("repository_fingerprint") or row.get("repository_fingerprint") or "")[:64],
        "free_bytes": current.get("free_bytes"),
        "capacity_bytes": current.get("capacity_bytes"),
        "last_checked_at": current.get("checked_at") or row.get("last_checked_at"),
        "sanitized": True,
    }


def _public_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    path = Path(spec["path"])
    health = _health_for_row({
        "location_id": spec["candidate_id"],
        "root_path": str(path),
        "is_default": 0,
        "is_forgotten": 0,
        "repository_id": f"restic:{spec['candidate_id']}",
        "repository_fingerprint": "",
    })
    return {
        "candidate_id": spec["candidate_id"],
        "kind": spec["kind"],
        "display_name": spec["display_name"],
        "status": health.get("status"),
        "reason_code": health.get("reason_code"),
        "available": bool(health.get("available")),
        "writable": bool(health.get("writable")),
        "is_removable": bool(spec.get("is_removable")),
        "sanitized": True,
    }


def _record_event(
    *, event_type: str, row: dict[str, Any], status: str, reason_code: str = "", actor: dict[str, Any] | None = None
) -> None:
    actor = actor or {}
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO recovery_backup_location_events(
                occurred_at, event_type, location_id, kind, status, reason_code,
                summary, actor_type, auth_method, sanitized
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                _utc(),
                str(event_type or "location.updated")[:80],
                str(row.get("location_id") or "")[:120],
                str(row.get("kind") or "configured")[:40],
                str(status or "unknown")[:40],
                str(reason_code or "")[:80],
                "Backup location registry changed for the protected Server Host.",
                str(actor.get("actor_type") or "authenticated")[:32],
                str(actor.get("auth_method") or "")[:48],
            ),
        )


def locations_projection() -> dict[str, Any]:
    rows = _all_rows()
    locations: list[dict[str, Any]] = []
    for row in rows:
        health = _health_for_row(row)
        locations.append(_public(row, health=health))
    registered = {item["location_id"] for item in locations}
    candidates = [item for item in (_public_candidate(spec) for spec in _candidate_specs()) if item["candidate_id"] not in registered]
    selected = next((item for item in locations if item.get("is_selected")), None)
    return {
        "status": "ready" if selected and selected.get("available") else "review",
        "summary": "Backup location is backend-managed on this protected Server Host.",
        "server_host_only": True,
        "selected_location_id": selected.get("location_id") if selected else DEFAULT_LOCATION_ID,
        "selected_location": selected,
        "default_location_id": DEFAULT_LOCATION_ID,
        "locations": locations,
        "candidates": candidates,
        "picker": {
            "system_folder_picker": "not_implemented",
            "selection_mode": "backend_discovered_candidates",
            "raw_paths_accepted": False,
        },
        "updated_at": _utc(),
        "sanitized": True,
    }


def discover_candidate(candidate_id: str, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    _schema()
    value = str(candidate_id or "").strip()
    spec = next((item for item in _candidate_specs() if item["candidate_id"] == value), None)
    if not spec:
        raise BackupLocationError("candidate_not_found", "That backend-discovered storage candidate is no longer available.")
    root = _validate_custom_root(Path(spec["path"]), allow_missing=True)
    now = _utc()
    with connection() as conn:
        _ensure_default(conn)
        conn.execute(
            """
            INSERT INTO recovery_backup_locations(
                location_id, kind, display_name, root_path, canonical_root,
                repository_id, repository_fingerprint, is_default, is_selected,
                is_removable, is_forgotten, status, reason_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '', 0, 0, ?, 0, 'checking', '', ?, ?)
            ON CONFLICT(location_id) DO UPDATE SET
                kind=excluded.kind, display_name=excluded.display_name,
                root_path=excluded.root_path, canonical_root=excluded.canonical_root,
                is_removable=excluded.is_removable, is_forgotten=0, updated_at=excluded.updated_at
            """,
            (
                spec["candidate_id"],
                spec["kind"],
                spec["display_name"],
                str(root),
                str(root),
                f"restic:{spec['candidate_id']}",
                1 if spec.get("is_removable") else 0,
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM recovery_backup_locations WHERE location_id = ?",
            (spec["candidate_id"],),
        ).fetchone()
    resolved = dict(row) if row else {}
    _record_event(event_type="location.discovered", row=resolved, status="registered", actor=actor)
    return locations_projection()


def register_location(
    root_path: str | Path,
    *,
    display_name: str | None = None,
    kind: str | None = None,
    is_removable: bool | None = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a path only for trusted backend callers and qualification tests.

    There is intentionally no HTTP path-registration endpoint.  Production
    browser flows use ``discover_candidate`` so arbitrary browser paths cannot
    become repositories.
    """
    _schema()
    root = _validate_custom_root(Path(root_path), allow_missing=True)
    detected_kind, detected_label, detected_removable = _classify_candidate(root)
    location_id = _location_id(root)
    now = _utc()
    with connection() as conn:
        _ensure_default(conn)
        conn.execute(
            """
            INSERT INTO recovery_backup_locations(
                location_id, kind, display_name, root_path, canonical_root,
                repository_id, repository_fingerprint, is_default, is_selected,
                is_removable, is_forgotten, status, reason_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '', 0, 0, ?, 0, 'checking', '', ?, ?)
            ON CONFLICT(location_id) DO UPDATE SET
                kind=excluded.kind, display_name=excluded.display_name,
                root_path=excluded.root_path, canonical_root=excluded.canonical_root,
                is_removable=excluded.is_removable, is_forgotten=0, updated_at=excluded.updated_at
            """,
            (
                location_id,
                kind or detected_kind,
                str(display_name or detected_label)[:120],
                str(root),
                str(root),
                f"restic:{location_id}",
                1 if (detected_removable if is_removable is None else bool(is_removable)) else 0,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM recovery_backup_locations WHERE location_id = ?", (location_id,)).fetchone()
    resolved = dict(row) if row else {"location_id": location_id, "kind": kind or detected_kind}
    _record_event(event_type="location.registered", row=resolved, status="registered", actor=actor)
    return locations_projection()


def select_location(location_id: str, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    value = str(location_id or "").strip()
    if is_operation_busy():
        raise BackupLocationError("operation_in_progress", "Backup location changes are paused while Recovery work is running.")
    row = _row(value)
    if not row or bool(row.get("is_forgotten")):
        raise BackupLocationError("location_not_found", "Choose a registered backup location.")
    health = _health_for_row(row)
    if not health.get("available"):
        raise BackupLocationError(str(health.get("reason_code") or "location_unavailable"), "That backup location is not currently writable.")
    if value != DEFAULT_LOCATION_ID and not bool(row.get("is_default")):
        _ensure_custom_root(row)
    now = _utc()
    with connection() as conn:
        _ensure_default(conn)
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE recovery_backup_locations SET is_selected = 0, updated_at = ?", (now,))
            tx.execute(
                "UPDATE recovery_backup_locations SET is_selected = 1, is_forgotten = 0, updated_at = ? WHERE location_id = ?",
                (now, value),
            )
            selected = tx.execute(
                "SELECT * FROM recovery_backup_locations WHERE location_id = ?",
                (value,),
            ).fetchone()
    resolved = dict(selected) if selected else row
    if value != DEFAULT_LOCATION_ID and not bool(resolved.get("is_default")):
        resolved = _update_health(resolved, _health_for_row(resolved))
    _record_event(event_type="location.selected", row=resolved, status="selected", reason_code=str(health.get("reason_code") or ""), actor=actor)
    try:
        from . import lite_backup

        lite_backup._touch_recovery_projection()
    except Exception:
        pass
    return locations_projection()


def forget_location(location_id: str, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    value = str(location_id or "").strip()
    if is_operation_busy():
        raise BackupLocationError("operation_in_progress", "Backup location changes are paused while Recovery work is running.")
    row = _row(value)
    if not row or bool(row.get("is_forgotten")):
        raise BackupLocationError("location_not_found", "Choose a registered backup location.")
    if bool(row.get("is_default")):
        raise BackupLocationError("default_location_required", "The private default backup location cannot be forgotten.")
    now = _utc()
    with connection() as conn:
        _ensure_default(conn)
        with begin_immediate(conn) as tx:
            tx.execute(
                "UPDATE recovery_backup_locations SET is_selected = 0, is_forgotten = 1, updated_at = ? WHERE location_id = ?",
                (now, value),
            )
            tx.execute(
                "UPDATE recovery_backup_locations SET is_selected = 1, updated_at = ? WHERE location_id = ? AND NOT EXISTS (SELECT 1 FROM recovery_backup_locations WHERE is_selected = 1 AND is_forgotten = 0)",
                (now, DEFAULT_LOCATION_ID),
            )
            forgotten = tx.execute(
                "SELECT * FROM recovery_backup_locations WHERE location_id = ?",
                (value,),
            ).fetchone()
    resolved = dict(forgotten) if forgotten else row
    _record_event(event_type="location.forgotten", row=resolved, status="forgotten", actor=actor)
    try:
        from . import lite_backup

        lite_backup._touch_recovery_projection()
    except Exception:
        pass
    return locations_projection()


def manifest_location(manifest: dict[str, Any]) -> dict[str, Any]:
    location_id = str(manifest.get("location_id") or DEFAULT_LOCATION_ID).strip() or DEFAULT_LOCATION_ID
    metadata = location_metadata(location_id)
    repository = manifest.get("repository") if isinstance(manifest.get("repository"), dict) else {}
    result = {
        **metadata,
        "available": False,
        "status": "unavailable",
        "reason_code": "location_not_registered",
    }
    row = _row(location_id)
    if row and not bool(row.get("is_forgotten")):
        health = _health_for_row(row)
        result.update({
            "available": bool(health.get("available")),
            "status": health.get("status"),
            "reason_code": health.get("reason_code"),
        })
    if not result.get("display_name"):
        result["display_name"] = str(repository.get("location") or "Configured encrypted repository")[:120]
    return result


def layout_for_manifest(manifest: dict[str, Any]):
    """Resolve and validate the immutable repository binding for a restore point."""
    location_id = str(manifest.get("location_id") or DEFAULT_LOCATION_ID).strip() or DEFAULT_LOCATION_ID
    try:
        layout = layout_for_location(location_id)
    except BackupLocationError as exc:
        raise BackupLocationError(
            exc.reason_code,
            "The backup location for this restore point is unavailable. Discover it again before continuing.",
        ) from exc
    location = manifest_location(manifest)
    if location.get("available") is not True:
        raise BackupLocationError(
            str(location.get("reason_code") or "location_unavailable"),
            "The backup location for this restore point is unavailable. Discover it again before continuing.",
        )
    stored = manifest.get("backup_location") if isinstance(manifest.get("backup_location"), dict) else {}
    expected = str(stored.get("repository_fingerprint") or "").strip()
    if expected:
        config = layout.repository / "config"
        if not config.is_file():
            raise BackupLocationError("repository_missing", "The encrypted repository for this restore point is unavailable.")
        try:
            actual = hashlib.sha256(config.read_bytes()).hexdigest()[:32]
        except OSError as exc:
            raise BackupLocationError("repository_unreadable", "The encrypted repository for this restore point cannot be read.") from exc
        if actual != expected:
            raise BackupLocationError("repository_identity_mismatch", "The repository no longer matches this restore point.")
    return layout


def is_operation_busy() -> bool:
    try:
        from . import lite_backup

        return lite_backup._BACKUP_OPERATION_LOCK.locked()
    except Exception:
        return False
