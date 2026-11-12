-- Pocket Lab Lite System Health: worker-owned incident/repair history, no read-time DDL.
CREATE TABLE lite_system_health_observations (
  source TEXT NOT NULL,
  target_id TEXT NOT NULL,
  status TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  source_revision TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (source, target_id)
);
CREATE TABLE lite_system_health_incidents (
  incident_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  target_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('detected','diagnosing','diagnosed','repair_available','repairing','verifying','resolved','blocked','failed','manual_attention_required')),
  severity TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 1,
  recurrence_count INTEGER NOT NULL DEFAULT 0,
  observation_count INTEGER NOT NULL DEFAULT 1,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  evidence_revision TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL,
  suspected_cause TEXT NOT NULL DEFAULT '',
  verified_cause TEXT NOT NULL DEFAULT '',
  CHECK(length(summary) <= 240)
);
CREATE INDEX lite_system_health_incidents_current ON lite_system_health_incidents(state, last_seen_at DESC);
CREATE INDEX lite_system_health_incidents_target ON lite_system_health_incidents(source, target_id, last_seen_at DESC);
CREATE TABLE lite_system_health_repair_attempts (
  repair_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL REFERENCES lite_system_health_incidents(incident_id),
  incident_generation INTEGER NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  operation_id TEXT NOT NULL,
  risk_class TEXT NOT NULL CHECK(risk_class IN ('A','B','C')),
  execution_state TEXT NOT NULL,
  authorization_state TEXT NOT NULL,
  preflight_state TEXT NOT NULL,
  verification_state TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  completed_at TEXT,
  requested_by TEXT NOT NULL,
  safe_summary TEXT NOT NULL,
  outcome TEXT NOT NULL DEFAULT 'not_executed'
);
CREATE INDEX lite_system_health_repairs_incident ON lite_system_health_repair_attempts(incident_id, requested_at DESC);
CREATE TABLE lite_system_health_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  incident_id TEXT NOT NULL,
  generation INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  safe_summary TEXT NOT NULL
);
CREATE INDEX lite_system_health_events_recent ON lite_system_health_events(created_at DESC, id DESC);