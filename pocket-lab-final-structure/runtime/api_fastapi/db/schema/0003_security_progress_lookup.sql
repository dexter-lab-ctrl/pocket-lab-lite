CREATE INDEX idx_security_runs_progress_latest
    ON security_scan_runs((active_key IS NOT NULL) DESC, updated_at_epoch_ms DESC);
