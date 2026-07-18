from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..db.connection import (
    begin_immediate,
    connection,
    database_path,
    open_fast_read_connection,
    progress_read_timeout_ms,
    read_connection,
)
from ..db.migrations import apply_migrations
from . import lite_security_evidence as evidence
from . import lite_storage_faults
from . import lite_security_policy as policy


ACTIVE_STATUSES = frozenset({"queued", "accepted", "running", "working", "in_progress"})
TERMINAL_STATUSES = frozenset({"succeeded", "degraded", "failed", "cancelled"})
VALID_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES
STORE_MODES = frozenset({"json", "dual", "sqlite"})
MAX_METADATA_BYTES = 32 * 1024
DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 100
DEFAULT_RECENT_COMPLETION_SECONDS = 45
MAX_RECENT_COMPLETION_SECONDS = 300
IMPORT_VERSION = 1
_INITIALIZED_DATABASES: set[Path] = set()
_INITIALIZE_LOCK = threading.Lock()


@dataclass(frozen=True)
class ReservationResult:
    reserved: bool
    reason: str
    run: dict[str, Any]


@dataclass
class ImportReport:
    preview: bool
    source_root: str
    source_checksum: str
    runs_seen: int = 0
    runs_imported: int = 0
    runs_skipped: int = 0
    findings_imported: int = 0
    tools_imported: int = 0
    evidence_refs_imported: int = 0
    runs_deleted: int = 0
    reconciled: bool = False
    parity_matched: bool | None = None
    malformed_optional_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return policy.redact_value(asdict(self))


class SecurityStoreError(RuntimeError):
    """Base error for the inactive SQLite Security repository."""


class SecurityReconciliationError(SecurityStoreError):
    """Canonical JSON reconciliation failed strict in-transaction parity."""

    def __init__(self, message: str, *, mismatch_fields: Iterable[str]) -> None:
        super().__init__(message)
        self.mismatch_fields = sorted({str(field) for field in mismatch_fields})


class InvalidSecurityStoreValue(SecurityStoreError):
    """A status/profile/app/run value is outside the repository contract."""


class SecurityProgressReadContention(SecurityStoreError):
    """A latency-sensitive Progress read could not obtain SQLite promptly."""

    def __init__(self, message: str, *, connection_wait_ms: float, query_ms: float) -> None:
        super().__init__(message)
        self.connection_wait_ms = float(connection_wait_ms)
        self.query_ms = float(query_ms)


@dataclass(frozen=True)
class ProgressReadResult:
    progress: dict[str, Any] | None
    connection_wait_ms: float
    query_ms: float
    projection_build_ms: float


_PROGRESS_COLUMNS = """
    r.run_id,
    r.profile,
    r.app_id,
    r.status,
    r.current_stage,
    r.current_percent,
    r.current_message,
    r.current_tool,
    r.updated_at,
    r.updated_at_epoch_ms,
    r.requested_at,
    r.requested_at_epoch_ms,
    r.command_published_at,
    r.command_received_at,
    r.execution_started_at,
    r.last_progress_at,
    r.delivery_attempt,
    r.revision AS run_revision,
    COALESCE(pe.event_id, 0) AS event_id,
    COALESCE(pe.sequence_no, 0) AS sequence_no,
    COALESCE(dr.revision, 0) AS domain_revision
"""
_PROGRESS_LATEST_SQL = f"""
    SELECT {_PROGRESS_COLUMNS}
    FROM security_scan_runs AS r
    LEFT JOIN security_scan_progress_events AS pe
      ON pe.event_id = (
        SELECT event_id
        FROM security_scan_progress_events
        WHERE run_id = r.run_id
        ORDER BY event_id DESC
        LIMIT 1
      )
    LEFT JOIN domain_revisions AS dr ON dr.domain = 'security'
    ORDER BY (r.active_key IS NOT NULL) DESC, r.updated_at_epoch_ms DESC
    LIMIT 1
"""
_PROGRESS_RUN_SQL = f"""
    SELECT {_PROGRESS_COLUMNS}
    FROM security_scan_runs AS r
    LEFT JOIN security_scan_progress_events AS pe
      ON pe.event_id = (
        SELECT event_id
        FROM security_scan_progress_events
        WHERE run_id = r.run_id
        ORDER BY event_id DESC
        LIMIT 1
      )
    LEFT JOIN domain_revisions AS dr ON dr.domain = 'security'
    WHERE r.run_id = ?
    LIMIT 1
"""
_PROGRESS_EVENT_SELECT = """
    SELECT
        pe.event_id,
        pe.run_id,
        pe.sequence_no,
        pe.status,
        pe.stage,
        pe.percent,
        pe.message,
        pe.tool,
        pe.created_at,
        pe.created_at_epoch_ms,
        pe.payload_json,
        r.profile,
        r.app_id,
        r.updated_at AS run_updated_at,
        r.updated_at_epoch_ms AS run_updated_at_epoch_ms,
        r.revision AS run_revision,
        COALESCE(dr.revision, 0) AS domain_revision
    FROM security_scan_progress_events AS pe
    JOIN security_scan_runs AS r ON r.run_id = pe.run_id
    LEFT JOIN domain_revisions AS dr ON dr.domain = 'security'
"""


def _progress_event_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["event_id"] = int(item.get("event_id") or 0)
    item["sequence_no"] = int(item.get("sequence_no") or 0)
    item["percent"] = max(0, min(100, int(item.get("percent") or 0)))
    item["created_at_epoch_ms"] = int(item.get("created_at_epoch_ms") or 0)
    item["run_updated_at_epoch_ms"] = int(item.get("run_updated_at_epoch_ms") or 0)
    item["run_revision"] = int(item.get("run_revision") or 0)
    item["domain_revision"] = int(item.get("domain_revision") or 0)
    item["payload"] = _json_value(item.pop("payload_json", None), {})
    return policy.redact_value(item)


def _progress_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    run = dict(row)
    status = str(run.get("status") or "")
    return policy.redact_value({
        "run_id": run.get("run_id"),
        "profile": run.get("profile"),
        "app_id": run.get("app_id"),
        "status": status,
        "stage": run.get("current_stage"),
        "percent": run.get("current_percent"),
        "message": run.get("current_message"),
        "tool": run.get("current_tool"),
        "updated_at": run.get("updated_at"),
        "updated_at_epoch_ms": int(run.get("updated_at_epoch_ms") or 0),
        "requested_at": run.get("requested_at"),
        "requested_at_epoch_ms": int(run.get("requested_at_epoch_ms") or 0),
        "command_published_at": run.get("command_published_at"),
        "command_received_at": run.get("command_received_at"),
        "execution_started_at": run.get("execution_started_at"),
        "last_progress_at": run.get("last_progress_at"),
        "delivery_attempt": int(run.get("delivery_attempt") or 0),
        "run_revision": int(run.get("run_revision") or 0),
        "active_scan": status in ACTIVE_STATUSES,
        "event_id": int(run.get("event_id") or 0),
        "sequence_no": int(run.get("sequence_no") or 0),
        "domain_revision": int(run.get("domain_revision") or 0),
    })


class SecurityProgressReader:
    """Dedicated reusable read-only connection for live Progress projection."""

    def __init__(self, *, timeout_ms: int | None = None) -> None:
        self.timeout_ms = (
            progress_read_timeout_ms()
            if timeout_ms is None
            else max(25, min(int(timeout_ms), 2_000))
        )
        self._connection: sqlite3.Connection | None = None

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            connection.close()

    def _ensure_connection(self) -> float:
        if self._connection is not None:
            return 0.0
        started = time.monotonic()
        self._connection = open_fast_read_connection(timeout_ms=self.timeout_ms)
        return (time.monotonic() - started) * 1000

    def read(self, run_id: str | None = None) -> ProgressReadResult:
        connection_wait_ms = self._ensure_connection()
        query_started = time.monotonic()
        try:
            if run_id:
                row = self._connection.execute(
                    _PROGRESS_RUN_SQL,
                    (_normalize_run_id(run_id),),
                ).fetchone()
            else:
                row = self._connection.execute(_PROGRESS_LATEST_SQL).fetchone()
        except sqlite3.OperationalError as exc:
            query_ms = (time.monotonic() - query_started) * 1000
            message = str(exc).lower()
            if "locked" in message or "busy" in message:
                raise SecurityProgressReadContention(
                    "Security Progress SQLite read was busy",
                    connection_wait_ms=connection_wait_ms,
                    query_ms=query_ms,
                ) from exc
            self.close()
            raise
        query_ms = (time.monotonic() - query_started) * 1000
        projection_started = time.monotonic()
        progress = _progress_payload(row)
        projection_build_ms = (time.monotonic() - projection_started) * 1000
        return ProgressReadResult(
            progress=progress,
            connection_wait_ms=connection_wait_ms,
            query_ms=query_ms,
            projection_build_ms=projection_build_ms,
        )

    def __enter__(self) -> "SecurityProgressReader":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any, *, default: str | None = None) -> str:
    text = str(value or default or utc_now()).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _history_sort_key(item: Mapping[str, Any]) -> tuple[int, str]:
    epoch = item.get("completed_at_epoch_ms")
    if epoch is None:
        epoch = item.get("updated_at_epoch_ms")
    if epoch is None:
        epoch = item.get("requested_at_epoch_ms")
    if epoch is None:
        timestamp = (
            item.get("completed_at")
            or item.get("updated_at")
            or item.get("requested_at")
        )
        epoch = _epoch_ms(timestamp) if timestamp else 0
    return int(epoch or 0), str(item.get("run_id") or "")


def _canonical_history(
    items: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = None,
) -> list[Mapping[str, Any]]:
    ordered = sorted(
        (item for item in items if str(item.get("run_id") or "").strip()),
        key=_history_sort_key,
        reverse=True,
    )
    return ordered if limit is None else ordered[: max(0, int(limit))]


def _epoch_ms(value: Any) -> int:
    parsed = datetime.fromisoformat(_parse_timestamp(value).replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def security_store_mode() -> str:
    mode = os.environ.get("POCKETLAB_LITE_SECURITY_STORE_MODE", "json").strip().lower()
    if mode not in STORE_MODES:
        raise InvalidSecurityStoreValue(
            "POCKETLAB_LITE_SECURITY_STORE_MODE must be json, dual, or sqlite"
        )
    return mode


def sqlite_shadow_read_enabled() -> bool:
    value = os.environ.get("POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ", "0").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"", "0", "false", "no", "off"}:
        return False
    raise InvalidSecurityStoreValue(
        "POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ must be 0 or 1"
    )




def _bounded_environment_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise InvalidSecurityStoreValue(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise InvalidSecurityStoreValue(f"{name} must be between {minimum} and {maximum}")
    return value


def security_accepted_stale_seconds() -> int:
    return _bounded_environment_int(
        "POCKETLAB_LITE_SECURITY_ACCEPTED_STALE_SECONDS",
        120,
        minimum=30,
        maximum=3600,
    )


def security_received_stale_seconds() -> int:
    return _bounded_environment_int(
        "POCKETLAB_LITE_SECURITY_RECEIVED_STALE_SECONDS",
        180,
        minimum=30,
        maximum=7200,
    )


def security_published_stale_seconds() -> int:
    return _bounded_environment_int(
        "POCKETLAB_LITE_SECURITY_PUBLISHED_STALE_SECONDS",
        security_accepted_stale_seconds(),
        minimum=30,
        maximum=7200,
    )


def security_recent_completion_seconds() -> int:
    return _bounded_environment_int(
        "POCKETLAB_LITE_SECURITY_RECENT_COMPLETION_SECONDS",
        DEFAULT_RECENT_COMPLETION_SECONDS,
        minimum=0,
        maximum=MAX_RECENT_COMPLETION_SECONDS,
    )


def sqlite_compact_reads_enabled() -> bool:
    mode = security_store_mode()
    if mode == "sqlite":
        return True
    if mode == "json":
        return False
    value = os.environ.get(
        "POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "0"
    ).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"", "0", "false", "no", "off"}:
        return False
    raise InvalidSecurityStoreValue(
        "POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS must be 0 or 1"
    )


def sqlite_lifecycle_writes_enabled() -> bool:
    return security_store_mode() in {"dual", "sqlite"}

def _normalize_profile(value: Any) -> str:
    try:
        return policy.normalize_scan_profile(value)
    except ValueError as exc:
        raise InvalidSecurityStoreValue(str(exc)) from exc


def _normalize_app(profile: str, value: Any) -> str:
    if profile != policy.SCAN_PROFILE_APP:
        return ""
    try:
        return policy.normalize_app_id(value)
    except ValueError as exc:
        raise InvalidSecurityStoreValue(str(exc)) from exc


