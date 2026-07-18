from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .. import deps


class SQLiteConfigurationError(RuntimeError):
    """Raised when a bounded SQLite setting or database path is unsafe."""


@dataclass(frozen=True)
class SQLiteSettings:
    path: Path
    busy_timeout_ms: int
    synchronous: str
    wal_autocheckpoint: int


_UNSAFE_PATH_PARTS = (
    "/storage/emulated/",
    "/sdcard/",
    "/mnt/sdcard/",
)
_UNSAFE_NETWORK_FILESYSTEMS = {
    "9p",
    "cifs",
    "fuse.sshfs",
    "nfs",
    "nfs4",
    "smb3",
}
_VALID_SYNCHRONOUS = {"NORMAL", "FULL"}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_FRONTEND_STORAGE_ROOTS = tuple(
    (_REPOSITORY_ROOT / name).resolve(strict=False)
    for name in ("src", "public", "dist", "pwa_dist")
)


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SQLiteConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SQLiteConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _resolved_database_path() -> Path:
    override = os.environ.get("POCKETLAB_LITE_DB_PATH", "").strip()
    state_dir = "" if override else str(deps.settings().state_dir)
    return _resolved_database_path_cached(override, state_dir)


@lru_cache(maxsize=16)
def _resolved_database_path_cached(override: str, state_dir: str) -> Path:
    raw_candidate = (
        Path(override).expanduser()
        if override
        else Path(state_dir) / "pocketlab-lite.sqlite3"
    )
    raw_normalized = raw_candidate.as_posix().lower()
    candidate = raw_candidate.resolve(strict=False)
    normalized = candidate.as_posix().lower()
    if candidate.name in {"", ".", ".."} or candidate.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise SQLiteConfigurationError("POCKETLAB_LITE_DB_PATH must name a .db, .sqlite, or .sqlite3 file")
    if any(
        part in normalized or part in raw_normalized for part in _UNSAFE_PATH_PARTS
    ):
        raise SQLiteConfigurationError("Pocket Lab SQLite must not use Android shared storage")
    if candidate.parent == _REPOSITORY_ROOT:
        raise SQLiteConfigurationError("Pocket Lab SQLite must not be stored in the repository root")
    if any(candidate == root or root in candidate.parents for root in _FRONTEND_STORAGE_ROOTS):
        raise SQLiteConfigurationError("Pocket Lab SQLite must not be stored in frontend/PWA files")
    filesystem = _filesystem_type(candidate.parent)
    if filesystem in _UNSAFE_NETWORK_FILESYSTEMS:
        raise SQLiteConfigurationError(
            f"Pocket Lab SQLite does not support the {filesystem} filesystem"
        )
    return candidate


def _filesystem_type(path: Path) -> str | None:
    """Best-effort mount lookup; unavailable mount metadata is not fatal."""
    mounts = Path("/proc/mounts")
    try:
        entries = mounts.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    resolved = path.resolve(strict=False)
    best: tuple[int, str] | None = None
    for line in entries:
        fields = line.split()
        if len(fields) < 3:
            continue
        mount_point = Path(fields[1].replace("\\040", " ")).resolve(strict=False)
        if resolved != mount_point and mount_point not in resolved.parents:
            continue
        candidate = (len(mount_point.parts), fields[2].strip().lower())
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def sqlite_settings() -> SQLiteSettings:
    synchronous = os.environ.get("POCKETLAB_LITE_DB_SYNCHRONOUS", "NORMAL").strip().upper()
    if synchronous not in _VALID_SYNCHRONOUS:
        raise SQLiteConfigurationError(
            "POCKETLAB_LITE_DB_SYNCHRONOUS must be NORMAL or FULL"
        )
    busy_timeout_ms = _bounded_int(
        "POCKETLAB_LITE_DB_BUSY_TIMEOUT_MS", 20_000, minimum=1_000, maximum=120_000
    )
    wal_autocheckpoint = _bounded_int(
        "POCKETLAB_LITE_DB_WAL_AUTOCHECKPOINT", 1_000, minimum=1, maximum=100_000
    )
    override = os.environ.get("POCKETLAB_LITE_DB_PATH", "").strip()
    state_dir = "" if override else str(deps.settings().state_dir)
    return _sqlite_settings_cached(
        override, state_dir, busy_timeout_ms, synchronous, wal_autocheckpoint
    )


