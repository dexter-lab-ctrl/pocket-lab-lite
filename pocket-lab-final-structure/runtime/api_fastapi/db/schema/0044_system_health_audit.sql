-- Immutable, sanitized diagnostic decisions and explicit denied-remediation audit.
CREATE TABLE lite_system_health_diagnoses (
  diagnosis_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  incident_generation INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  symptom TEXT NOT NULL,
  suspected_cause TEXT NOT NULL,
  confidence TEXT NOT NULL,
  evidence_freshness TEXT NOT NULL,
  recommended_action TEXT NOT NULL
);
CREATE INDEX lite_system_health_diagnoses_incident ON lite_system_health_diagnoses(incident_id,created_at DESC);
CREATE TABLE lite_system_health_repair_denials (
  denial_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  incident_generation INTEGER NOT NULL,
  idempotency_digest TEXT NOT NULL UNIQUE,
  operation_id TEXT NOT NULL,
  risk_class TEXT NOT NULL,
  denied_at TEXT NOT NULL,
  actor_class TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  safe_summary TEXT NOT NULL
);
CREATE INDEX lite_system_health_denials_recent ON lite_system_health_repair_denials(denied_at DESC);
