-- Durable request authority and owner preferences. No qualification or activation
-- is seeded here. Session references are internal identifiers, not credentials.
CREATE TABLE lite_system_health_request_authority (
    request_id TEXT PRIMARY KEY REFERENCES lite_system_health_recovery_requests(request_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL CHECK(length(session_id) BETWEEN 1 AND 120),
    actor_role TEXT NOT NULL CHECK(actor_role IN ('Owner','Admin','Operator')),
    authorization_version INTEGER NOT NULL CHECK(authorization_version >= 1),
    enterprise_enabled INTEGER NOT NULL CHECK(enterprise_enabled IN (0,1)),
    confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1))
);
CREATE TABLE lite_system_health_preferences (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    revision INTEGER NOT NULL CHECK(revision>=1),
    recovery_mode TEXT NOT NULL CHECK(recovery_mode IN ('monitor','assisted')),
    resource_mode TEXT NOT NULL CHECK(resource_mode IN ('balanced','low_power','maintenance')),
    updated_at TEXT NOT NULL
);
CREATE TABLE lite_system_health_control_audit (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('preferences_changed','recovery_cancelled','diagnostics_exported')),
    subject_id TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);
CREATE INDEX lite_system_health_control_audit_recent ON lite_system_health_control_audit(event_id DESC);