def _normalize_run_id(value: Any) -> str:
    normalized = evidence.safe_run_id(str(value or ""))
    if normalized == "unknown" or len(normalized) > 120:
        raise InvalidSecurityStoreValue("Security run_id is required")
    return normalized


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "waiting": "queued",
        "complete": "succeeded",
        "completed": "succeeded",
        "success": "succeeded",
        "done": "succeeded",
        "review": "degraded",
        "partial": "degraded",
        "canceled": "cancelled",
        "error": "failed",
        "timed_out": "failed",
        "timeout": "failed",
        "interrupted": "failed",
        "submit_failed": "failed",
    }
    normalized = aliases.get(raw, raw)
    if normalized not in VALID_STATUSES:
        raise InvalidSecurityStoreValue(f"Unsupported Security status: {raw or '<empty>'}")
    return normalized


def _active_key(profile: str, app_id: str) -> str:
    scope = os.environ.get("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global").strip().lower()
    if scope == "global":
        return "security:global"
    if scope != "profile":
        raise InvalidSecurityStoreValue(
            "POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE must be global or profile"
        )
    return f"security:{profile}:{app_id}" if profile == policy.SCAN_PROFILE_APP else f"security:{profile}:"


def _safe_json(value: Any, *, max_bytes: int = MAX_METADATA_BYTES) -> str | None:
    if value in (None, {}, []):
        return None
    clean = policy.redact_value(value)
    encoded = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    raw = encoded.encode("utf-8")
    if len(raw) > max_bytes:
        digest = hashlib.sha256(raw).hexdigest()
        encoded = json.dumps(
            {"truncated": True, "sha256": digest, "original_bytes": len(raw)},
            separators=(",", ":"),
        )
    return encoded


