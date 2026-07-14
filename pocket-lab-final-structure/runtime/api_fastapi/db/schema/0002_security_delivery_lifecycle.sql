ALTER TABLE security_scan_runs ADD COLUMN command_published_at TEXT;
ALTER TABLE security_scan_runs ADD COLUMN command_published_at_epoch_ms INTEGER;
ALTER TABLE security_scan_runs ADD COLUMN command_received_at TEXT;
ALTER TABLE security_scan_runs ADD COLUMN command_received_at_epoch_ms INTEGER;
ALTER TABLE security_scan_runs ADD COLUMN execution_started_at TEXT;
ALTER TABLE security_scan_runs ADD COLUMN execution_started_at_epoch_ms INTEGER;
ALTER TABLE security_scan_runs ADD COLUMN last_progress_at TEXT;
ALTER TABLE security_scan_runs ADD COLUMN last_progress_at_epoch_ms INTEGER;
ALTER TABLE security_scan_runs ADD COLUMN delivery_attempt INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_security_runs_delivery_state
    ON security_scan_runs(status, command_received_at_epoch_ms, execution_started_at_epoch_ms, updated_at_epoch_ms);
