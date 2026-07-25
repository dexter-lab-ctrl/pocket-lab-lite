from __future__ import annotations

"""Bounded semantic source revisions for prepared Lite projections.

The callbacks in this module are probes only. They never execute shell commands,
network calls, backup/restore work, scanner work, or live collectors. Each probe
reads a bounded set of sanitized lifecycle metadata and returns a deterministic
positive 63-bit revision that ignores display-time drift.
"""

from dataclasses import dataclass
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Iterable

from .. import deps
from ..db.runtime import SQLITE_READS


_SCHEMA_VERSION = 1
_MAX_JSON_BYTES = 512 * 1024
_MAX_CONTAINER_ITEMS = 64
_MAX_DB_ROWS = 64
_MAX_MANIFEST_ENTRIES = 256

_VOLATILE_KEY = re.compile(
    r"(?:^|_)(?:generated|checked|requested|created|updated|completed|verified|"
    r"observed|seen|started|finished|expires|refreshed|received|published|"
    r"queued|accepted|failed|succeeded|saved|last_ran|first_ran)_?at(?:$|_)|"
    r"(?:^|_)(?:timestamp|epoch|age|elapsed|duration|latency|poll|retry_after|"
    r"projection_age|cache_age|seconds_ago)(?:$|_)",
    re.IGNORECASE,
)
_SENSITIVE_KEY = re.compile(
    r"(?:token|password|passwd|secret|credential|api[_-]?key|private[_-]?key|"
    r"cookie|authorization|bootstrap|command_payload|raw_log|raw_evidence|"
    r"database_url|nats_url|restic_password|hash|checksum|sha256)",
    re.IGNORECASE,
)
_NOISE_KEYS = frozenset(
    {
        "summary",
        "message",
        "description",
        "details",
        "technical_details",
        "evidence",
        "evidence_refs",
        "evidence_references",
        "troubleshooting",
        "display_label",
        "last_checked_text",
        "age_text",
    }
)
_SEMANTIC_SCALAR_KEYS = frozenset(
    {
        "id",
        "app_id",
        "device_id",
        "host_device_id",
        "operation_id",
        "command_id",
        "action_id",
        "latest_action_id",
        "latest_action_status",
        "latest_backup_id",
        "backup_id",
        "preview_id",
        "restore_id",
        "maintenance_id",
        "target_id",
        "mapping_id",
        "run_id",
        "generation",
        "revision",
        "schema_version",
        "projection_version",
        "status",
        "state",
        "phase",
        "step",
        "lifecycle_stage",
        "recovery_action",
        "operation_type",
        "install_state",
        "health",
        "health_state",
        "verification_status",
        "maintenance_status",
        "connection_state",
        "agent_status",
        "supervisor_status",
        "pm2_status",
        "role",
        "category",
        "risk",
        "mode",
        "version",
        "desired_version",
        "installed_version",
        "available_version",
        "process",
        "route",
        "path",
        "upstream",
        "source_kind",
        "target_kind",
        "installed",
        "enabled",
        "active",
        "ready",
        "reachable",
        "connected",
        "available",
        "eligible",
        "route_ready",
        "https_ready",
        "remote_access_ready",
        "rollback_available",
        "restore_allowed",
        "read_degraded",
        "refresh_pending",
        "current",
        "total",
        "percent",
        "size_bytes",
        "count",
        "ready_count",
        "attention_count",
        "media_included",
        "scope",
        "file",
        "truncated",
    }
)
_CONTAINER_KEYS = frozenset(
    {
        "apps",
        "items",
        "operations",
        "actions",
        "routes",
        "runtime",
        "access",
        "progress",
        "last_operation",
        "current_action",
        "pending_backup",
        "pending_restore_preview",
        "latest_backup",
        "last_backup",
        "latest_restore_preview",
        "last_restore",
        "active_operation",
        "maintenance",
        "database_protection",
        "backup_targets",
        "targets",
        "mappings",
        "storage",
        "media",
        "update",
        "backup",
        "recovery",
        "security",
        "verification",
        "target_statuses",
        "files",
        "value",
        "rows",
        "commands",
        "manifests",
        "related_domain_revisions",
        "current_state",
        "compatibility_files",
    }
)

