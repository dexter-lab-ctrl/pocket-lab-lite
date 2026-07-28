CREATE TABLE IF NOT EXISTS workflow_current_state (
    workflow_id TEXT PRIMARY KEY,
    projection_json TEXT NOT NULL,
    canonical_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    terminal INTEGER NOT NULL DEFAULT 0 CHECK (terminal IN (0, 1)),
    revision INTEGER NOT NULL DEFAULT 1,
    semantic_event_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    process_generation INTEGER NOT NULL DEFAULT 0,
    database_instance TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_workflow_current_status_updated
    ON workflow_current_state(status, updated_at_epoch_ms DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_current_terminal_updated
    ON workflow_current_state(terminal, updated_at_epoch_ms DESC);

CREATE TABLE IF NOT EXISTS workflow_event_index (
    event_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    event_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    observed_at_epoch_ms INTEGER NOT NULL,
    process_generation INTEGER NOT NULL DEFAULT 0,
    database_instance TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_workflow_event_workflow_time
    ON workflow_event_index(workflow_id, observed_at_epoch_ms DESC, event_id DESC);

CREATE TABLE IF NOT EXISTS workflow_command_state (
    command_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL DEFAULT '',
    command_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    process_generation INTEGER NOT NULL DEFAULT 0,
    database_instance TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_workflow_command_workflow
    ON workflow_command_state(workflow_id, updated_at_epoch_ms DESC);
