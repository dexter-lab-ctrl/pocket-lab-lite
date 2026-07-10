"""Backend-only SQLite primitives for Pocket Lab Lite.

The browser never imports or accesses this package.  Security remains JSON-backed
until the explicit later rollout phases select another store mode.
"""

from .connection import (
    SQLiteConfigurationError,
    begin_immediate,
    connection,
    database_path,
    online_backup,
    read_connection,
    sqlite_settings,
)
from .migrations import apply_migrations, current_schema_version

__all__ = [
    "SQLiteConfigurationError",
    "apply_migrations",
    "begin_immediate",
    "connection",
    "current_schema_version",
    "database_path",
    "online_backup",
    "read_connection",
    "sqlite_settings",
]