@lru_cache(maxsize=16)
def _sqlite_settings_cached(
    override: str,
    state_dir: str,
    busy_timeout_ms: int,
    synchronous: str,
    wal_autocheckpoint: int,
) -> SQLiteSettings:
    return SQLiteSettings(
        path=_resolved_database_path_cached(override, state_dir),
        busy_timeout_ms=busy_timeout_ms,
        synchronous=synchronous,
        wal_autocheckpoint=wal_autocheckpoint,
    )


def reset_sqlite_path_cache() -> None:
    """Clear process-local path/settings caches for tests or explicit reconfiguration."""
    _resolved_database_path_cached.cache_clear()
    _sqlite_settings_cached.cache_clear()


def database_path() -> Path:
    return sqlite_settings().path


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except (NotImplementedError, OSError):
        # Windows-mounted development filesystems may not support POSIX modes.
        # The caller still receives a usable database; health tooling reports the path.
        return


def ensure_database_parent(path: Path | None = None) -> Path:
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(target.parent, 0o700)
    return target


def online_backup(
    destination: Path,
    *,
    pages: int | None = None,
    sleep: float | None = None,
    progress=None,
) -> Path:
    """Create a bounded consistent SQLite backup without copying WAL/SHM files."""
    source_path = database_path()
    target = Path(destination).expanduser().resolve(strict=False)
    if target == source_path:
        raise SQLiteConfigurationError("SQLite backup destination must differ from the live database")
    if target.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise SQLiteConfigurationError("SQLite backup destination must use a database file suffix")
    bounded_pages = pages if pages is not None else _bounded_int(
        "POCKETLAB_LITE_DB_BACKUP_PAGES", 256, minimum=1, maximum=65_536
    )
    bounded_sleep = sleep if sleep is not None else (
        _bounded_int(
            "POCKETLAB_LITE_DB_BACKUP_SLEEP_MS", 25, minimum=0, maximum=1_000
        ) / 1000.0
    )
    ensure_database_parent(target)
    with read_connection() as source:
        backup = sqlite3.connect(str(target), isolation_level=None)
        try:
            source.backup(
                backup,
                pages=int(bounded_pages),
                progress=progress,
                sleep=float(bounded_sleep),
            )
        finally:
            backup.close()
    _chmod_best_effort(target, 0o600)
    return target


def _apply_connection_policy(conn: sqlite3.Connection, settings: SQLiteSettings, *, read_only: bool) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {settings.busy_timeout_ms}")
    conn.execute(f"PRAGMA synchronous = {settings.synchronous}")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute(f"PRAGMA wal_autocheckpoint = {settings.wal_autocheckpoint}")
    if not read_only:
        journal_mode = _enable_wal_with_retry(conn, settings.busy_timeout_ms)
        if journal_mode != "wal":
            raise SQLiteConfigurationError(f"SQLite journal_mode is {journal_mode!r}, expected 'wal'")
    else:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal_mode != "wal":
            raise SQLiteConfigurationError(f"SQLite journal_mode is {journal_mode!r}, expected 'wal'")
        conn.execute("PRAGMA query_only = ON")
    if int(conn.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
        raise SQLiteConfigurationError("SQLite foreign_keys could not be enabled")
    if int(conn.execute("PRAGMA busy_timeout").fetchone()[0]) != settings.busy_timeout_ms:
        raise SQLiteConfigurationError("SQLite busy_timeout does not match the configured policy")
    expected_synchronous = 1 if settings.synchronous == "NORMAL" else 2
    if int(conn.execute("PRAGMA synchronous").fetchone()[0]) != expected_synchronous:
        raise SQLiteConfigurationError("SQLite synchronous does not match the configured policy")
    if int(conn.execute("PRAGMA temp_store").fetchone()[0]) != 2:
        raise SQLiteConfigurationError("SQLite temp_store could not be set to MEMORY")
    if int(conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]) != settings.wal_autocheckpoint:
        raise SQLiteConfigurationError(
            "SQLite wal_autocheckpoint does not match the configured policy"
        )