def _json_value(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = dict(row)
    payload["partial_results"] = bool(payload.get("partial_results"))
    payload["evidence_saved"] = bool(payload.get("evidence_saved"))
    payload["metadata"] = _json_value(payload.pop("metadata_json", None), {})
    return policy.redact_value(payload)


def _bump_revision(conn: sqlite3.Connection, at: str | None = None) -> int:
    updated_at = _parse_timestamp(at)
    conn.execute(
        """
        INSERT INTO domain_revisions(domain, revision, updated_at)
        VALUES ('security', 1, ?)
        ON CONFLICT(domain) DO UPDATE SET
            revision = domain_revisions.revision + 1,
            updated_at = excluded.updated_at
        """,
        (updated_at,),
    )
    row = conn.execute(
        "SELECT revision FROM domain_revisions WHERE domain = ?", ("security",)
    ).fetchone()
    return int(row["revision"])


def _set_metadata(conn: sqlite3.Connection, key: str, value: Any, *, at: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO security_store_metadata(metadata_key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(metadata_key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        """,
        (str(key)[:160], _safe_json(value) or "{}", _parse_timestamp(at)),
    )


def _get_metadata(conn: sqlite3.Connection, key: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT value_json FROM security_store_metadata WHERE metadata_key = ?",
        (str(key)[:160],),
    ).fetchone()
    return _json_value(row["value_json"], {}) if row else {}


def _normalized_finding_identity_material(finding: Mapping[str, Any]) -> list[str]:
    technical = finding.get("technical") if isinstance(finding.get("technical"), Mapping) else {}
    source = str(finding.get("source") or "security").strip().lower()[:80]
    category = str(finding.get("category") or technical.get("category") or "finding").strip().lower()[:120]
    component = str(finding.get("component") or "").strip().lower()[:160]
    safe_target = str(
        finding.get("file") or finding.get("target") or technical.get("file") or technical.get("target") or ""
    ).strip().replace("\\", "/").lower()[:300]
    if category == "protected_runtime_secret" or "protected backend runtime secret" in str(
        finding.get("title") or finding.get("summary") or ""
    ).strip().lower():
        # A protected-runtime-secret is a posture item, not a raw secret match.
        # Scanner IDs, line numbers, match values, and redacted payload fragments are volatile,
        # so identity is intentionally scoped to the sanitized component posture.
        return [source, "protected_runtime_secret", component or "pocket-lab-lite"]
    rule_id = str(finding.get("rule_id") or finding.get("id") or category or "finding").strip().lower()[:240]
    return [source, category, rule_id, component, safe_target]


def _finding_key(finding: Mapping[str, Any]) -> tuple[str, str]:
    material = _normalized_finding_identity_material(finding)
    digest = hashlib.sha256(json.dumps(material, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    return f"{material[0]}:{digest[:24]}", digest


def _progress_fingerprint(
    run_id: str,
    status: str,
    stage: str | None,
    percent: int | None,
    message: str | None,
    tool: str | None,
) -> str:
    material = policy.redact_value([run_id, status, stage or "", percent, message or "", tool or ""])
    return hashlib.sha256(json.dumps(material, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class SecuritySQLiteRepository:
    """Transactional Security repository for shadow import, dual-write, and compact reads."""

    def __init__(self, *, initialize: bool = True) -> None:
        if initialize:
            path = database_path()
            with _INITIALIZE_LOCK:
                if path not in _INITIALIZED_DATABASES:
                    apply_migrations()
                    _INITIALIZED_DATABASES.add(path)

    @property
    def path(self) -> Path:
        return database_path()

    def reserve_scan(
        self,
        *,
        run_id: str,
        profile: str,
        app_id: str | None = None,
        app_label: str | None = None,
        summary: str = "",
        requested_at: str | None = None,
        command_id: str | None = None,
        correlation_id: str | None = None,
        recent_completion_seconds: int = 0,
        timing_sink: dict[str, float] | None = None,
    ) -> ReservationResult:
        total_started = time.monotonic()
        lite_storage_faults.raise_if_storage_fault("sqlite_lifecycle_write")
        normalize_started = total_started
        normalized_profile = _normalize_profile(profile)
        normalized_app = _normalize_app(normalized_profile, app_id)
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(requested_at)
        now_epoch = _epoch_ms(now)
        active_key = _active_key(normalized_profile, normalized_app)
        normalize_done = time.monotonic()
        connection_started = normalize_done
        connection_timing: dict[str, float] = {}
        with connection(timing_sink=connection_timing) as conn:
            connection_done = time.monotonic()
            begin_started = connection_done
            with begin_immediate(conn) as tx:
                begin_done = time.monotonic()
                active_started = begin_done
                active = tx.execute(
                    "SELECT * FROM security_scan_runs WHERE active_key = ? ORDER BY updated_at_epoch_ms DESC LIMIT 1",
                    (active_key,),
                ).fetchone()
                active_done = time.monotonic()
                if active:
                    result_started = active_done
                    result = ReservationResult(False, "active", _row(active) or {})
                    result_done = time.monotonic()
                    if timing_sink is not None:
                        timing_sink.update({
                            "normalize_ms": max(0.0, (normalize_done-normalize_started)*1000.0),
                            "connection_wait_ms": max(0.0, (connection_done-connection_started)*1000.0),
                            "connection_path_resolve_ms": float(connection_timing.get("path_resolve_ms") or 0.0),
                            "connection_sqlite_connect_ms": float(connection_timing.get("sqlite_connect_ms") or 0.0),
                            "connection_pragma_setup_ms": float(connection_timing.get("pragma_setup_ms") or 0.0),
                            "begin_wait_ms": max(0.0, (begin_done-begin_started)*1000.0),
                            "active_lookup_ms": max(0.0, (active_done-active_started)*1000.0),
                            "recent_lookup_ms": 0.0,
                            "write_ms": 0.0,
                            "commit_ms": 0.0,
                            "result_build_ms": max(0.0, (result_done-result_started)*1000.0),
                            "total_ms": max(0.0, (result_done-total_started)*1000.0),
                        })
                    return result
                recent_started = active_done
                recent_window = max(
                    0, min(int(recent_completion_seconds), MAX_RECENT_COMPLETION_SECONDS)
                )
                recent = None
                if recent_window > 0:
                    cutoff = now_epoch - recent_window * 1000
                    recent = tx.execute(
                        """
                        SELECT * FROM security_scan_runs
                        WHERE profile = ? AND app_id = ? AND status IN ('succeeded', 'degraded')
                          AND completed_at_epoch_ms >= ?
                        ORDER BY completed_at_epoch_ms DESC LIMIT 1
                        """,
                        (normalized_profile, normalized_app, cutoff),
                    ).fetchone()
                recent_done = time.monotonic()
                if recent:
                    result_started = recent_done
                    result = ReservationResult(False, "recent_completion", _row(recent) or {})
                    result_done = time.monotonic()
                    if timing_sink is not None:
                        timing_sink.update({
                            "normalize_ms": max(0.0, (normalize_done-normalize_started)*1000.0),
                            "connection_wait_ms": max(0.0, (connection_done-connection_started)*1000.0),
                            "connection_path_resolve_ms": float(connection_timing.get("path_resolve_ms") or 0.0),
                            "connection_sqlite_connect_ms": float(connection_timing.get("sqlite_connect_ms") or 0.0),
                            "connection_pragma_setup_ms": float(connection_timing.get("pragma_setup_ms") or 0.0),
                            "begin_wait_ms": max(0.0, (begin_done-begin_started)*1000.0),
                            "active_lookup_ms": max(0.0, (active_done-active_started)*1000.0),
                            "recent_lookup_ms": max(0.0, (recent_done-recent_started)*1000.0),
                            "write_ms": 0.0,
                            "commit_ms": 0.0,
                            "result_build_ms": max(0.0, (result_done-result_started)*1000.0),
                            "total_ms": max(0.0, (result_done-total_started)*1000.0),
                        })
                    return result
                write_started = recent_done
                tx.execute(
                    """
                    INSERT INTO security_scan_runs(
                        run_id, profile, app_id, app_label, status, active_key, summary,
                        requested_at, updated_at, requested_at_epoch_ms, updated_at_epoch_ms,
                        command_id, correlation_id, source, revision
                    ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, 'security-api', 1)
                    """,
                    (
                        normalized_run, normalized_profile, normalized_app,
                        str(app_label or "")[:120], active_key,
                        policy.redact_text(summary)[:500], now, now, now_epoch, now_epoch,
                        str(command_id or "")[:160] or None,
                        str(correlation_id or "")[:160] or None,
                    ),
                )
                queued_message = policy.redact_text(summary)[:500] or "Security check queued."
                fingerprint = _progress_fingerprint(
                    normalized_run, "queued", "queued", 5, queued_message, None
                )
                tx.execute(
                    """
                    INSERT INTO security_scan_progress_events(
                        run_id, sequence_no, status, stage, percent, message, tool,
                        created_at, created_at_epoch_ms, payload_json, fingerprint
                    ) VALUES (?, 1, 'queued', 'queued', 5, ?, NULL, ?, ?, NULL, ?)
                    """,
                    (normalized_run, queued_message, now, now_epoch, fingerprint),
                )
                domain_revision = _bump_revision(tx, now)
                write_done = time.monotonic()
            commit_done = time.monotonic()
        result_started = commit_done
        run = {
            "run_id": normalized_run,
            "profile": normalized_profile,
            "app_id": normalized_app,
            "app_label": str(app_label or "")[:120],
            "status": "queued",
            "active_key": active_key,
            "summary": queued_message,
            "requested_at": now,
            "updated_at": now,
            "requested_at_epoch_ms": now_epoch,
            "updated_at_epoch_ms": now_epoch,
            "command_id": str(command_id or "")[:160] or None,
            "correlation_id": str(correlation_id or "")[:160] or None,
            "source": "security-api",
            "revision": 1,
            "percent": 5,
            "stage": "queued",
            "message": queued_message,
            "domain_revision": domain_revision,
        }
        result = ReservationResult(True, "reserved", run)
        result_done = time.monotonic()
        if timing_sink is not None:
            timing_sink.update({
                "normalize_ms": max(0.0, (normalize_done-normalize_started)*1000.0),
                "connection_wait_ms": max(0.0, (connection_done-connection_started)*1000.0),
                "connection_path_resolve_ms": float(connection_timing.get("path_resolve_ms") or 0.0),
                "connection_sqlite_connect_ms": float(connection_timing.get("sqlite_connect_ms") or 0.0),
                "connection_pragma_setup_ms": float(connection_timing.get("pragma_setup_ms") or 0.0),
                "begin_wait_ms": max(0.0, (begin_done-begin_started)*1000.0),
                "active_lookup_ms": max(0.0, (active_done-active_started)*1000.0),
                "recent_lookup_ms": max(0.0, (recent_done-recent_started)*1000.0),
                "write_ms": max(0.0, (write_done-write_started)*1000.0),
                "commit_ms": max(0.0, (commit_done-write_done)*1000.0),
                "result_build_ms": max(0.0, (result_done-result_started)*1000.0),
                "total_ms": max(0.0, (result_done-total_started)*1000.0),
            })
        return result

    def get_active_scan(self, profile: str | None = None, app_id: str | None = None) -> dict[str, Any] | None:
        with read_connection() as conn:
            if profile is None:
                row = conn.execute(
                    "SELECT * FROM security_scan_runs WHERE active_key IS NOT NULL ORDER BY updated_at_epoch_ms DESC LIMIT 1"
                ).fetchone()
            else:
                normalized_profile = _normalize_profile(profile)
                normalized_app = _normalize_app(normalized_profile, app_id)
                row = conn.execute(
                    "SELECT * FROM security_scan_runs WHERE active_key = ? ORDER BY updated_at_epoch_ms DESC LIMIT 1",
                    (_active_key(normalized_profile, normalized_app),),
                ).fetchone()
        return _row(row)

    def list_stale_start_candidates(
        self,
        *,
        now: str | None = None,
        published_stale_seconds: int | None = None,
        received_stale_seconds: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return queued/accepted runs that have not begun execution.

        Published-but-never-received and received-but-never-started states use
        separate bounded thresholds. Running rows are deliberately excluded.
        """
        current_time = _parse_timestamp(now)
        current_epoch = _epoch_ms(current_time)
        published_threshold = max(
            30,
            min(
                int(
                    published_stale_seconds
                    if published_stale_seconds is not None
                    else security_published_stale_seconds()
                ),
                7200,
            ),
        )
        received_threshold = max(
            30,
            min(
                int(
                    received_stale_seconds
                    if received_stale_seconds is not None
                    else security_received_stale_seconds()
                ),
                7200,
            ),
        )
        published_cutoff = current_epoch - published_threshold * 1000
        received_cutoff = current_epoch - received_threshold * 1000
        bounded = max(1, min(int(limit), 50))
        with read_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM security_scan_runs
                WHERE status IN ('queued', 'accepted')
                  AND active_key IS NOT NULL
                  AND execution_started_at IS NULL
                  AND (
                    (command_received_at IS NULL
                     AND COALESCE(command_published_at_epoch_ms, updated_at_epoch_ms) <= ?)
                    OR
                    (command_received_at IS NOT NULL
                     AND command_received_at_epoch_ms <= ?)
                  )
                ORDER BY updated_at_epoch_ms ASC
                LIMIT ?
                """,
                (published_cutoff, received_cutoff, bounded),
            ).fetchall()
        payload: list[dict[str, Any]] = []
        for row in rows:
            item = _row(row) or {}
            item["stale_state"] = (
                "published_not_received"
                if not item.get("command_received_at")
                else "received_not_started"
            )
            payload.append(item)
        return policy.redact_value(payload)

    def list_stale_accepted_runs(
        self,
        *,
        now: str | None = None,
        stale_seconds: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Backward-compatible accepted-start watchdog query."""
        candidates = self.list_stale_start_candidates(
            now=now,
            published_stale_seconds=stale_seconds,
            received_stale_seconds=stale_seconds,
            limit=limit,
        )
        return [item for item in candidates if item.get("status") == "accepted"]

    def fail_stale_start_run(
        self,
        run_id: str,
        *,
        expected_status: str,
        expected_revision: int,
        expected_updated_at_epoch_ms: int,
        expected_active_key: str,
        completed_at: str | None = None,
        failure_code: str = "worker_start_timeout",
    ) -> dict[str, Any] | None:
        """Terminalize one unchanged pre-execution run using compare-and-set."""
        normalized_run = _normalize_run_id(run_id)
        normalized_status = _normalize_status(expected_status)
        if normalized_status not in {"queued", "accepted"}:
            return None
        now = _parse_timestamp(completed_at)
        now_epoch = _epoch_ms(now)
        summary = "The safety check could not start. Try again."
        stage = "Safety check could not start"
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
            if not current:
                return None
            if (
                str(current["status"]) != normalized_status
                or str(current["active_key"] or "") != str(expected_active_key or "")
                or int(current["revision"] or 0) != int(expected_revision)
                or int(current["updated_at_epoch_ms"] or 0)
                != int(expected_updated_at_epoch_ms)
                or current["execution_started_at"] is not None
            ):
                return None
            percent = int(current["current_percent"] or 0)
            cursor = tx.execute(
                """
                UPDATE security_scan_runs
                SET status = 'failed', active_key = NULL, summary = ?,
                    completed_at = ?, completed_at_epoch_ms = ?,
                    updated_at = ?, updated_at_epoch_ms = ?,
                    current_stage = ?, current_percent = ?, current_message = ?,
                    failure_code = ?, failure_message = ?, revision = revision + 1
                WHERE run_id = ? AND status = ? AND revision = ?
                  AND updated_at_epoch_ms = ? AND active_key = ?
                  AND execution_started_at IS NULL
                """,
                (
                    summary, now, now_epoch, now, now_epoch, stage, percent,
                    summary, policy.redact_text(failure_code)[:120], summary,
                    normalized_run, normalized_status, int(expected_revision),
                    int(expected_updated_at_epoch_ms), str(expected_active_key),
                ),
            )
            if cursor.rowcount != 1:
                return None
            event = self._append_progress_event(
                tx,
                normalized_run,
                status="failed",
                stage=stage,
                percent=percent,
                message=summary,
                tool=None,
                payload={"failure_code": failure_code},
                created_at=now,
            )
            self._upsert_profile_snapshot(tx, normalized_run, updated_at=now)
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
        result = _row(row) or {}
        result["domain_revision"] = revision
        result["progress_event"] = event
        return policy.redact_value(result)

    def fail_stale_accepted_run(
        self,
        run_id: str,
        *,
        expected_updated_at_epoch_ms: int,
        completed_at: str | None = None,
        expected_revision: int | None = None,
        expected_active_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Backward-compatible accepted-run compare-and-set wrapper."""
        current = self.get_run(run_id) or {}
        return self.fail_stale_start_run(
            run_id,
            expected_status="accepted",
            expected_revision=int(
                expected_revision
                if expected_revision is not None
                else current.get("revision") or 0
            ),
            expected_updated_at_epoch_ms=expected_updated_at_epoch_ms,
            expected_active_key=str(
                expected_active_key
                if expected_active_key is not None
                else current.get("active_key") or ""
            ),
            completed_at=completed_at,
        )

    def get_recent_completion(
        self, profile: str, app_id: str | None = None, *, within_seconds: int = 30
    ) -> dict[str, Any] | None:
        normalized_profile = _normalize_profile(profile)
        normalized_app = _normalize_app(normalized_profile, app_id)
        cutoff = int((datetime.now(timezone.utc) - timedelta(seconds=max(0, within_seconds))).timestamp() * 1000)
        with read_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM security_scan_runs
                WHERE profile = ? AND app_id = ? AND status IN ('succeeded', 'degraded')
                  AND completed_at_epoch_ms >= ?
                ORDER BY completed_at_epoch_ms DESC LIMIT 1
                """,
                (normalized_profile, normalized_app, cutoff),
            ).fetchone()
        return _row(row)

    def mark_command_published(
        self, run_id: str, *, published_at: str | None = None
    ) -> dict[str, Any]:
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(published_at)
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT status FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            if str(current["status"]) in TERMINAL_STATUSES:
                return _row(
                    tx.execute(
                        "SELECT * FROM security_scan_runs WHERE run_id = ?",
                        (normalized_run,),
                    ).fetchone()
                ) or {}
            tx.execute(
                """
                UPDATE security_scan_runs
                SET command_published_at = COALESCE(command_published_at, ?),
                    command_published_at_epoch_ms = COALESCE(command_published_at_epoch_ms, ?),
                    updated_at = ?, updated_at_epoch_ms = ?, revision = revision + 1
                WHERE run_id = ?
                """,
                (now, _epoch_ms(now), now, _epoch_ms(now), normalized_run),
            )
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
        result = _row(row) or {}
        result["domain_revision"] = revision
        return policy.redact_value(result)

    def mark_command_received(
        self,
        run_id: str,
        *,
        received_at: str | None = None,
        delivery_attempt: int = 1,
        published_at: str | None = None,
    ) -> dict[str, Any]:
        """Record worker receipt and repair durable publication evidence.

        The NATS command carries the API-captured publication timestamp. If the
        worker wins the race against the API lifecycle commit, receipt repairs
        command_published_at without changing the worker-owned run status.
        """
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(received_at)
        published = _parse_timestamp(published_at) if published_at else None
        attempt = max(1, min(int(delivery_attempt or 1), 10_000))
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            tx.execute(
                """
                UPDATE security_scan_runs
                SET command_published_at = COALESCE(command_published_at, ?),
                    command_published_at_epoch_ms = COALESCE(command_published_at_epoch_ms, ?),
                    command_received_at = COALESCE(command_received_at, ?),
                    command_received_at_epoch_ms = COALESCE(command_received_at_epoch_ms, ?),
                    delivery_attempt = CASE
                        WHEN delivery_attempt > ? THEN delivery_attempt ELSE ? END,
                    updated_at = CASE
                        WHEN updated_at_epoch_ms > ? THEN updated_at ELSE ? END,
                    updated_at_epoch_ms = CASE
                        WHEN updated_at_epoch_ms > ? THEN updated_at_epoch_ms ELSE ? END,
                    revision = revision + 1
                WHERE run_id = ?
                """,
                (
                    published, _epoch_ms(published) if published else None,
                    now, _epoch_ms(now), attempt, attempt,
                    _epoch_ms(now), now, _epoch_ms(now), _epoch_ms(now), normalized_run,
                ),
            )
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
        result = _row(row) or {}
        result["domain_revision"] = revision
        return policy.redact_value(result)

    def mark_published_and_accepted(
        self, run_id: str, *, published_at: str, accepted_at: str | None = None,
        summary: str = "", timing_sink: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Commit publication evidence and API acceptance in one transaction."""
        total_started = time.monotonic()
        normalized_run = _normalize_run_id(run_id)
        published = _parse_timestamp(published_at)
        accepted = _parse_timestamp(accepted_at)
        accepted_epoch = max(_epoch_ms(published), _epoch_ms(accepted))
        accepted = datetime.fromtimestamp(
            accepted_epoch / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        normalize_done = time.monotonic()
        connection_started = normalize_done
        connection_timing: dict[str, float] = {}
        with connection(timing_sink=connection_timing) as conn:
            connection_done = time.monotonic()
            begin_started = connection_done
            with begin_immediate(conn) as tx:
                begin_done = time.monotonic()
                lookup_started = begin_done
                current = tx.execute(
                    "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
                ).fetchone()
                lookup_done = time.monotonic()
                if not current:
                    raise SecurityStoreError("Security run not found")
                current_status = str(current["status"] or "")
                worker_owned = current_status in TERMINAL_STATUSES or current_status in {
                    "running", "working", "in_progress"
                }
                write_started = lookup_done
                event = None
                if worker_owned:
                    tx.execute(
                        """
                        UPDATE security_scan_runs
                        SET command_published_at = COALESCE(command_published_at, ?),
                            command_published_at_epoch_ms = COALESCE(command_published_at_epoch_ms, ?),
                            accepted_at = COALESCE(accepted_at, ?),
                            revision = revision + 1
                        WHERE run_id = ?
                        """,
                        (published, _epoch_ms(published), accepted, normalized_run),
                    )
                    revision_time = _parse_timestamp(current["updated_at"] or accepted)
                    revision = _bump_revision(tx, revision_time)
                else:
                    tx.execute(
                        """
                        UPDATE security_scan_runs
                        SET status = 'accepted',
                            command_published_at = COALESCE(command_published_at, ?),
                            command_published_at_epoch_ms = COALESCE(command_published_at_epoch_ms, ?),
                            accepted_at = COALESCE(accepted_at, ?),
                            updated_at = ?, updated_at_epoch_ms = ?,
                            summary = CASE WHEN ? = '' THEN summary ELSE ? END,
                            revision = revision + 1
                        WHERE run_id = ?
                        """,
                        (
                            published, _epoch_ms(published), accepted, accepted, accepted_epoch,
                            summary, policy.redact_text(summary)[:500], normalized_run,
                        ),
                    )
                    event = self._append_progress_event(
                        tx, normalized_run, status="accepted", stage="accepted", percent=5,
                        message=summary or "Security check accepted.", tool=None, payload=None,
                        created_at=accepted,
                    )
                    revision = _bump_revision(tx, accepted)
                row = tx.execute(
                    "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
                ).fetchone()
                write_done = time.monotonic()
            commit_done = time.monotonic()
        result_started = commit_done
        result = _row(row) or {}
        result["domain_revision"] = revision
        if worker_owned:
            result["publication_repaired_after_worker_progress"] = True
        elif event is not None:
            result["progress_event"] = event
        result = policy.redact_value(result)
        result_done = time.monotonic()
        if timing_sink is not None:
            timing_sink.update({
                "normalize_ms": max(0.0, (normalize_done-total_started)*1000.0),
                "connection_wait_ms": max(0.0, (connection_done-connection_started)*1000.0),
                "connection_path_resolve_ms": float(connection_timing.get("path_resolve_ms") or 0.0),
                "connection_sqlite_connect_ms": float(connection_timing.get("sqlite_connect_ms") or 0.0),
                "connection_pragma_setup_ms": float(connection_timing.get("pragma_setup_ms") or 0.0),
                "begin_wait_ms": max(0.0, (begin_done-begin_started)*1000.0),
                "lookup_ms": max(0.0, (lookup_done-lookup_started)*1000.0),
                "write_ms": max(0.0, (write_done-write_started)*1000.0),
                "commit_ms": max(0.0, (commit_done-write_done)*1000.0),
                "result_build_ms": max(0.0, (result_done-result_started)*1000.0),
                "total_ms": max(0.0, (result_done-total_started)*1000.0),
            })
        return result

    def mark_accepted(
        self, run_id: str, *, accepted_at: str | None = None, summary: str = ""
    ) -> dict[str, Any]:
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(accepted_at)
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT status FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            current_status = str(current["status"])
            if current_status in TERMINAL_STATUSES or current_status in {"accepted", "running", "working", "in_progress"}:
                return _row(
                    tx.execute(
                        "SELECT * FROM security_scan_runs WHERE run_id = ?",
                        (normalized_run,),
                    ).fetchone()
                ) or {}
            tx.execute(
                """
                UPDATE security_scan_runs
                SET status = 'accepted', accepted_at = COALESCE(accepted_at, ?),
                    updated_at = ?, updated_at_epoch_ms = ?,
                    summary = CASE WHEN ? = '' THEN summary ELSE ? END,
                    revision = revision + 1
                WHERE run_id = ?
                """,
                (
                    now, now, _epoch_ms(now), summary,
                    policy.redact_text(summary)[:500], normalized_run,
                ),
            )
            event = self._append_progress_event(
                tx, normalized_run, status="accepted", stage="accepted", percent=5,
                message=summary or "Security check accepted.", tool=None, payload=None,
                created_at=now,
            )
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
        result = _row(row) or {}
        result["domain_revision"] = revision
        result["progress_event"] = event
        return result

    def mark_running(self, run_id: str, *, started_at: str | None = None, summary: str = "") -> dict[str, Any]:
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(started_at)
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT status FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            if str(current["status"]) in TERMINAL_STATUSES:
                raise SecurityStoreError("Terminal Security run cannot be restarted")
            tx.execute(
                """
                UPDATE security_scan_runs
                SET status = 'running', accepted_at = COALESCE(accepted_at, ?),
                    started_at = COALESCE(started_at, ?),
                    started_at_epoch_ms = COALESCE(started_at_epoch_ms, ?),
                    execution_started_at = COALESCE(execution_started_at, ?),
                    execution_started_at_epoch_ms = COALESCE(execution_started_at_epoch_ms, ?),
                    last_progress_at = COALESCE(last_progress_at, ?),
                    last_progress_at_epoch_ms = COALESCE(last_progress_at_epoch_ms, ?),
                    updated_at = ?, updated_at_epoch_ms = ?,
                    summary = CASE WHEN ? = '' THEN summary ELSE ? END,
                    revision = revision + 1
                WHERE run_id = ?
                """,
                (
                    now, now, _epoch_ms(now), now, _epoch_ms(now),
                    now, _epoch_ms(now), now, _epoch_ms(now), summary,
                    policy.redact_text(summary)[:500], normalized_run,
                ),
            )
            _bump_revision(tx, now)
            row = tx.execute("SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)).fetchone()
        return _row(row) or {}

    def _append_progress_event(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        *,
        status: str,
        stage: str | None,
        percent: int | None,
        message: str | None,
        tool: str | None,
        payload: Any,
        created_at: str,
    ) -> dict[str, Any]:
        fingerprint = _progress_fingerprint(
            run_id, status, stage, percent, message, tool
        )
        duplicate = conn.execute(
            "SELECT event_id, sequence_no FROM security_scan_progress_events "
            "WHERE run_id = ? AND fingerprint = ?",
            (run_id, fingerprint),
        ).fetchone()
        if duplicate:
            return {
                "deduplicated": True,
                "event_id": int(duplicate["event_id"]),
                "sequence_no": int(duplicate["sequence_no"]),
            }
        sequence = int(
            conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence "
                "FROM security_scan_progress_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()["next_sequence"]
        )
        cursor = conn.execute(
            """
            INSERT INTO security_scan_progress_events(
                run_id, sequence_no, status, stage, percent, message, tool,
                created_at, created_at_epoch_ms, payload_json, fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, sequence, status, stage, percent, message, tool,
                created_at, _epoch_ms(created_at), _safe_json(payload), fingerprint,
            ),
        )
        return {
            "deduplicated": False,
            "event_id": int(cursor.lastrowid),
            "sequence_no": sequence,
        }

    def record_progress(
        self,
        run_id: str,
        *,
        status: str,
        stage: str | None = None,
        percent: int | None = None,
        message: str | None = None,
        tool: str | None = None,
        payload: Any = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        normalized_run = _normalize_run_id(run_id)
        normalized_status = _normalize_status(status)
        if percent is not None and not 0 <= int(percent) <= 100:
            raise InvalidSecurityStoreValue("Security progress percent must be 0..100")
        now = _parse_timestamp(created_at)
        clean_stage = policy.redact_text(str(stage or ""))[:160] or None
        clean_message = policy.redact_text(str(message or ""))[:500] or None
        clean_tool = policy.redact_text(str(tool or ""))[:80] or None
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT active_key, status FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            if str(current["status"]) in TERMINAL_STATUSES:
                row = tx.execute(
                    "SELECT * FROM security_scan_runs WHERE run_id = ?",
                    (normalized_run,),
                ).fetchone()
                return {
                    "deduplicated": True,
                    "ignored_terminal": True,
                    "run": _row(row) or {},
                }
            event = self._append_progress_event(
                tx, normalized_run, status=normalized_status, stage=clean_stage,
                percent=int(percent) if percent is not None else None,
                message=clean_message, tool=clean_tool, payload=payload, created_at=now,
            )
            if event["deduplicated"]:
                row = tx.execute(
                    "SELECT * FROM security_scan_runs WHERE run_id = ?",
                    (normalized_run,),
                ).fetchone()
                return {**event, "run": _row(row) or {}}
            active_key = current["active_key"] if normalized_status in ACTIVE_STATUSES else None
            tx.execute(
                """
                UPDATE security_scan_runs
                SET status = ?, active_key = ?, current_stage = ?, current_percent = ?,
                    current_message = ?, current_tool = ?, last_progress_at = ?,
                    last_progress_at_epoch_ms = ?, updated_at = ?, updated_at_epoch_ms = ?,
                    metadata_json = COALESCE(?, metadata_json), revision = revision + 1
                WHERE run_id = ?
                """,
                (
                    normalized_status, active_key, clean_stage,
                    int(percent) if percent is not None else None, clean_message, clean_tool,
                    now, _epoch_ms(now), now, _epoch_ms(now),
                    _safe_json(payload), normalized_run,
                ),
            )
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
        return {**event, "domain_revision": revision, "run": _row(row) or {}}

    def complete_run(
        self,
        run_id: str,
        *,
        status: str = "succeeded",
        summary: str = "",
        score: int | None = None,
        partial_results: bool = False,
        completed_at: str | None = None,
        findings: Sequence[Mapping[str, Any]] | None = None,
        evidence_refs: Sequence[Any] | None = None,
        tool_results: Mapping[str, Any] | None = None,
        counts: Mapping[str, int] | None = None,
        checks_reviewed: int = 0,
        items_to_review: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_status = _normalize_status(status)
        if normalized_status not in {"succeeded", "degraded", "cancelled"}:
            raise InvalidSecurityStoreValue("complete_run requires succeeded, degraded, or cancelled")
        return self._finish_run(
            run_id,
            status=normalized_status,
            summary=summary,
            score=score,
            partial_results=partial_results,
            completed_at=completed_at,
            findings=findings,
            evidence_refs=evidence_refs,
            tool_results=tool_results,
            counts=counts,
            checks_reviewed=checks_reviewed,
            items_to_review=items_to_review,
            metadata=metadata,
        )

    def fail_run(
        self,
        run_id: str,
        *,
        failure_code: str,
        failure_message: str,
        summary: str = "Security check needs review.",
        completed_at: str | None = None,
        partial_results: bool = False,
        evidence_refs: Sequence[Any] | None = None,
        tool_results: Mapping[str, Any] | None = None,
        findings: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._finish_run(
            run_id,
            status="failed",
            summary=policy.redact_text(summary)[:500] or "Security check needs review.",
            partial_results=partial_results,
            completed_at=completed_at,
            failure_code=policy.redact_text(failure_code)[:120],
            failure_message=policy.redact_text(failure_message)[:500],
            evidence_refs=evidence_refs,
            tool_results=tool_results,
            findings=findings,
            metadata=metadata,
        )

    def _finish_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: str,
        score: int | None = None,
        partial_results: bool = False,
        completed_at: str | None = None,
        findings: Sequence[Mapping[str, Any]] | None = None,
        evidence_refs: Sequence[Any] | None = None,
        tool_results: Mapping[str, Any] | None = None,
        counts: Mapping[str, int] | None = None,
        checks_reviewed: int = 0,
        items_to_review: int = 0,
        failure_code: str | None = None,
        failure_message: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_run = _normalize_run_id(run_id)
        now = _parse_timestamp(completed_at)
        safe_counts = {
            severity: max(0, int((counts or {}).get(severity, 0)))
            for severity in policy.SEVERITIES
        }
        if findings and not any(safe_counts.values()):
            for finding in findings:
                safe_counts[policy.normalize_severity(finding.get("severity"))] += 1
        terminal_material = policy.redact_value({
            "status": status, "summary": summary, "score": score,
            "partial_results": bool(partial_results), "counts": safe_counts,
            "checks_reviewed": checks_reviewed, "items_to_review": items_to_review,
            "failure_code": failure_code, "failure_message": failure_message,
            "findings": list(findings or [])[:500],
            "evidence_refs": list(evidence_refs or [])[:500],
            "tool_results": dict(tool_results or {}), "metadata": dict(metadata or {}),
        })
        terminal_fingerprint = hashlib.sha256(
            json.dumps(terminal_material, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with connection() as conn, begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
            if not current:
                raise SecurityStoreError("Security run not found")
            # A terminal write is authoritative, but its timestamp may come from
            # scanner/tool metadata or a compatibility projection. Never commit a
            # terminal row whose lifecycle clock moves backwards relative to the
            # already-committed run. Otherwise the monotonic in-memory projection
            # must correctly reject the terminal candidate and can remain stuck on
            # the prior running state.
            current_updated_at = _parse_timestamp(current["updated_at"])
            if _epoch_ms(now) < int(current["updated_at_epoch_ms"] or 0):
                now = current_updated_at

            current_metadata = _json_value(current["metadata_json"], {})
            if (
                str(current["status"]) in TERMINAL_STATUSES
                and current_metadata.get("terminal_fingerprint") == terminal_fingerprint
            ):
                revision_row = tx.execute(
                    "SELECT revision FROM domain_revisions WHERE domain = 'security'"
                ).fetchone()
                return {
                    "deduplicated": True,
                    "domain_revision": int(revision_row["revision"]) if revision_row else 0,
                    "run": _row(current) or {},
                }
            merged_metadata = {
                **(current_metadata if isinstance(current_metadata, dict) else {}),
                **policy.redact_value(dict(metadata or {})),
                "terminal_fingerprint": terminal_fingerprint,
            }
            terminal_percent = (
                100 if status in {"succeeded", "degraded", "cancelled"}
                else current["current_percent"]
            )
            terminal_stage = (
                "Safety check complete" if status in {"succeeded", "degraded", "cancelled"}
                else current["current_stage"] or "Safety check needs review"
            )
            tx.execute(
                """
                UPDATE security_scan_runs
                SET status = ?, active_key = NULL, summary = ?, score = ?, partial_results = ?,
                    completed_at = ?, completed_at_epoch_ms = ?, updated_at = ?, updated_at_epoch_ms = ?,
                    last_progress_at = ?, last_progress_at_epoch_ms = ?,
                    current_percent = ?, current_stage = ?, current_message = ?,
                    checks_reviewed = ?, items_to_review = ?, critical_count = ?, high_count = ?,
                    medium_count = ?, low_count = ?, info_count = ?, failure_code = ?,
                    failure_message = ?, evidence_saved = ?, metadata_json = ?, revision = revision + 1
                WHERE run_id = ?
                """,
                (
                    status, policy.redact_text(summary)[:500],
                    int(score) if score is not None else None, int(bool(partial_results)),
                    now, _epoch_ms(now), now, _epoch_ms(now), now, _epoch_ms(now),
                    terminal_percent, terminal_stage, policy.redact_text(summary)[:500],
                    max(0, int(checks_reviewed)),
                    max(0, int(items_to_review)), safe_counts["critical"], safe_counts["high"],
                    safe_counts["medium"], safe_counts["low"], safe_counts["info"],
                    failure_code, failure_message, int(bool(evidence_refs)),
                    _safe_json(merged_metadata), normalized_run,
                ),
            )
            self._replace_findings(tx, normalized_run, findings or [])
            self._replace_evidence_refs(tx, normalized_run, evidence_refs or [], created_at=now)
            self._replace_tool_runs(tx, normalized_run, tool_results or {})
            self._upsert_profile_snapshot(tx, normalized_run, updated_at=now)
            event = self._append_progress_event(
                tx, normalized_run, status=status, stage=terminal_stage,
                percent=terminal_percent, message=policy.redact_text(summary)[:500], tool=None,
                payload={"failure_code": failure_code} if failure_code else None, created_at=now,
            )
            revision = _bump_revision(tx, now)
            row = tx.execute(
                "SELECT * FROM security_scan_runs WHERE run_id = ?", (normalized_run,)
            ).fetchone()
        return {
            "deduplicated": False, "domain_revision": revision,
            "progress_event": event, "run": _row(row) or {},
        }

    def _replace_findings(self, conn: sqlite3.Connection, run_id: str, findings: Sequence[Mapping[str, Any]]) -> int:
        conn.execute("DELETE FROM security_scan_findings WHERE run_id = ?", (run_id,))
        count = 0
        seen: set[str] = set()
        for finding in list(findings)[:500]:
            clean = policy.redact_value(dict(finding))
            finding_key, fingerprint = _finding_key(clean)
            if finding_key in seen:
                continue
            seen.add(finding_key)
            severity = policy.normalize_severity(clean.get("severity"))
            title = policy.redact_text(str(clean.get("title") or clean.get("summary") or "Security finding"))[:240]
            conn.execute(
                """
                INSERT INTO security_scan_findings(
                    run_id, finding_key, fingerprint, source, severity, title, summary,
                    component, status, first_seen_at, last_seen_at, resolved_at,
                    remediation_json, technical_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    finding_key,
                    fingerprint,
                    policy.redact_text(str(clean.get("source") or "security"))[:80],
                    severity,
                    title,
                    policy.redact_text(str(clean.get("summary") or ""))[:500],
                    policy.redact_text(str(clean.get("component") or ""))[:160],
                    policy.redact_text(str(clean.get("status") or "present"))[:40],
                    _parse_timestamp(clean.get("first_seen_at")) if clean.get("first_seen_at") else None,
                    _parse_timestamp(clean.get("last_seen_at")) if clean.get("last_seen_at") else None,
                    _parse_timestamp(clean.get("resolved_at")) if clean.get("resolved_at") else None,
                    _safe_json(clean.get("remediation") or clean.get("recommendation")),
                    _safe_json({key: clean.get(key) for key in ("category", "file", "target", "redacted") if key in clean}),
                ),
            )
            count += 1
        return count

    def _replace_evidence_refs(
        self, conn: sqlite3.Connection, run_id: str, refs: Sequence[Any], *, created_at: str
    ) -> int:
        conn.execute("DELETE FROM security_scan_evidence_refs WHERE run_id = ?", (run_id,))
        count = 0
        seen: set[str] = set()
        for item in list(refs)[:500]:
            if isinstance(item, Mapping):
                relative = str(item.get("relative_path") or item.get("path") or item.get("evidence_ref") or "")
                kind = str(item.get("kind") or Path(relative).stem or "evidence")
                sha256 = str(item.get("sha256") or "") or None
                size_bytes = item.get("size_bytes")
                metadata = {key: value for key, value in item.items() if key not in {"relative_path", "path", "evidence_ref", "sha256", "size_bytes"}}
            else:
                relative = str(item or "")
                kind = Path(relative).stem or "evidence"
                sha256 = None
                size_bytes = None
                metadata = {}
            safe_relative = _safe_evidence_relative_path(run_id, relative)
            if not safe_relative or safe_relative in seen:
                continue
            seen.add(safe_relative)
            conn.execute(
                """
                INSERT INTO security_scan_evidence_refs(
                    run_id, kind, relative_path, sha256, size_bytes, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    policy.redact_text(kind)[:80],
                    safe_relative,
                    sha256[:64] if sha256 else None,
                    max(0, int(size_bytes)) if size_bytes is not None else None,
                    created_at,
                    _safe_json(metadata),
                ),
            )
            count += 1
        return count

    def _replace_tool_runs(self, conn: sqlite3.Connection, run_id: str, tool_results: Mapping[str, Any]) -> int:
        conn.execute("DELETE FROM security_scan_tool_runs WHERE run_id = ?", (run_id,))
        count = 0
        for tool_name, raw in list(tool_results.items())[:100]:
            payload = policy.redact_value(raw if isinstance(raw, Mapping) else {"status": str(raw)})
            conn.execute(
                """
                INSERT INTO security_scan_tool_runs(
                    run_id, tool_name, status, started_at, completed_at, duration_ms,
                    finding_count, timed_out, timeout_reason, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    policy.redact_text(str(tool_name))[:80],
                    policy.redact_text(str(payload.get("status") or "unknown"))[:40],
                    _parse_timestamp(payload.get("started_at")) if payload.get("started_at") else None,
                    _parse_timestamp(payload.get("completed_at")) if payload.get("completed_at") else None,
                    max(0, int(payload.get("duration_ms") or 0)) or None,
                    max(0, int(payload.get("finding_count") or 0)),
                    int(str(payload.get("status") or "").lower() == "timed_out" or bool(payload.get("timed_out"))),
                    policy.redact_text(str(payload.get("timeout_reason") or ""))[:240] or None,
                    _safe_json({key: value for key, value in payload.items() if key not in {"status", "started_at", "completed_at", "duration_ms", "finding_count", "timed_out", "timeout_reason"}}),
                ),
            )
            count += 1
        return count

    def _upsert_profile_snapshot(self, conn: sqlite3.Connection, run_id: str, *, updated_at: str) -> None:
        run = conn.execute("SELECT * FROM security_scan_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not run:
            return
        conn.execute(
            """
            INSERT INTO security_profile_snapshots(
                profile, app_id, latest_run_id, latest_status, latest_score,
                latest_summary, latest_completed_at, latest_evidence_at, updated_at, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(profile, app_id) DO UPDATE SET
                latest_run_id = excluded.latest_run_id,
                latest_status = excluded.latest_status,
                latest_score = excluded.latest_score,
                latest_summary = excluded.latest_summary,
                latest_completed_at = excluded.latest_completed_at,
                latest_evidence_at = excluded.latest_evidence_at,
                updated_at = excluded.updated_at,
                revision = security_profile_snapshots.revision + 1
            """,
            (
                run["profile"],
                run["app_id"],
                run_id,
                run["status"],
                run["score"],
                run["summary"],
                run["completed_at"],
                run["completed_at"] if run["evidence_saved"] else None,
                updated_at,
            ),
        )

    def get_domain_revision(self) -> dict[str, Any]:
        with read_connection() as conn:
            row = conn.execute(
                "SELECT revision, updated_at FROM domain_revisions WHERE domain = 'security'"
            ).fetchone()
        return {
            "revision": int(row["revision"]) if row else 0,
            "updated_at": row["updated_at"] if row else None,
        }

    def get_progress(self, run_id: str | None = None) -> dict[str, Any] | None:
        """Read Progress through the bounded dedicated reader contract."""
        with SecurityProgressReader() as reader:
            return reader.read(run_id).progress

    def get_progress_event(self, event_id: int) -> dict[str, Any] | None:
        numeric = int(event_id)
        if numeric <= 0:
            return None
        with read_connection() as conn:
            row = conn.execute(
                _PROGRESS_EVENT_SELECT + " WHERE pe.event_id = ? LIMIT 1",
                (numeric,),
            ).fetchone()
        return _progress_event_payload(row)

    def get_latest_progress_event(
        self, run_id: str | None = None
    ) -> dict[str, Any] | None:
        clause = ""
        parameters: tuple[Any, ...] = ()
        if run_id:
            clause = " WHERE pe.run_id = ?"
            parameters = (_normalize_run_id(run_id),)
        with read_connection() as conn:
            row = conn.execute(
                _PROGRESS_EVENT_SELECT + clause + " ORDER BY pe.event_id DESC LIMIT 1",
                parameters,
            ).fetchone()
        return _progress_event_payload(row)

    def get_oldest_progress_event_id(self) -> int | None:
        with read_connection() as conn:
            row = conn.execute(
                "SELECT MIN(event_id) AS event_id FROM security_scan_progress_events"
            ).fetchone()
        value = row["event_id"] if row else None
        return int(value) if value is not None else None

    def get_latest_progress_event_id(self) -> int | None:
        with read_connection() as conn:
            row = conn.execute(
                "SELECT MAX(event_id) AS event_id FROM security_scan_progress_events"
            ).fetchone()
        value = row["event_id"] if row else None
        return int(value) if value is not None else None

    def list_progress_events_after(
        self, event_id: int, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        numeric = max(0, int(event_id))
        with read_connection() as conn:
            rows = conn.execute(
                _PROGRESS_EVENT_SELECT
                + " WHERE pe.event_id > ? ORDER BY pe.event_id ASC LIMIT ?",
                (numeric, bounded),
            ).fetchall()
        return [payload for row in rows if (payload := _progress_event_payload(row))]

    def list_progress_events(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        with read_connection() as conn:
            rows = conn.execute(
                _PROGRESS_EVENT_SELECT
                + " WHERE pe.run_id = ? ORDER BY pe.event_id DESC LIMIT ?",
                (_normalize_run_id(run_id), bounded),
            ).fetchall()
        return [payload for row in rows if (payload := _progress_event_payload(row))]

    def prune_progress_events(
        self,
        *,
        retention_days: int = 30,
        max_rows: int = 20_000,
        min_per_active_run: int = 100,
        batch_size: int = 500,
        now_epoch_ms: int | None = None,
    ) -> dict[str, Any]:
        """Prune one bounded batch while preserving active and terminal truth."""
        days = max(1, min(int(retention_days), 3650))
        row_cap = max(100, min(int(max_rows), 2_000_000))
        minimum = max(1, min(int(min_per_active_run), 1000))
        bounded_batch = max(1, min(int(batch_size), 2000))
        current_epoch_ms = int(now_epoch_ms or time.time() * 1000)
        cutoff_epoch_ms = current_epoch_ms - (days * 24 * 60 * 60 * 1000)
        recorded_at = datetime.fromtimestamp(
            current_epoch_ms / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")

        with connection() as conn, begin_immediate(conn) as tx:
            total_before = int(
                tx.execute(
                    "SELECT COUNT(*) AS count FROM security_scan_progress_events"
                ).fetchone()["count"]
            )
            active_ids = {
                int(row["event_id"])
                for row in tx.execute(
                    """
                    SELECT pe.event_id
                    FROM security_scan_progress_events AS pe
                    JOIN security_scan_runs AS r ON r.run_id = pe.run_id
                    WHERE r.status IN ('queued','accepted','running','working','in_progress')
                    """
                ).fetchall()
            }
            terminal_ids = {
                int(row["event_id"])
                for row in tx.execute(
                    """
                    SELECT MAX(pe.event_id) AS event_id
                    FROM security_scan_progress_events AS pe
                    JOIN security_scan_runs AS r ON r.run_id = pe.run_id
                    WHERE r.status IN ('succeeded','degraded','failed','cancelled')
                    GROUP BY pe.run_id
                    """
                ).fetchall()
                if row["event_id"] is not None
            }
            recent_completed_ids = {
                int(row["event_id"])
                for row in tx.execute(
                    """
                    SELECT event_id FROM (
                        SELECT pe.event_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY pe.run_id ORDER BY pe.event_id DESC
                               ) AS retained_rank
                        FROM security_scan_progress_events AS pe
                        JOIN security_scan_runs AS r ON r.run_id = pe.run_id
                        WHERE r.status NOT IN ('queued','accepted','running','working','in_progress')
                    )
                    WHERE retained_rank <= ?
                    """,
                    (minimum,),
                ).fetchall()
            }
            protected_ids = active_ids | terminal_ids | recent_completed_ids
            scan_limit = min(
                50_000,
                max(bounded_batch * 10, bounded_batch + len(protected_ids)),
            )
            oldest_rows = tx.execute(
                """
                SELECT event_id, created_at_epoch_ms
                FROM security_scan_progress_events
                ORDER BY event_id ASC
                LIMIT ?
                """,
                (scan_limit,),
            ).fetchall()
            age_candidates = [
                int(row["event_id"])
                for row in oldest_rows
                if int(row["event_id"]) not in protected_ids
                and int(row["created_at_epoch_ms"] or 0) < cutoff_epoch_ms
            ]
            excess = max(0, total_before - row_cap)
            cap_candidates = [
                int(row["event_id"])
                for row in oldest_rows
                if int(row["event_id"]) not in protected_ids
            ][:excess]
            delete_ids = list(dict.fromkeys(age_candidates + cap_candidates))[:bounded_batch]
            if delete_ids:
                placeholders = ",".join("?" for _ in delete_ids)
                tx.execute(
                    f"DELETE FROM security_scan_progress_events WHERE event_id IN ({placeholders})",
                    tuple(delete_ids),
                )
            total_after = total_before - len(delete_ids)
            oldest_row = tx.execute(
                "SELECT MIN(event_id) AS event_id FROM security_scan_progress_events"
            ).fetchone()
            latest_row = tx.execute(
                "SELECT MAX(event_id) AS event_id FROM security_scan_progress_events"
            ).fetchone()
            result = {
                "status": "completed",
                "retention_days": days,
                "max_rows": row_cap,
                "min_per_active_run": minimum,
                "batch_size": bounded_batch,
                "rows_before": total_before,
                "rows_deleted": len(delete_ids),
                "rows_after": total_after,
                "active_event_rows_preserved": len(active_ids),
                "terminal_event_rows_preserved": len(terminal_ids),
                "oldest_retained_event_id": (
                    int(oldest_row["event_id"])
                    if oldest_row and oldest_row["event_id"] is not None
                    else None
                ),
                "latest_retained_event_id": (
                    int(latest_row["event_id"])
                    if latest_row and latest_row["event_id"] is not None
                    else None
                ),
                "row_cap_satisfied": total_after <= row_cap,
                "recorded_at": recorded_at,
                "sanitized": True,
            }
            _set_metadata(tx, "progress_retention:last", result, at=recorded_at)
        return policy.redact_value(result)

    def list_tool_runs(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 100))
        with read_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM security_scan_tool_runs WHERE run_id = ? "
                "ORDER BY tool_run_id LIMIT ?",
                (_normalize_run_id(run_id), bounded),
            ).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = _json_value(item.pop("metadata_json", None), {})
            payloads.append(policy.redact_value(item))
        return payloads


    def get_summary(self) -> dict[str, Any]:
        with read_connection() as conn:
            latest = conn.execute(
                "SELECT * FROM security_scan_runs ORDER BY updated_at_epoch_ms DESC LIMIT 1"
            ).fetchone()
            revision = conn.execute(
                "SELECT revision, updated_at FROM domain_revisions WHERE domain = ?", ("security",)
            ).fetchone()
            history_count = int(conn.execute("SELECT COUNT(*) AS count FROM security_scan_runs").fetchone()["count"])
            finding_count = 0
            if latest:
                finding_count = int(conn.execute(
                    "SELECT COUNT(*) AS count FROM security_scan_findings WHERE run_id = ?", (latest["run_id"],)
                ).fetchone()["count"])
        run = _row(latest)
        return policy.redact_value({
            "latest_run": run,
            "history_count": history_count,
            "finding_count": finding_count,
            "revision": int(revision["revision"]) if revision else 0,
            "updated_at": revision["updated_at"] if revision else None,
            "storage_backend": "sqlite",
        })

    def get_profile_snapshot(self, profile: str, app_id: str | None = None) -> dict[str, Any] | None:
        normalized_profile = _normalize_profile(profile)
        normalized_app = _normalize_app(normalized_profile, app_id)
        with read_connection() as conn:
            row = conn.execute(
                "SELECT * FROM security_profile_snapshots WHERE profile = ? AND app_id = ?",
                (normalized_profile, normalized_app),
            ).fetchone()
        return policy.redact_value(dict(row)) if row else None

    def get_previous_comparable_run(
        self,
        current_run_id: str,
        *,
        profile: str,
        app_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the previous complete run for the exact profile/app scope."""
        normalized_run = _normalize_run_id(current_run_id)
        normalized_profile = _normalize_profile(profile)
        normalized_app = _normalize_app(normalized_profile, app_id)
        with read_connection() as conn:
            current = conn.execute(
                "SELECT completed_at_epoch_ms, run_id FROM security_scan_runs WHERE run_id = ?",
                (normalized_run,),
            ).fetchone()
            if not current or current["completed_at_epoch_ms"] is None:
                return None
            row = conn.execute(
                """
                SELECT * FROM security_scan_runs
                WHERE profile = ? AND app_id = ? AND run_id != ?
                  AND status IN ('succeeded', 'degraded')
                  AND partial_results = 0
                  AND completed_at_epoch_ms IS NOT NULL
                  AND (completed_at_epoch_ms < ?
                       OR (completed_at_epoch_ms = ? AND run_id < ?))
                ORDER BY completed_at_epoch_ms DESC, run_id DESC
                LIMIT 1
                """,
                (
                    normalized_profile, normalized_app, normalized_run,
                    int(current["completed_at_epoch_ms"]),
                    int(current["completed_at_epoch_ms"]),
                    normalized_run,
                ),
            ).fetchone()
        return _row(row)

    def list_tool_runs_for_runs(
        self, run_ids: Sequence[str], *, per_run_limit: int = 12
    ) -> dict[str, list[dict[str, Any]]]:
        """Read bounded tool summaries for a page of history in one query."""
        normalized = [_normalize_run_id(value) for value in list(run_ids)[:MAX_HISTORY_LIMIT] if value]
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        bounded = max(1, min(int(per_run_limit), 20))
        with read_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM security_scan_tool_runs WHERE run_id IN ({placeholders}) "
                "ORDER BY run_id, tool_run_id",
                tuple(normalized),
            ).fetchall()
        result: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            run_id = str(row["run_id"])
            if len(result.get(run_id, [])) >= bounded:
                continue
            item = dict(row)
            item["metadata"] = _json_value(item.pop("metadata_json", None), {})
            result.setdefault(run_id, []).append(policy.redact_value(item))
        return result

    def list_runs(self, *, limit: int = DEFAULT_HISTORY_LIMIT, profile: str | None = None, app_id: str | None = None) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), MAX_HISTORY_LIMIT))
        with read_connection() as conn:
            if profile is None:
                rows = conn.execute(
                    "SELECT * FROM security_scan_runs ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC, run_id DESC LIMIT ?",
                    (bounded,),
                ).fetchall()
            else:
                normalized_profile = _normalize_profile(profile)
                normalized_app = _normalize_app(normalized_profile, app_id)
                rows = conn.execute(
                    "SELECT * FROM security_scan_runs WHERE profile = ? AND app_id = ? ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC, run_id DESC LIMIT ?",
                    (normalized_profile, normalized_app, bounded),
                ).fetchall()
        return [_row(item) or {} for item in rows]

    def list_runs_page(
        self,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        cursor_epoch_ms: int | None = None,
        cursor_run_id: str | None = None,
        profile: str | None = None,
        app_id: str | None = None,
    ) -> dict[str, Any]:
        bounded = max(1, min(int(limit), MAX_HISTORY_LIMIT))
        clauses: list[str] = []
        parameters: list[Any] = []
        if profile is not None:
            normalized_profile = _normalize_profile(profile)
            normalized_app = _normalize_app(normalized_profile, app_id)
            clauses.extend(["profile = ?", "app_id = ?"])
            parameters.extend([normalized_profile, normalized_app])
        if cursor_epoch_ms is not None and cursor_run_id:
            clauses.append(
                "(COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) < ? "
                "OR (COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) = ? AND run_id < ?))"
            )
            parameters.extend([int(cursor_epoch_ms), int(cursor_epoch_ms), _normalize_run_id(cursor_run_id)])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with read_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM security_scan_runs" + where +
                " ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC, run_id DESC LIMIT ?",
                (*parameters, bounded + 1),
            ).fetchall()
        has_more = len(rows) > bounded
        selected = rows[:bounded]
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = {
                "epoch_ms": int(last["completed_at_epoch_ms"] or last["updated_at_epoch_ms"] or last["requested_at_epoch_ms"]),
                "run_id": str(last["run_id"]),
            }
        return {
            "runs": [_row(row) or {} for row in selected],
            "has_more": has_more,
            "next_cursor": next_cursor,
            "limit": bounded,
        }

    def get_latest_run(
        self, profile: str | None = None, app_id: str | None = None
    ) -> dict[str, Any] | None:
        with read_connection() as conn:
            if profile is None:
                row = conn.execute(
                    "SELECT * FROM security_scan_runs ORDER BY updated_at_epoch_ms DESC LIMIT 1"
                ).fetchone()
            else:
                normalized_profile = _normalize_profile(profile)
                if normalized_profile == policy.SCAN_PROFILE_APP and not str(app_id or "").strip():
                    row = conn.execute(
                        "SELECT * FROM security_scan_runs WHERE profile = 'app' "
                        "ORDER BY updated_at_epoch_ms DESC LIMIT 1"
                    ).fetchone()
                else:
                    normalized_app = _normalize_app(normalized_profile, app_id)
                    row = conn.execute(
                        "SELECT * FROM security_scan_runs WHERE profile = ? AND app_id = ? "
                        "ORDER BY updated_at_epoch_ms DESC LIMIT 1",
                        (normalized_profile, normalized_app),
                    ).fetchone()
        return _row(row)

    def record_projection_status(
        self,
        run_id: str,
        *,
        component: str,
        degraded: bool,
        reason: str = "",
    ) -> None:
        normalized_run = _normalize_run_id(run_id)
        normalized_component = (
            "run" if str(component).strip().lower() == "run" else "state"
        )
        updated_at = utc_now()
        with connection() as conn, begin_immediate(conn) as tx:
            component_key = (
                f"json_projection:{normalized_run}:{normalized_component}"
            )
            _set_metadata(
                tx,
                component_key,
                {
                    "degraded": bool(degraded),
                    "reason": policy.redact_text(reason)[:160],
                    "updated_at": updated_at,
                },
                at=updated_at,
            )
            state_status = _get_metadata(
                tx, f"json_projection:{normalized_run}:state"
            )
            run_status = _get_metadata(
                tx, f"json_projection:{normalized_run}:run"
            )
            degraded_components = [
                name
                for name, status in (("state", state_status), ("run", run_status))
                if bool(status.get("degraded"))
            ]
            _set_metadata(
                tx,
                f"json_projection:{normalized_run}",
                {
                    "degraded": bool(degraded_components),
                    "components": degraded_components,
                    "updated_at": updated_at,
                },
                at=updated_at,
            )

    def reconcile_stale_runs(
        self, *, now: str | None = None, stale_seconds: int | None = None
    ) -> list[dict[str, Any]]:
        current_time = _parse_timestamp(now)
        current_epoch = _epoch_ms(current_time)
        quick_stale = stale_seconds if stale_seconds is not None else _bounded_environment_int(
            "POCKETLAB_LITE_SECURITY_STALE_ACTIVE_SECONDS", 7200, minimum=900, maximum=172800
        )
        full_stale = max(
            int(quick_stale),
            _bounded_environment_int(
                "POCKETLAB_LITE_SECURITY_FULL_STALE_ACTIVE_SECONDS",
                28800, minimum=3600, maximum=345600,
            ),
        )
        reconciled: list[dict[str, Any]] = []
        with connection() as conn, begin_immediate(conn) as tx:
            rows = tx.execute(
                "SELECT * FROM security_scan_runs WHERE active_key IS NOT NULL "
                "ORDER BY updated_at_epoch_ms"
            ).fetchall()
            for row in rows:
                threshold = full_stale if row["profile"] == policy.SCAN_PROFILE_FULL else int(quick_stale)
                if current_epoch - int(row["updated_at_epoch_ms"]) < threshold * 1000:
                    continue
                summary = "The previous safety check was interrupted and can be started again."
                tx.execute(
                    """
                    UPDATE security_scan_runs
                    SET status = 'failed', active_key = NULL, completed_at = ?,
                        completed_at_epoch_ms = ?, updated_at = ?, updated_at_epoch_ms = ?,
                        failure_code = 'interrupted', failure_message = ?,
                        current_message = ?, revision = revision + 1
                    WHERE run_id = ?
                    """,
                    (current_time, current_epoch, current_time, current_epoch, summary, summary, row["run_id"]),
                )
                self._append_progress_event(
                    tx, str(row["run_id"]), status="failed",
                    stage=str(row["current_stage"] or "interrupted"),
                    percent=row["current_percent"], message=summary, tool=row["current_tool"],
                    payload={"failure_code": "interrupted"}, created_at=current_time,
                )
                self._upsert_profile_snapshot(
                    tx, str(row["run_id"]), updated_at=current_time
                )
                reconciled.append({"run_id": str(row["run_id"]), "profile": str(row["profile"])})
            if reconciled:
                _bump_revision(tx, current_time)
        return policy.redact_value(reconciled)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with read_connection() as conn:
            row = conn.execute("SELECT * FROM security_scan_runs WHERE run_id = ?", (_normalize_run_id(run_id),)).fetchone()
        return _row(row)

    def list_findings(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        with read_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM security_scan_findings WHERE run_id = ? ORDER BY finding_row_id LIMIT ?",
                (_normalize_run_id(run_id), bounded),
            ).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["remediation"] = _json_value(item.pop("remediation_json", None), None)
            item["technical"] = _json_value(item.pop("technical_json", None), None)
            payloads.append(policy.redact_value(item))
        return payloads

    def list_evidence_refs(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        with read_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM security_scan_evidence_refs WHERE run_id = ? ORDER BY evidence_ref_id LIMIT ?",
                (_normalize_run_id(run_id), bounded),
            ).fetchall()
        return [policy.redact_value({**dict(row), "metadata": _json_value(row["metadata_json"], {})}) for row in rows]

    def import_legacy_state(
        self,
        *,
        source_root: Path | None = None,
        preview: bool = False,
        hash_evidence: bool = False,
        force: bool = False,
        reconcile: bool = False,
    ) -> dict[str, Any]:
        root = (source_root or evidence.security_root()).resolve()
        state_path = root / "security_state.json"
        state = _load_core_json(state_path)
        source_checksum = _source_checksum(root)
        report = ImportReport(
            preview=preview,
            source_root=root.name or "security",
            source_checksum=source_checksum,
        )
        normalized = _normalized_legacy_runs(root, state, report)
        selected_active = None
        active_candidates = [item for item in normalized if item["status"] in ACTIVE_STATUSES]
        if active_candidates:
            selected_active = max(active_candidates, key=lambda item: item["updated_at_epoch_ms"])["run_id"]
        canonical_run_ids = {str(item["run_id"]) for item in normalized}
        report.reconciled = bool(reconcile)
        if preview:
            report.runs_imported = len(normalized)
            for item in normalized:
                report.findings_imported += len(item["findings"])
                report.tools_imported += len(item["tool_results"])
                report.evidence_refs_imported += len(_legacy_evidence_refs(root, item, hash_evidence=False))
            return report.to_dict()
        with connection() as conn, begin_immediate(conn) as tx:
            previous = _get_metadata(tx, "legacy_import:last")
            if (
                not force
                and not reconcile
                and previous.get("source_checksum") == source_checksum
                and int(previous.get("import_version") or 0) == IMPORT_VERSION
            ):
                report.runs_skipped = len(normalized)
                report.warnings.append(
                    "Legacy Security source is unchanged; import skipped."
                )
                return report.to_dict()
            for item in normalized:
                if item["status"] in ACTIVE_STATUSES and item["run_id"] != selected_active:
                    item = {**item, "status": "failed", "active_key": None, "failure_code": "legacy_multiple_active_runs", "failure_message": "Older active legacy run retained as failed in the SQLite shadow index."}
                else:
                    item["active_key"] = _active_key(item["profile"], item["app_id"]) if item["status"] in ACTIVE_STATUSES else None
                refs = _legacy_evidence_refs(root, item, hash_evidence=hash_evidence)
                item = {**item, "evidence_saved": bool(refs)}
                self._upsert_legacy_run(tx, item)
                report.findings_imported += self._replace_findings(tx, item["run_id"], item["findings"])
                report.tools_imported += self._replace_tool_runs(tx, item["run_id"], item["tool_results"])
                report.evidence_refs_imported += self._replace_evidence_refs(tx, item["run_id"], refs, created_at=item["updated_at"])
                if item.get("progress"):
                    self._upsert_imported_progress(tx, item)
                report.runs_imported += 1
            if reconcile:
                existing_run_ids = {
                    str(row[0])
                    for row in tx.execute("SELECT run_id FROM security_scan_runs")
                }
                stale_run_ids = sorted(existing_run_ids - canonical_run_ids)
                if stale_run_ids:
                    placeholders = ",".join("?" for _ in stale_run_ids)
                    deleted = tx.execute(
                        f"DELETE FROM security_scan_runs WHERE run_id IN ({placeholders})",
                        stale_run_ids,
                    )
                    report.runs_deleted = max(0, int(deleted.rowcount))
                tx.execute("DELETE FROM security_profile_snapshots")
                latest_rows = tx.execute(
                    """
                    SELECT run_id
                    FROM security_scan_runs
                    ORDER BY
                        profile, app_id,
                        COALESCE(
                            completed_at_epoch_ms,
                            updated_at_epoch_ms,
                            requested_at_epoch_ms
                        ) DESC,
                        run_id DESC
                    """
                ).fetchall()
                seen_profiles: set[tuple[str, str]] = set()
                for row in latest_rows:
                    run = tx.execute(
                        "SELECT profile, app_id, updated_at FROM security_scan_runs WHERE run_id = ?",
                        (row["run_id"],),
                    ).fetchone()
                    key = (str(run["profile"]), str(run["app_id"]))
                    if key in seen_profiles:
                        continue
                    seen_profiles.add(key)
                    self._upsert_profile_snapshot(
                        tx, str(row["run_id"]), updated_at=str(run["updated_at"])
                    )
                canonical_projection = _normalized_runs_shadow_projection(normalized)
                parity = self._compare_projection_with_connection(
                    canonical_projection, tx
                )
                report.parity_matched = bool(parity["matched"])
                if not report.parity_matched:
                    raise SecurityReconciliationError(
                        "Legacy Security reconciliation did not converge",
                        mismatch_fields=parity["mismatch_fields"],
                    )
            else:
                for item in normalized:
                    self._upsert_profile_snapshot(
                        tx, item["run_id"], updated_at=item["updated_at"]
                    )
            revision = _bump_revision(tx)
            metadata = {
                **report.to_dict(),
                "import_version": IMPORT_VERSION,
                "domain_revision": revision,
                "database_path_name": database_path().name,
            }
            _set_metadata(tx, "legacy_import:last", metadata)
        return report.to_dict()

    def _upsert_legacy_run(self, conn: sqlite3.Connection, item: Mapping[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO security_scan_runs(
                run_id, profile, app_id, app_label, status, active_key, summary, score,
                partial_results, requested_at, accepted_at, started_at, completed_at, updated_at,
                requested_at_epoch_ms, started_at_epoch_ms, completed_at_epoch_ms, updated_at_epoch_ms,
                current_stage, current_percent, current_message, current_tool, checks_reviewed,
                items_to_review, critical_count, high_count, medium_count, low_count, info_count,
                failure_code, failure_message, command_id, correlation_id, source, revision,
                evidence_saved, metadata_json
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, 'legacy-json-import', 1, ?, ?
            )
            ON CONFLICT(run_id) DO UPDATE SET
                profile = excluded.profile, app_id = excluded.app_id, app_label = excluded.app_label,
                status = excluded.status, active_key = excluded.active_key, summary = excluded.summary,
                score = excluded.score, partial_results = excluded.partial_results,
                requested_at = excluded.requested_at, accepted_at = excluded.accepted_at,
                started_at = excluded.started_at, completed_at = excluded.completed_at,
                updated_at = excluded.updated_at, requested_at_epoch_ms = excluded.requested_at_epoch_ms,
                started_at_epoch_ms = excluded.started_at_epoch_ms,
                completed_at_epoch_ms = excluded.completed_at_epoch_ms,
                updated_at_epoch_ms = excluded.updated_at_epoch_ms,
                current_stage = excluded.current_stage, current_percent = excluded.current_percent,
                current_message = excluded.current_message, current_tool = excluded.current_tool,
                checks_reviewed = excluded.checks_reviewed, items_to_review = excluded.items_to_review,
                critical_count = excluded.critical_count, high_count = excluded.high_count,
                medium_count = excluded.medium_count, low_count = excluded.low_count,
                info_count = excluded.info_count, failure_code = excluded.failure_code,
                failure_message = excluded.failure_message, command_id = excluded.command_id,
                correlation_id = excluded.correlation_id, source = excluded.source,
                revision = security_scan_runs.revision + 1,
                evidence_saved = excluded.evidence_saved, metadata_json = excluded.metadata_json
            """,
            (
                item["run_id"], item["profile"], item["app_id"], item["app_label"], item["status"], item.get("active_key"),
                item["summary"], item.get("score"), int(item["partial_results"]), item["requested_at"], item.get("accepted_at"),
                item.get("started_at"), item.get("completed_at"), item["updated_at"], item["requested_at_epoch_ms"],
                item.get("started_at_epoch_ms"), item.get("completed_at_epoch_ms"), item["updated_at_epoch_ms"],
                item.get("current_stage"), item.get("current_percent"), item.get("current_message"), item.get("current_tool"),
                item["checks_reviewed"], item["items_to_review"], item["critical_count"], item["high_count"],
                item["medium_count"], item["low_count"], item["info_count"], item.get("failure_code"), item.get("failure_message"),
                item.get("command_id"), item.get("correlation_id"), int(item["evidence_saved"]), _safe_json(item.get("metadata")),
            ),
        )

    def _upsert_imported_progress(self, conn: sqlite3.Connection, item: Mapping[str, Any]) -> None:
        progress = item["progress"]
        fingerprint = _progress_fingerprint(item["run_id"], item["status"], progress.get("stage"), progress.get("percent"), progress.get("message"), progress.get("tool"))
        conn.execute(
            """
            INSERT INTO security_scan_progress_events(
                run_id, sequence_no, status, stage, percent, message, tool,
                created_at, created_at_epoch_ms, payload_json, fingerprint
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, fingerprint) DO NOTHING
            """,
            (
                item["run_id"], item["status"], progress.get("stage"), progress.get("percent"),
                progress.get("message"), progress.get("tool"), item["updated_at"], item["updated_at_epoch_ms"],
                _safe_json(progress), fingerprint,
            ),
        )

    def compare_json_state(
        self, state: Mapping[str, Any], *, record: bool = True
    ) -> dict[str, Any]:
        """Compare the bounded raw compatibility-state projection."""
        result = _compare_projections(
            _json_shadow_projection(state),
            self._sqlite_shadow_projection(),
        )
        if record:
            with connection() as conn, begin_immediate(conn) as tx:
                _set_metadata(tx, "shadow_compare:last", result)
        return result

    def compare_legacy_source(
        self,
        *,
        source_root: Path | None = None,
        record: bool = True,
    ) -> dict[str, Any]:
        """Compare SQLite with the complete normalized canonical JSON source."""
        root = (source_root or evidence.security_root()).resolve()
        state = _load_core_json(root / "security_state.json")
        report = ImportReport(
            preview=True,
            source_root=root.name or "security",
            source_checksum=_source_checksum(root),
        )
        normalized = _normalized_legacy_runs(root, state, report)
        result = _compare_projections(
            _normalized_runs_shadow_projection(normalized),
            self._sqlite_shadow_projection(),
        )
        result.update(
            {
                "source_root": report.source_root,
                "runs_seen": report.runs_seen,
                "runs_normalized": len(normalized),
                "runs_skipped": report.runs_skipped,
                "malformed_optional_files": report.malformed_optional_files,
                "warnings": report.warnings,
            }
        )
        if record:
            with connection() as conn, begin_immediate(conn) as tx:
                _set_metadata(tx, "shadow_compare:last", result)
        return policy.redact_value(result)

    def _compare_projection_with_connection(
        self,
        canonical_projection: Mapping[str, Any],
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        return _compare_projections(
            canonical_projection,
            self._sqlite_shadow_projection(conn=conn),
        )

    def _sqlite_shadow_projection(
        self, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any]:
        if conn is None:
            runs = self.list_runs(limit=DEFAULT_HISTORY_LIMIT)
        else:
            rows = conn.execute(
                """
                SELECT * FROM security_scan_runs
                ORDER BY COALESCE(
                    completed_at_epoch_ms,
                    updated_at_epoch_ms,
                    requested_at_epoch_ms
                ) DESC, run_id DESC
                LIMIT ?
                """,
                (DEFAULT_HISTORY_LIMIT,),
            ).fetchall()
            runs = [_row(row) or {} for row in rows]
        runs = list(_canonical_history(runs, limit=DEFAULT_HISTORY_LIMIT))
        latest = runs[0] if runs else {}
        if latest.get("run_id") and conn is None:
            findings = self.list_findings(str(latest.get("run_id")))
            refs = self.list_evidence_refs(str(latest.get("run_id")))
        elif latest.get("run_id"):
            findings = [
                dict(row)
                for row in conn.execute(
                    "SELECT severity FROM security_scan_findings WHERE run_id = ?",
                    (str(latest.get("run_id")),),
                ).fetchall()
            ]
            refs = conn.execute(
                "SELECT 1 FROM security_scan_evidence_refs WHERE run_id = ? LIMIT 1",
                (str(latest.get("run_id")),),
            ).fetchall()
        else:
            findings = []
            refs = []
        counts = {severity: int(latest.get(f"{severity}_count") or 0) for severity in policy.SEVERITIES}
        if findings and not any(counts.values()):
            for finding in findings:
                counts[policy.normalize_severity(finding.get("severity"))] += 1
        return {
            "latest_run_id": latest.get("run_id") or "",
            "profile": latest.get("profile") or "",
            "app_id": latest.get("app_id") or "",
            "status": latest.get("status") or "",
            "score": latest.get("score"),
            "current_percent": latest.get("current_percent"),
            "current_stage": latest.get("current_stage") or "",
            "finding_counts": counts,
            "evidence_saved": bool(latest.get("evidence_saved") or refs),
            "latest_completed_at": latest.get("completed_at") or "",
            "history_count": len(runs),
            "latest_run_ids": [item.get("run_id") for item in runs],
        }


def _safe_evidence_relative_path(run_id: str, value: Any) -> str | None:
    text = str(value or "").replace("\\", "/").strip()
    if not text:
        return None
    marker = "security/evidence/"
    if marker in text:
        text = text[text.index(marker):]
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        return None
    expected_prefix = f"security/evidence/{evidence.safe_run_id(run_id)}/"
    if not text.startswith(expected_prefix):
        text = expected_prefix + Path(text).name
    return policy.redact_text(text)[:500]


def _load_core_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecurityStoreError("Malformed core Security state JSON") from exc
    if not isinstance(payload, dict):
        raise SecurityStoreError("Core Security state must be a JSON object")
    return policy.redact_value(payload)


def _source_checksum(root: Path) -> str:
    digest = hashlib.sha256()
    maximum_runs = max(
        1,
        min(
            int(os.environ.get("POCKETLAB_LITE_SECURITY_IMPORT_MAX_RUNS", "5000")),
            20_000,
        ),
    )
    paths = [
        root / "security_state.json",
        *sorted((root / "runs").glob("*.json"))[:maximum_runs],
    ]
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    evidence_files = sorted((root / "evidence").glob("*/*.json"))[:20_000]
    for path in evidence_files:
        try:
            stat_result = path.stat()
        except OSError:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(str(stat_result.st_size).encode("ascii"))
        digest.update(str(stat_result.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def _legacy_run_candidates(root: Path, state: Mapping[str, Any], report: ImportReport) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    runs_root = root / "runs"
    maximum = max(1, min(int(os.environ.get("POCKETLAB_LITE_SECURITY_IMPORT_MAX_RUNS", "5000")), 20_000))
    for path in sorted(runs_root.glob("*.json"))[:maximum]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report.malformed_optional_files.append(path.name)
            continue
        if not isinstance(payload, dict):
            report.malformed_optional_files.append(path.name)
            continue
        run_id = evidence.safe_run_id(str(payload.get("run_id") or path.stem))
        candidates[run_id] = policy.redact_value(payload)
    history = state.get("history") if isinstance(state.get("history"), list) else []
    for payload in [*history, state.get("last_run")]:
        if not isinstance(payload, dict):
            continue
        run_id = evidence.safe_run_id(str(payload.get("run_id") or ""))
        if run_id != "unknown":
            candidates.setdefault(run_id, policy.redact_value(payload))
    return list(candidates.values())


def _normalized_legacy_runs(
    root: Path,
    state: Mapping[str, Any],
    report: ImportReport,
) -> list[dict[str, Any]]:
    candidates = _legacy_run_candidates(root, state, report)
    report.runs_seen = len(candidates)
    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            normalized.append(_normalize_legacy_run(candidate, state))
        except (InvalidSecurityStoreValue, TypeError, ValueError) as exc:
            report.runs_skipped += 1
            report.warnings.append(policy.redact_text(str(exc))[:240])
    return normalized


def _normalize_legacy_run(payload: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    run_id = _normalize_run_id(payload.get("run_id"))
    profile = _normalize_profile(payload.get("scan_profile") or payload.get("profile") or ("app" if payload.get("app_id") else "quick"))
    app_id = _normalize_app(profile, payload.get("app_id"))
    status = _normalize_status(payload.get("status") or "succeeded")
    requested_at = _parse_timestamp(payload.get("requested_at") or payload.get("started_at") or payload.get("completed_at") or state.get("updated_at"))
    started_at = _parse_timestamp(payload.get("started_at")) if payload.get("started_at") else None
    completed_at = _parse_timestamp(payload.get("completed_at")) if payload.get("completed_at") else None
    updated_at = _parse_timestamp(payload.get("updated_at") or completed_at or started_at or requested_at)
    is_latest = str((state.get("last_run") or {}).get("run_id") or "") == run_id
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else state.get("findings") if is_latest and isinstance(state.get("findings"), list) else []
    refs = payload.get("evidence_refs") if isinstance(payload.get("evidence_refs"), list) else state.get("evidence_refs") if is_latest and isinstance(state.get("evidence_refs"), list) else []
    tool_results = payload.get("tool_results") if isinstance(payload.get("tool_results"), dict) else {}
    progress = state.get("scan_progress") if is_latest and isinstance(state.get("scan_progress"), dict) else {}
    percent = progress.get("percent")
    return {
        "run_id": run_id,
        "profile": profile,
        "app_id": app_id,
        "app_label": policy.redact_text(str(payload.get("app_label") or ""))[:120],
        "status": status,
        "summary": policy.redact_text(str(payload.get("summary") or state.get("summary") or ""))[:500],
        "score": int(payload.get("score") if payload.get("score") is not None else state.get("score")) if (payload.get("score") is not None or state.get("score") is not None) else None,
        "partial_results": bool(payload.get("partial_results")),
        "requested_at": requested_at,
        "accepted_at": _parse_timestamp(payload.get("accepted_at")) if payload.get("accepted_at") else None,
        "started_at": started_at,
        "completed_at": completed_at,
        "updated_at": updated_at,
        "requested_at_epoch_ms": _epoch_ms(requested_at),
        "started_at_epoch_ms": _epoch_ms(started_at) if started_at else None,
        "completed_at_epoch_ms": _epoch_ms(completed_at) if completed_at else None,
        "updated_at_epoch_ms": _epoch_ms(updated_at),
        "current_stage": policy.redact_text(str(progress.get("stage") or ""))[:160] or None,
        "current_percent": int(percent) if percent is not None else None,
        "current_message": policy.redact_text(str(progress.get("message") or ""))[:500] or None,
        "current_tool": policy.redact_text(str(progress.get("tool") or ""))[:80] or None,
        "checks_reviewed": max(0, int(payload.get("checks_reviewed") or payload.get("checks_count") or state.get("checks_reviewed") or 0)),
        "items_to_review": max(0, int(payload.get("items_to_review") or state.get("items_to_review") or len(findings))),
        "critical_count": max(0, int(payload.get("critical_count") or 0)),
        "high_count": max(0, int(payload.get("high_count") or 0)),
        "medium_count": max(0, int(payload.get("medium_count") or 0)),
        "low_count": max(0, int(payload.get("low_count") or 0)),
        "info_count": max(0, int(payload.get("info_count") or 0)),
        "failure_code": policy.redact_text(str(payload.get("failure_code") or ""))[:120] or None,
        "failure_message": policy.redact_text(str(payload.get("failure_message") or ""))[:500] or None,
        "command_id": policy.redact_text(str(payload.get("command_id") or ""))[:160] or None,
        "correlation_id": policy.redact_text(str(payload.get("correlation_id") or ""))[:160] or None,
        "evidence_saved": bool(refs),
        "findings": findings,
        "evidence_refs": refs,
        "tool_results": tool_results,
        "progress": progress,
        "metadata": {"import_version": IMPORT_VERSION, "legacy_original_status": payload.get("status"), "legacy_source": "security/runs"},
    }


def _legacy_evidence_refs(root: Path, item: Mapping[str, Any], *, hash_evidence: bool) -> list[dict[str, Any]]:
    run_id = str(item["run_id"])
    refs: dict[str, dict[str, Any]] = {}
    maximum_hash_bytes = max(
        0,
        min(
            int(
                os.environ.get(
                    "POCKETLAB_LITE_SECURITY_IMPORT_HASH_MAX_BYTES",
                    str(1024 * 1024),
                )
            ),
            16 * 1024 * 1024,
        ),
    )
    for raw in item.get("evidence_refs") or []:
        relative = _safe_evidence_relative_path(run_id, raw)
        if relative:
            metadata: dict[str, Any] = {
                "relative_path": relative,
                "kind": Path(relative).stem,
            }
            relative_under_security = relative.removeprefix("security/")
            evidence_path = root / relative_under_security
            try:
                size = evidence_path.stat().st_size
                metadata["size_bytes"] = size
                if hash_evidence and size <= maximum_hash_bytes:
                    metadata["sha256"] = hashlib.sha256(
                        evidence_path.read_bytes()
                    ).hexdigest()
            except OSError:
                metadata["missing"] = True
            refs[relative] = metadata
    directory = root / "evidence" / evidence.safe_run_id(run_id)
    if directory.exists():
        for path in sorted(directory.glob("*.json"))[:500]:
            relative = f"security/evidence/{evidence.safe_run_id(run_id)}/{path.name}"
            metadata: dict[str, Any] = {"relative_path": relative, "kind": path.stem}
            try:
                size = path.stat().st_size
                metadata["size_bytes"] = size
                if hash_evidence and size <= maximum_hash_bytes:
                    metadata["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                metadata["missing"] = True
            refs[relative] = metadata
    return list(refs.values())


def _normalized_runs_shadow_projection(
    normalized_runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    runs = list(
        _canonical_history(
            normalized_runs,
            limit=DEFAULT_HISTORY_LIMIT,
        )
    )
    latest = runs[0] if runs else {}
    counts = {
        severity: int(latest.get(f"{severity}_count") or 0)
        for severity in policy.SEVERITIES
    }
    findings = latest.get("findings")
    if not any(counts.values()) and isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, Mapping):
                counts[policy.normalize_severity(finding.get("severity"))] += 1
    refs = latest.get("evidence_refs")
    return {
        "latest_run_id": latest.get("run_id") or "",
        "profile": latest.get("profile") or "",
        "app_id": latest.get("app_id") or "",
        "status": latest.get("status") or "",
        "score": latest.get("score"),
        "current_percent": latest.get("current_percent"),
        "current_stage": latest.get("current_stage") or "",
        "finding_counts": counts,
        "evidence_saved": bool(latest.get("evidence_saved") or refs),
        "latest_completed_at": latest.get("completed_at") or "",
        "history_count": len(runs),
        "latest_run_ids": [item.get("run_id") for item in runs],
    }


def _json_shadow_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    last = state.get("last_run") if isinstance(state.get("last_run"), Mapping) else {}
    progress = state.get("scan_progress") if isinstance(state.get("scan_progress"), Mapping) else {}
    history = list(
        _canonical_history(
            (
                item
                for item in state.get("history", [])
                if isinstance(item, Mapping)
            ),
            limit=DEFAULT_HISTORY_LIMIT,
        )
    ) if isinstance(state.get("history"), list) else []
    counts = {severity: int(last.get(f"{severity}_count") or 0) for severity in policy.SEVERITIES}
    if not any(counts.values()) and isinstance(state.get("findings"), list):
        for finding in state.get("findings") or []:
            if isinstance(finding, Mapping):
                counts[policy.normalize_severity(finding.get("severity"))] += 1
    refs = last.get("evidence_refs") if isinstance(last.get("evidence_refs"), list) else state.get("evidence_refs") if isinstance(state.get("evidence_refs"), list) else []
    return {
        "latest_run_id": last.get("run_id") or "",
        "profile": last.get("scan_profile") or last.get("profile") or "",
        "app_id": last.get("app_id") or "",
        "status": _normalize_status(last.get("status") or "succeeded") if last else "",
        "score": last.get("score") if last.get("score") is not None else state.get("score"),
        "current_percent": progress.get("percent"),
        "current_stage": progress.get("stage") or "",
        "finding_counts": counts,
        "evidence_saved": bool(refs),
        "latest_completed_at": last.get("completed_at") or "",
        "history_count": len(history),
        "latest_run_ids": [item.get("run_id") for item in history],
    }


def _projection_checksum(value: Mapping[str, Any]) -> str:
    clean = policy.redact_value(value)
    return hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _compare_projections(
    canonical_projection: Mapping[str, Any],
    sqlite_projection: Mapping[str, Any],
) -> dict[str, Any]:
    fields = sorted(set(canonical_projection) | set(sqlite_projection))
    mismatches = [
        field
        for field in fields
        if canonical_projection.get(field) != sqlite_projection.get(field)
    ]
    return {
        "matched": not mismatches,
        "mismatch_fields": mismatches,
        "json_checksum": _projection_checksum(canonical_projection),
        "sqlite_checksum": _projection_checksum(sqlite_projection),
        "compared_at": utc_now(),
    }


def shadow_compare_if_enabled(state: Mapping[str, Any]) -> dict[str, Any] | None:
    security_store_mode()  # validates the rollout switch even while JSON remains authoritative.
    if not sqlite_shadow_read_enabled():
        return None
    repository = SecuritySQLiteRepository(initialize=True)
    return repository.compare_json_state(policy.redact_value(dict(state)), record=True)
