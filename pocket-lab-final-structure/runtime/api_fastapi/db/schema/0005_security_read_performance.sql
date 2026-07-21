-- Hot Security list reads use deterministic keyset ordering. These expression
-- indexes prevent full scans and temporary sort B-trees as history grows.
CREATE INDEX IF NOT EXISTS idx_security_runs_history_cursor
    ON security_scan_runs(
        COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC,
        run_id DESC
    );

CREATE INDEX IF NOT EXISTS idx_security_runs_profile_history_cursor
    ON security_scan_runs(
        profile,
        app_id,
        COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC,
        run_id DESC
    );

-- Summary/profile reads use updated_at semantics rather than completed_at.
CREATE INDEX IF NOT EXISTS idx_security_runs_profile_updated_latest
    ON security_scan_runs(profile, app_id, updated_at_epoch_ms DESC, run_id DESC);

-- The app profile can span multiple app IDs; this partial index preserves the
-- global "latest app check" order without duplicating non-app rows.
CREATE INDEX IF NOT EXISTS idx_security_runs_app_updated_latest
    ON security_scan_runs(profile, updated_at_epoch_ms DESC, run_id DESC)
    WHERE profile = 'app';
