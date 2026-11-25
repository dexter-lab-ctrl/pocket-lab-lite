CREATE TABLE lite_system_health_service_owner_evidence (
    evidence_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    process_instance_digest TEXT NOT NULL,
    owner_generation INTEGER NOT NULL CHECK(owner_generation>=0),
    completed_at TEXT NOT NULL,
    verification_state TEXT NOT NULL CHECK(verification_state IN ('pending','verified','unavailable')),
    verified_at TEXT
);
CREATE INDEX lite_system_health_service_owner_pending ON lite_system_health_service_owner_evidence(verification_state,completed_at);
CREATE INDEX lite_system_health_service_owner_recent ON lite_system_health_service_owner_evidence(completed_at DESC);
