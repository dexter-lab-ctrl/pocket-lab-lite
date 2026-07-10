from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .connection import begin_immediate, connection


class MigrationError(RuntimeError):
    """Base migration failure."""


class MigrationChecksumError(MigrationError):
    """An applied migration changed after deployment."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str


_MIGRATION_RE = re.compile(r"^(\d+)_([a-z0-9_\-]+)\.sql$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def schema_dir() -> Path:
    return Path(__file__).with_name("schema")


def discover_migrations(directory: Path | None = None) -> list[Migration]:
    root = directory or schema_dir()
    migrations: list[Migration] = []
    for path in sorted(root.glob("*.sql")):
        match = _MIGRATION_RE.match(path.name)
        if not match:
            continue
        raw = path.read_bytes()
        migrations.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                path=path,
                checksum=hashlib.sha256(raw).hexdigest(),
                sql=raw.decode("utf-8"),
            )
        )
    versions = [item.version for item in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError("duplicate SQLite migration version")
    return migrations


def _statements(sql: str) -> Iterable[str]:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise MigrationError("incomplete SQL statement in migration")


def _ensure_metadata_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
        """
    )


def apply_migrations(directory: Path | None = None) -> list[int]:
    migrations = discover_migrations(directory)
    applied_now: list[int] = []
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_metadata_table(tx)
            applied = {
                int(row["version"]): (str(row["name"]), str(row["checksum"]))
                for row in tx.execute(
                    "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
                )
            }
            known_versions = {item.version for item in migrations}
            unexpected = sorted(set(applied) - known_versions)
            if unexpected:
                raise MigrationError(
                    f"database schema is newer than this runtime: {unexpected}"
                )
            for migration in migrations:
                prior = applied.get(migration.version)
                if prior:
                    prior_name, prior_checksum = prior
                    if prior_name != migration.name or prior_checksum != migration.checksum:
                        raise MigrationChecksumError(
                            f"migration {migration.version} checksum/name mismatch"
                        )
                    continue
                for statement in _statements(migration.sql):
                    tx.execute(statement)
                tx.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
                    (migration.version, migration.name, utc_now(), migration.checksum),
                )
                applied_now.append(migration.version)
    return applied_now


def current_schema_version() -> int:
    with connection() as conn:
        _ensure_metadata_table(conn)
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
        return int(row["version"] if row else 0)


def migration_rows() -> list[dict[str, object]]:
    with connection() as conn:
        _ensure_metadata_table(conn)
        return [dict(row) for row in conn.execute(
            "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version"
        )]
