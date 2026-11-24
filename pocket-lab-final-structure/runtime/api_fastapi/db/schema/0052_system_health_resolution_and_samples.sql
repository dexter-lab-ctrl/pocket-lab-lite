-- Preserve uncertain execution history; acknowledgement is not verification.
CREATE TABLE lite_system_health_maintenance_resolutions (
    command_id TEXT PRIMARY KEY REFERENCES lite_system_health_maintenance_admissions(command_id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition='closed_unverified')
);
CREATE TABLE lite_system_health_availability_samples (
    bucket INTEGER NOT NULL,
    service_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('healthy','unhealthy','unknown')),
    PRIMARY KEY(bucket,service_id)
);
CREATE INDEX lite_system_health_availability_service ON lite_system_health_availability_samples(service_id,bucket);
