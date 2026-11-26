ALTER TABLE lite_lifecycle_audit ADD COLUMN decision_id TEXT;
ALTER TABLE lite_lifecycle_audit ADD COLUMN grant_id TEXT;
ALTER TABLE lite_lifecycle_audit ADD COLUMN reason_code TEXT NOT NULL DEFAULT '';
CREATE INDEX idx_lifecycle_audit_decision ON lite_lifecycle_audit(decision_id);
