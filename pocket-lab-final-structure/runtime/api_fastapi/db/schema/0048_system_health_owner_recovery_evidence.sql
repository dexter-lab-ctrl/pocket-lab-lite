-- Owner-reported recovery evidence independent of operator-request admissions.
-- This table never authorizes execution. Only existing owner callbacks write it.
CREATE TABLE lite_system_health_owner_recovery_evidence (
    evidence_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL CHECK(operation_id='runtime.consumer.reconnect'),
    execution_owner TEXT NOT NULL CHECK(execution_owner='nats_worker_watchdog'),
    target_scope TEXT NOT NULL CHECK(target_scope='local_worker_consumer'),
    owner_instance TEXT NOT NULL,
    consumer_generation INTEGER NOT NULL CHECK(consumer_generation >= 0),
    incident_id TEXT,
    incident_generation INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    verification_state TEXT NOT NULL CHECK(verification_state IN ('pending','verified','failed','unavailable')),
    verified_at TEXT,
    UNIQUE(owner_instance,consumer_generation)
);
CREATE INDEX lite_system_health_owner_recovery_recent
    ON lite_system_health_owner_recovery_evidence(completed_at DESC);
CREATE INDEX lite_system_health_owner_recovery_pending
    ON lite_system_health_owner_recovery_evidence(verification_state,completed_at);
