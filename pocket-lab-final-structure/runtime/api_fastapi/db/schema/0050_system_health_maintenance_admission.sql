-- Admission fence for existing NATS maintenance owner. The command lifecycle
-- remains authoritative for delivery; this records scope and execution evidence.
CREATE TABLE lite_system_health_maintenance_admissions (
    command_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL CHECK(operation_id IN ('storage.evidence.preview','storage.evidence.retention','sqlite.checkpoint.passive','recovery.database.rehearse','projection.reconcile','storage.logs.preview','storage.logs.cleanup','storage.temp.preview','storage.temp.cleanup','runtime.telemetry.recover','runtime.server_agent.recover')),
    actor_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    idempotency_digest TEXT NOT NULL UNIQUE,
    preview_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('queued','executing','verified','blocked','uncertain','expired','cancelled')),
    requested_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    completed_at TEXT,
    candidate_json TEXT NOT NULL DEFAULT '[]' CHECK(length(candidate_json)<=32768),
    evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(length(evidence_json)<=4096)
);
CREATE UNIQUE INDEX lite_system_health_maintenance_singleflight
ON lite_system_health_maintenance_admissions((1)) WHERE status IN ('queued','executing');
CREATE INDEX lite_system_health_maintenance_recent ON lite_system_health_maintenance_admissions(requested_at DESC);