def _enable_wal_with_retry(conn: sqlite3.Connection, busy_timeout_ms: int) -> str:
    """Handle the short first-open race when API and worker create the DB together."""
    deadline = time.monotonic() + (busy_timeout_ms / 1000)
    delay = 0.025
    while True:
        try:
            return str(conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" not in message and "busy" not in message:
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SQLiteConfigurationError(
                    "SQLite journal_mode could not be configured before the busy timeout"
                ) from exc
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 0.25)


def progress_read_timeout_ms() -> int:
    """Short, bounded timeout for latency-sensitive live progress reads."""
    return _bounded_int(
        "POCKETLAB_LITE_DB_PROGRESS_READ_TIMEOUT_MS",
        250,
        minimum=25,
        maximum=2_000,
    )


def open_fast_read_connection(*, timeout_ms: int | None = None) -> sqlite3.Connection:
    """Open a read-only connection without write-oriented PRAGMA validation.

    Live progress reads must never inherit the general 20-second writer busy
    timeout. WAL readers are safe to fail fast and use a last-known snapshot.
    """
    settings = sqlite_settings()
    path = settings.path
    if not path.exists():
        raise FileNotFoundError(path)
    bounded_timeout = progress_read_timeout_ms() if timeout_ms is None else max(25, min(int(timeout_ms), 2_000))
    conn = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
        uri=True,
        timeout=bounded_timeout / 1000,
        isolation_level=None,
        check_same_thread=False,
    )
    try:
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {bounded_timeout}")
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn
    except Exception:
        conn.close()
        raise


def open_connection(
    *, read_only: bool = False, timing_sink: dict[str, float] | None = None
) -> sqlite3.Connection:
    total_started = time.monotonic()
    path_started = total_started
    settings = sqlite_settings()
    path = settings.path
    path_done = time.monotonic()
    connect_started = path_done
    if read_only:
        if not path.exists():
            raise FileNotFoundError(path)
        conn = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro",
            uri=True,
            timeout=settings.busy_timeout_ms / 1000,
            isolation_level=None,
            check_same_thread=False,
        )
    else:
        ensure_database_parent(path)
        conn = sqlite3.connect(
            str(path),
            timeout=settings.busy_timeout_ms / 1000,
            isolation_level=None,
            check_same_thread=False,
        )
    connect_done = time.monotonic()
    policy_started = connect_done
    try:
        _apply_connection_policy(conn, settings, read_only=read_only)
        policy_done = time.monotonic()
        if not read_only:
            _chmod_best_effort(path, 0o600)
        if timing_sink is not None:
            timing_sink.update({
                "path_resolve_ms": max(0.0, (path_done - path_started) * 1000.0),
                "sqlite_connect_ms": max(0.0, (connect_done - connect_started) * 1000.0),
                "pragma_setup_ms": max(0.0, (policy_done - policy_started) * 1000.0),
                "total_ms": max(0.0, (policy_done - total_started) * 1000.0),
            })
        return conn
    except Exception:
        conn.close()
        raise


@contextmanager
def connection(
    *, timing_sink: dict[str, float] | None = None
) -> Iterator[sqlite3.Connection]:
    conn = open_connection(read_only=False, timing_sink=timing_sink)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def fast_read_connection(*, timeout_ms: int | None = None) -> Iterator[sqlite3.Connection]:
    conn = open_fast_read_connection(timeout_ms=timeout_ms)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def read_connection() -> Iterator[sqlite3.Connection]:
    conn = open_connection(read_only=True)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def begin_immediate(conn: sqlite3.Connection | None = None) -> Iterator[sqlite3.Connection]:
    owned = conn is None
    active = conn or open_connection(read_only=False)
    try:
        active.execute("BEGIN IMMEDIATE")
        yield active
        active.execute("COMMIT")
    except Exception:
        try:
            active.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        if owned:
            active.close()
