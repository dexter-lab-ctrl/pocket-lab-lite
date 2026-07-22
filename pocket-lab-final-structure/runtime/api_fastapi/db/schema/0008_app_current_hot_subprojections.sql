ALTER TABLE app_current_state ADD COLUMN security_profile_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE app_current_state ADD COLUMN backup_targets_json TEXT NOT NULL DEFAULT '{}';
