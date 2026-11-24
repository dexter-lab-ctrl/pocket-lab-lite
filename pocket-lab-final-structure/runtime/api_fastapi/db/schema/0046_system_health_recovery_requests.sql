-- Bounded, server-owned System Health recovery admission.
-- This is a request ledger, not a second executor. The existing worker
-- recovery watchdog is the only component allowed to call the recovery owner.
CREATE TABLE lite_system_health_recovery_requests (
    request_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES lite_system_health_incidents(incident_id),
    incident_generation INTEGER NOT NULL CHECK(incident_generation >= 1),
    enrollment_generation INTEGER NOT NULL DEFAULT 0 CHECK(enrollment_generation >= 0),
    operation_id TEXT NOT NULL CHECK(operation_id='runtime.consumer.reconnect'),
    target_type TEXT NOT NULL CHECK(target_type='system_health_incident'),
    target_id TEXT NOT NULL,
    target_revision TEXT NOT NULL DEFAULT '',
    idempotency_digest TEXT NOT NULL UNIQUE,
    request_digest TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    policy_revision TEXT NOT NULL DEFAULT '',
    policy_decision_id TEXT NOT NULL DEFAULT '',
    authorization_state TEXT NOT NULL CHECK(authorization_state IN ('pending','authorized','approval_required','denied','stale')),
    approval_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN (
        'requested','preflight_checked','approval_required','approved','admitted',
        'accepted','executing','awaiting_verification','verified','denied',
        'blocked','expired','cancelled','execution_failed','verification_failed',
        'verification_unavailable','manual_attention_required'
    )),
    execution_state TEXT NOT NULL CHECK(execution_state IN ('not_started','queued','accepted','running','succeeded','failed','cancelled','blocked')),
    verification_state TEXT NOT NULL CHECK(verification_state IN ('not_started','pending','verified','failed','unavailable')),
    requested_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    lease_until TEXT,
    completed_at TEXT,
    attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt >= 0 AND attempt <= 3),
    max_attempts INTEGER NOT NULL DEFAULT 2 CHECK(max_attempts BETWEEN 0 AND 3),
    before_evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(length(before_evidence_json) <= 4096),
    after_evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(length(after_evidence_json) <= 4096),
    safe_summary TEXT NOT NULL DEFAULT '' CHECK(length(safe_summary) <= 240),
    outcome TEXT NOT NULL DEFAULT 'not_executed' CHECK(length(outcome) <= 80),
    terminal_reason TEXT NOT NULL DEFAULT '' CHECK(length(terminal_reason) <= 120)
);

CREATE INDEX lite_system_health_recovery_ready
    ON lite_system_health_recovery_requests(status,available_at,requested_at);
CREATE INDEX lite_system_health_recovery_incident
    ON lite_system_health_recovery_requests(incident_id,requested_at DESC);
CREATE INDEX lite_system_health_recovery_actor
    ON lite_system_health_recovery_requests(actor_id,requested_at DESC);
CREATE UNIQUE INDEX lite_system_health_recovery_single_flight
    ON lite_system_health_recovery_requests(incident_id,operation_id)
    WHERE status IN ('requested','preflight_checked','approval_required','approved','admitted','accepted','executing','awaiting_verification');