_APP_SCOPE_FILES: dict[str, tuple[str, ...]] = {
    "catalog": (
        "lite_catalog_state.json",
        "app_routes.json",
        "lite_app_update_state.json",
        "lite_app_backup_state.json",
        "lite_app_storage_mappings.json",
        "lite_photoprism_media_operations.json",
    ),
    "lifecycle": (
        "lite_catalog_state.json",
        "app_routes.json",
        "lite_app_update_state.json",
        "lite_app_backup_state.json",
        "lite_app_storage_mappings.json",
        "lite_photoprism_media_operations.json",
    ),
    "actions": (
        "lite_catalog_state.json",
        "lite_app_update_state.json",
        "lite_app_backup_state.json",
        "lite_app_storage_mappings.json",
        "lite_photoprism_media_operations.json",
    ),
    "update": (
        "lite_catalog_state.json",
        "lite_app_update_state.json",
    ),
    "backup": (
        "lite_catalog_state.json",
        "lite_app_backup_state.json",
        "backup_state.json",
    ),
}
_RECOVERY_SUMMARY_FILES = (
    "backup_state.json",
    "lite_app_backup_state.json",
    "recovery.json",
    "security/maintenance/maintenance-state.json",
)
_RECOVERY_DETAILS_FILES = (
    *_RECOVERY_SUMMARY_FILES,
    "lite_app_storage_mappings.json",
    "lite_app_update_state.json",
)

# Append-only compatibility journals are not semantic current-state authorities.
# They may grow beyond the bounded probe budget on long-lived edge nodes.
_COMPATIBILITY_APPEND_FILES = frozenset({"lite_app_operations.json"})


@dataclass(frozen=True, slots=True)
class ProjectionRevisionContract:
    source_revision: Callable[[], int]
    max_probe_seconds: float
    quiet_window_seconds: float
    priority: int
    work_class: str
    deadline_seconds: float


_PROBE_LOCK = threading.Lock()
_PROBE_DIAGNOSTICS: dict[str, dict[str, Any]] = {}
_FILE_CACHE_LOCK = threading.Lock()
_FILE_SEMANTIC_CACHE: dict[str, tuple[tuple[int, int, int], dict[str, Any]]] = {}
_MAX_FILE_CACHE_ENTRIES = 96
_UNSAFE_SOURCE_STATES = frozenset(
    {"invalid", "oversized", "not_file", "database_unavailable", "database_read_failed"}
)


class SemanticSourceUnavailable(RuntimeError):
    """A bounded source probe could not prove a safe semantic revision."""


def _bounded_text(value: Any) -> str:
    text = str(value or "").strip()
    return text[:192]


def _semantic_value(value: Any, *, key: str = "", parent: str = "", depth: int = 0) -> Any:
    if depth > 7:
        return None
    normalized_key = str(key or "").strip().lower()
    if normalized_key and (
        normalized_key in _NOISE_KEYS
        or _VOLATILE_KEY.search(normalized_key)
        or _SENSITIVE_KEY.search(normalized_key)
    ):
        return None
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        parent_is_container = normalized_key in _CONTAINER_KEYS or str(parent).lower() in _CONTAINER_KEYS
        for child_key in sorted(value, key=lambda item: str(item))[:_MAX_CONTAINER_ITEMS]:
            child_name = str(child_key)
            child_normalized = child_name.strip().lower()
            if (
                child_normalized in _NOISE_KEYS
                or _VOLATILE_KEY.search(child_normalized)
                or _SENSITIVE_KEY.search(child_normalized)
            ):
                continue
            child_value = value[child_key]
            allowed = (
                child_normalized in _SEMANTIC_SCALAR_KEYS
                or child_normalized in _CONTAINER_KEYS
                or parent_is_container
                or isinstance(child_value, (dict, list, tuple))
            )
            if not allowed:
                continue
            semantic = _semantic_value(
                child_value,
                key=child_normalized,
                parent=normalized_key,
                depth=depth + 1,
            )
            if semantic is not None and semantic not in ({}, []):
                output[child_name[:96]] = semantic
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [
            _semantic_value(item, key="", parent=normalized_key, depth=depth + 1)
            for item in list(value)[:_MAX_CONTAINER_ITEMS]
        ]
        visible = [item for item in items if item is not None and item not in ({}, [])]
        return sorted(
            visible,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), default=str),
        )
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return max(-(2**63), min(2**63 - 1, value))
    if isinstance(value, float):
        return round(value, 6)
    if value is None:
        return None
    if normalized_key and normalized_key not in _SEMANTIC_SCALAR_KEYS and str(parent).lower() not in _CONTAINER_KEYS:
        return None
    return _bounded_text(value)


