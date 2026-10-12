-- Non-secret, per-human read position for prepared workspace history. Cursor is server-owned.
CREATE TABLE IF NOT EXISTS lite_home_activity_read_cursors (
 human_id TEXT PRIMARY KEY NOT NULL,
 history_revision INTEGER NOT NULL DEFAULT 0 CHECK (history_revision >= 0),
 last_reviewed_at TEXT NOT NULL
);
