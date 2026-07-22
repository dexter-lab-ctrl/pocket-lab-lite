-- Compact, replayable revision events for focused Lite frontend synchronization.
-- Full domain payloads, command bodies, logs, and evidence remain outside this table.
CREATE TABLE IF NOT EXISTS lite_revision_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    database_instance TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN (
        'security', 'fleet', 'apps', 'recovery', 'commands', 'storage', 'audit'
    )),
    revision INTEGER NOT NULL CHECK (revision >= 0),
    changed_ids_json TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT 'domain_state_changed',
    projection_version INTEGER NOT NULL DEFAULT 1 CHECK (projection_version > 0),
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lite_revision_events_domain_revision
    ON lite_revision_events(database_instance, domain, revision);
CREATE INDEX IF NOT EXISTS idx_lite_revision_events_replay
    ON lite_revision_events(database_instance, event_id);
CREATE INDEX IF NOT EXISTS idx_lite_revision_events_retention
    ON lite_revision_events(occurred_at_epoch_ms, event_id);

ALTER TABLE command_lifecycle ADD COLUMN lifecycle_stage TEXT NOT NULL DEFAULT 'accepted';
ALTER TABLE command_lifecycle ADD COLUMN terminal_at TEXT;
ALTER TABLE command_lifecycle ADD COLUMN ignored_redelivery INTEGER NOT NULL DEFAULT 0 CHECK (ignored_redelivery IN (0, 1));
ALTER TABLE command_lifecycle ADD COLUMN recovery_action TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_commands_lifecycle_stage
    ON command_lifecycle(lifecycle_stage, updated_at_epoch_ms DESC, command_id DESC);
