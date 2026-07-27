-- Phase 3C semantic hardening: explainable canonical commits, split activity
-- current/history domains, and a bounded cross-process dirty signal mailbox.
-- Metadata only is retained; no raw payloads, logs, evidence bodies, commands,
-- private paths, credentials, or telemetry streams are stored here.
ALTER TABLE phase3b_current_state
    ADD COLUMN canonical_hash TEXT NOT NULL DEFAULT '';

ALTER TABLE phase3b_revision_events
    ADD COLUMN previous_semantic_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE phase3b_revision_events
    ADD COLUMN new_semantic_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE phase3b_revision_events
    ADD COLUMN changed_paths_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE phase3b_revision_events
    ADD COLUMN source_revision_before INTEGER NOT NULL DEFAULT 0;
ALTER TABLE phase3b_revision_events
    ADD COLUMN source_revision_after INTEGER NOT NULL DEFAULT 0;
ALTER TABLE phase3b_revision_events
    ADD COLUMN scheduler_generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE phase3b_revision_events
    ADD COLUMN execution_owner TEXT NOT NULL DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS idx_phase3b_revision_events_domain_recent
    ON phase3b_revision_events(domain, event_id DESC);

ALTER TABLE projection_refresh_state
    ADD COLUMN source_revision INTEGER NOT NULL DEFAULT -1;
ALTER TABLE projection_refresh_state
    ADD COLUMN last_duration_ms REAL NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN execution_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN committed_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN unchanged_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN dirty_mark_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN followup_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projection_refresh_state
    ADD COLUMN trigger_reason TEXT NOT NULL DEFAULT 'event';
ALTER TABLE projection_refresh_state
    ADD COLUMN last_trigger_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE projection_refresh_state
    ADD COLUMN execution_owner TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE projection_refresh_state
    ADD COLUMN executor_build_version TEXT NOT NULL DEFAULT 'unavailable';
ALTER TABLE projection_refresh_state
    ADD COLUMN executor_process_generation TEXT NOT NULL DEFAULT 'unknown';

CREATE TABLE IF NOT EXISTS projection_dirty_signals (
    domain TEXT PRIMARY KEY,
    signal_generation INTEGER NOT NULL DEFAULT 0,
    claimed_generation INTEGER NOT NULL DEFAULT 0,
    trigger_reason TEXT NOT NULL DEFAULT 'event',
    requested_by TEXT NOT NULL DEFAULT 'unknown',
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    CHECK (signal_generation >= 0),
    CHECK (claimed_generation >= 0),
    CHECK (claimed_generation <= signal_generation)
);

CREATE INDEX IF NOT EXISTS idx_projection_dirty_signals_pending
    ON projection_dirty_signals(claimed_generation, signal_generation, updated_at_epoch_ms);

INSERT OR IGNORE INTO domain_revisions(domain, revision, updated_at) VALUES
    ('system.activity_current', 0, '1970-01-01T00:00:00Z'),
    ('system.activity_history', 0, '1970-01-01T00:00:00Z');