def canonical_semantic_revision(namespace: str, material: Any, *, schema_version: int = _SCHEMA_VERSION) -> int:
    canonical = json.dumps(
        {
            "namespace": str(namespace or "lite")[:96],
            "schema_version": max(1, int(schema_version)),
            "material": _semantic_value(material, key="root"),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    revision = int.from_bytes(hashlib.sha256(canonical.encode("utf-8")).digest()[:8], "big")
    return max(1, revision & ((1 << 63) - 1))


def _read_json_semantics(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"file": path.name, "state": "missing"}
    if not path.is_file():
        return {"file": path.name, "state": "not_file"}
    if stat.st_size > _MAX_JSON_BYTES:
        return {"file": path.name, "state": "oversized"}

    cache_key = str(path)[:1024]
    fingerprint = (
        int(getattr(stat, "st_ino", 0) or 0),
        int(stat.st_size),
        int(getattr(stat, "st_mtime_ns", 0) or 0),
    )
    with _FILE_CACHE_LOCK:
        cached = _FILE_SEMANTIC_CACHE.get(cache_key)
        if cached is not None and cached[0] == fingerprint:
            return dict(cached[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        result = {"file": path.name, "state": "invalid"}
    else:
        result = {
            "file": path.name,
            "state": "ready",
            "value": _semantic_value(payload, key="root"),
        }
    with _FILE_CACHE_LOCK:
        if len(_FILE_SEMANTIC_CACHE) >= _MAX_FILE_CACHE_ENTRIES:
            _FILE_SEMANTIC_CACHE.pop(next(iter(_FILE_SEMANTIC_CACHE)), None)
        _FILE_SEMANTIC_CACHE[cache_key] = (fingerprint, dict(result))
    return result


def _read_rows(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    try:
        entry, _wait_ms = SQLITE_READS.acquire(timeout_seconds=0.35)
    except Exception:
        return [{"state": "database_unavailable"}]
    discard = False
    try:
        return [dict(row) for row in entry.connection.execute(sql, tuple(params)).fetchall()]
    except Exception:
        discard = True
        return [{"state": "database_read_failed"}]
    finally:
        SQLITE_READS.release(entry, discard=discard)


def _app_current_rows(app_id: str) -> list[dict[str, Any]]:
    return _read_rows(
        "SELECT app_id,app_name,status,installed,health_state,latest_action_id,"
        "latest_action_status,latest_backup_id,source_revision,summary,"
        "catalog_state_json,media_state_json,operation_state_json,"
        "update_state_json,backup_profile_json,security_profile_json,"
        "backup_targets_json,projection_version "
        "FROM app_current_state WHERE app_id=? LIMIT 1",
        (str(app_id or "photoprism")[:120],),
    )


def _compatibility_file_diagnostics(state_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in sorted(_COMPATIBILITY_APPEND_FILES):
        path = state_dir / name
        try:
            stat = path.stat()
        except OSError:
            items.append({"file": name, "state": "missing", "semantic_authority": False})
            continue
        items.append(
            {
                "file": name,
                "state": "excluded_compatibility",
                "semantic_authority": False,
            }
        )
    return items


def _app_command_rows(app_id: str) -> list[dict[str, Any]]:
    return _read_rows(
        "SELECT command_id,entity_id,operation_type,status,lifecycle_stage,recovery_action "
        "FROM command_lifecycle WHERE entity_type='app' AND entity_id=? "
        "ORDER BY updated_at_epoch_ms DESC,command_id DESC LIMIT ?",
        (str(app_id or "photoprism")[:120], _MAX_DB_ROWS),
    )


def _latest_app_security_rows(app_id: str) -> list[dict[str, Any]]:
    return _read_rows(
        "SELECT run_id,profile,app_id,status,score FROM security_scan_runs "
        "WHERE profile='app' AND app_id=? "
        "ORDER BY COALESCE(completed_at_epoch_ms,updated_at_epoch_ms,requested_at_epoch_ms) DESC,run_id DESC LIMIT 4",
        (str(app_id or "photoprism")[:120],),
    )


def _recovery_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "commands": _read_rows(
            "SELECT command_id,entity_id,operation_type,status,lifecycle_stage,recovery_action "
            "FROM command_lifecycle WHERE operation_type LIKE '%backup%' "
            "OR operation_type LIKE '%restore%' OR operation_type LIKE '%recovery%' "
            "OR operation_type LIKE '%maintenance%' "
            "ORDER BY updated_at_epoch_ms DESC,command_id DESC LIMIT ?",
            (_MAX_DB_ROWS,),
        ),
        "maintenance": _read_rows(
            "SELECT maintenance_id,kind,mode,status FROM security_maintenance_runs "
            "ORDER BY requested_at DESC,maintenance_id DESC LIMIT 16"
        ),
        "database_backups": _read_rows(
            "SELECT backup_id,status,size_bytes,schema_version FROM security_database_backups "
            "ORDER BY created_at DESC,backup_id DESC LIMIT 16"
        ),
        "database_restores": _read_rows(
            "SELECT restore_id,backup_id,preview_id,state FROM security_database_restores "
            "ORDER BY requested_at DESC,restore_id DESC LIMIT 16"
        ),
    }


def _backup_root() -> Path:
    configured = os.environ.get("POCKETLAB_LITE_BACKUP_ROOT")
    return Path(configured).expanduser() if configured else Path.home() / "pocket-lab-lite-backups"


def _manifest_index_rows() -> list[dict[str, Any]]:
    """Return bounded backup current-state metadata without parsing historical manifests."""
    return _read_rows(
        "SELECT backup_id,backup_type,status,verification_status,size_bytes,summary "
        "FROM backup_manifest_index "
        "ORDER BY updated_at_epoch_ms DESC,backup_id DESC LIMIT ?",
        (_MAX_DB_ROWS,),
    )


def _manifest_semantics() -> dict[str, Any]:
    """Use SQLite metadata as authority; full manifest JSON is compatibility history only."""
    return {
        "state": "ready",
        "semantic_authority": "backup_manifest_index",
        "rows": _manifest_index_rows(),
        "compatibility_files": {
            "state": "excluded_compatibility",
            "semantic_authority": False,
            "kind": "backup_manifest",
        },
    }




def _unsafe_source_state(value: Any, *, depth: int = 0) -> str:
    if depth > 8:
        return ""
    if isinstance(value, dict):
        state = str(value.get("state") or "").strip().lower()
        if state in _UNSAFE_SOURCE_STATES:
            return state
        for child in value.values():
            unsafe = _unsafe_source_state(child, depth=depth + 1)
            if unsafe:
                return unsafe
    elif isinstance(value, (list, tuple)):
        for child in value[:_MAX_CONTAINER_ITEMS]:
            unsafe = _unsafe_source_state(child, depth=depth + 1)
            if unsafe:
                return unsafe
    return ""

def _record_probe(name: str, started: float, material: Any, error_type: str = "") -> None:
    duration_ms = max(0.0, (time.monotonic() - started) * 1000.0)
    item_count = 0
    if isinstance(material, dict):
        item_count = len(material)
    elif isinstance(material, (list, tuple)):
        item_count = len(material)
    with _PROBE_LOCK:
        _PROBE_DIAGNOSTICS[name] = {
            "last_probe_duration_ms": round(duration_ms, 3),
            "item_count": min(10_000, item_count),
            "last_error_type": str(error_type or "")[:80],
            "bounded": True,
            "sanitized": True,
        }


def _probe(name: str, callback: Callable[[], Any]) -> int:
    started = time.monotonic()
    material: Any = {}
    try:
        material = callback()
        unsafe_state = _unsafe_source_state(material)
        if unsafe_state:
            raise SemanticSourceUnavailable(unsafe_state)
        revision = canonical_semantic_revision(name, material)
    except Exception as exc:
        _record_probe(name, started, material, type(exc).__name__)
        raise
    _record_probe(name, started, material)
    return revision


def app_semantic_material(
    *,
    scope: str = "lifecycle",
    app_id: str = "photoprism",
    include_manifests: bool = False,
) -> dict[str, Any]:
    normalized_scope = str(scope or "lifecycle").strip().lower()
    files = _APP_SCOPE_FILES.get(normalized_scope, _APP_SCOPE_FILES["lifecycle"])
    state_dir = deps.settings().state_dir
    material: dict[str, Any] = {
        "scope": normalized_scope,
        "app_id": str(app_id or "photoprism")[:120],
        "files": [_read_json_semantics(state_dir / name) for name in files],
        "compatibility_files": _compatibility_file_diagnostics(state_dir),
        "current_state": _app_current_rows(app_id),
        "commands": _app_command_rows(app_id),
    }
    if include_manifests and normalized_scope == "backup":
        material["manifests"] = _manifest_semantics()
    if normalized_scope in {"catalog", "lifecycle", "actions"}:
        material["security"] = _latest_app_security_rows(app_id)
    return material


def app_source_revision(*, scope: str = "lifecycle", app_id: str = "photoprism") -> int:
    name = f"apps.{str(scope or 'lifecycle').lower()}:{str(app_id or 'photoprism').lower()}"
    return _probe(name, lambda: app_semantic_material(scope=scope, app_id=app_id))


def recovery_summary_material() -> dict[str, Any]:
    state_dir = deps.settings().state_dir
    return {
        "files": [_read_json_semantics(state_dir / name) for name in _RECOVERY_SUMMARY_FILES],
        "manifests": _manifest_semantics(),
        "rows": _recovery_rows(),
    }


def recovery_summary_source_revision() -> int:
    return _probe("recovery.summary", recovery_summary_material)


def recovery_details_material() -> dict[str, Any]:
    state_dir = deps.settings().state_dir
    fleet_revision_rows = _read_rows(
        "SELECT domain,revision FROM domain_revisions WHERE domain IN ('fleet','storage') ORDER BY domain"
    )
    return {
        "files": [_read_json_semantics(state_dir / name) for name in _RECOVERY_DETAILS_FILES],
        "summary": recovery_summary_material(),
        "apps": app_semantic_material(
            scope="lifecycle", app_id="photoprism", include_manifests=False
        ),
        "related_domain_revisions": fleet_revision_rows,
    }


def recovery_details_source_revision() -> int:
    return _probe("recovery.details", recovery_details_material)


def contract_for(domain: str, key: str) -> ProjectionRevisionContract | None:
    safe_domain = str(domain or "").strip().lower()
    safe_key = str(key or "").strip().lower()
    if safe_domain == "apps":
        app_id = safe_key.split(":", 1)[1] if ":" in safe_key else "photoprism"
        if safe_key == "catalog":
            return ProjectionRevisionContract(
                source_revision=partial(app_source_revision, scope="catalog", app_id="photoprism"),
                max_probe_seconds=300.0,
                quiet_window_seconds=1.0,
                priority=45,
                work_class="io",
                deadline_seconds=8.0,
            )
        if safe_key == "lifecycle":
            return ProjectionRevisionContract(
                source_revision=partial(app_source_revision, scope="lifecycle", app_id="photoprism"),
                max_probe_seconds=300.0,
                quiet_window_seconds=1.0,
                priority=35,
                work_class="cpu",
                deadline_seconds=8.0,
            )
        if safe_key.startswith("actions:"):
            return ProjectionRevisionContract(
                source_revision=partial(app_source_revision, scope="actions", app_id=app_id),
                max_probe_seconds=120.0,
                quiet_window_seconds=0.75,
                priority=30,
                work_class="io",
                deadline_seconds=6.0,
            )
        if safe_key.startswith("update:"):
            return ProjectionRevisionContract(
                source_revision=partial(app_source_revision, scope="update", app_id=app_id),
                max_probe_seconds=300.0,
                quiet_window_seconds=1.0,
                priority=45,
                work_class="io",
                deadline_seconds=6.0,
            )
        if safe_key.startswith("backup:"):
            return ProjectionRevisionContract(
                source_revision=partial(app_source_revision, scope="backup", app_id=app_id),
                max_probe_seconds=300.0,
                quiet_window_seconds=1.0,
                priority=55,
                work_class="io",
                deadline_seconds=6.0,
            )
    if safe_domain == "recovery" and safe_key == "summary":
        return ProjectionRevisionContract(
            source_revision=recovery_summary_source_revision,
            max_probe_seconds=300.0,
            quiet_window_seconds=1.0,
            priority=50,
            work_class="io",
            deadline_seconds=8.0,
        )
    if safe_domain == "recovery" and safe_key == "details":
        return ProjectionRevisionContract(
            source_revision=recovery_details_source_revision,
            max_probe_seconds=600.0,
            quiet_window_seconds=1.5,
            priority=60,
            work_class="io",
            deadline_seconds=10.0,
        )
    phase3b_domain = f"{safe_domain}.{safe_key}"
    if phase3b_domain in {
        "security.progress",
        "security.summary",
        "system.status",
        "system.health",
        "system.processes",
        "system.agent",
        "system.supervisor",
        "system.remote_access",
        "system.nats_remote",
        "system.fleet_probe",
    }:
        from .lite_phase3b_projections import source_revision_for

        critical = phase3b_domain in {"security.progress", "system.nats_remote"}
        high_priority = phase3b_domain in {
            "security.progress", "security.summary", "system.status", "system.health"
        }
        return ProjectionRevisionContract(
            source_revision=source_revision_for(phase3b_domain),
            max_probe_seconds=(
                30.0 if phase3b_domain == "security.progress"
                else 60.0 if phase3b_domain in {
                    "system.nats_remote", "system.agent", "system.supervisor"
                }
                else 300.0
            ),
            quiet_window_seconds=0.25 if phase3b_domain == "security.progress" else 1.0,
            priority=(10 if phase3b_domain == "security.progress" else 20 if high_priority else 40),
            work_class="critical" if critical else "io",
            deadline_seconds=(
                10.0 if phase3b_domain in {"system.processes", "system.remote_access"}
                else 8.0
            ),
        )
    phase3c_domain = f"{safe_domain}.{safe_key}"
    if phase3c_domain in {
        "system.telemetry_thresholds",
        "system.storage_pressure",
        "system.sqlite_health",
        "system.activity_summary",
    }:
        from .lite_phase3c_projections import source_revision_for

        return ProjectionRevisionContract(
            source_revision=source_revision_for(phase3c_domain),
            max_probe_seconds=(
                120.0 if phase3c_domain == "system.activity_summary"
                else 1800.0 if phase3c_domain == "system.sqlite_health"
                else 300.0
            ),
            quiet_window_seconds=1.0,
            priority=(25 if phase3c_domain == "system.sqlite_health" else 35 if phase3c_domain == "system.storage_pressure" else 45),
            work_class="io",
            deadline_seconds=8.0,
        )
    return None


def diagnostics() -> dict[str, Any]:
    with _PROBE_LOCK:
        probes = {key: dict(value) for key, value in sorted(_PROBE_DIAGNOSTICS.items())}
    with _FILE_CACHE_LOCK:
        file_cache_entries = min(len(_FILE_SEMANTIC_CACHE), _MAX_FILE_CACHE_ENTRIES)
    return {
        "schema_version": _SCHEMA_VERSION,
        "probes": probes,
        "probe_count": len(probes),
        "file_cache_entries": file_cache_entries,
        "sanitized": True,
    }
