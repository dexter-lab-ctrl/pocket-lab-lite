ALTER TABLE app_current_state ADD COLUMN catalog_state_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN media_state_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN operation_state_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN update_state_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN backup_profile_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN projection_version INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_app_current_updated
    ON app_current_state(updated_at_epoch_ms DESC, app_id);
