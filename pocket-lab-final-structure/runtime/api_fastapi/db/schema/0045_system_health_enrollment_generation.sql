-- Durable enrollment generation fencing for System Health projections.
-- Generation 1 is the deterministic backfill for the existing terminal
-- enrollment model. Removed identities remain terminal and cannot be reused;
-- an explicitly authorized future re-enrollment must create a new registry
-- record/generation through the enrollment owner rather than a heartbeat.
ALTER TABLE device_enrollment_registry
    ADD COLUMN enrollment_generation INTEGER NOT NULL DEFAULT 1
    CHECK(enrollment_generation >= 1);

ALTER TABLE device_removal_receipts
    ADD COLUMN enrollment_generation INTEGER NOT NULL DEFAULT 1
    CHECK(enrollment_generation >= 1);

ALTER TABLE lite_system_health_observations
    ADD COLUMN enrollment_generation INTEGER NOT NULL DEFAULT 0
    CHECK(enrollment_generation >= 0);

ALTER TABLE lite_system_health_incidents
    ADD COLUMN enrollment_generation INTEGER NOT NULL DEFAULT 0
    CHECK(enrollment_generation >= 0);

UPDATE lite_system_health_observations
SET enrollment_generation = COALESCE((
    SELECT registry.enrollment_generation
    FROM device_enrollment_registry AS registry
    WHERE registry.device_id=lite_system_health_observations.target_id
), 0)
WHERE source IN ('agent','supervisor','telemetry');

UPDATE lite_system_health_incidents
SET enrollment_generation = COALESCE((
    SELECT registry.enrollment_generation
    FROM device_enrollment_registry AS registry
    WHERE registry.device_id=lite_system_health_incidents.target_id
), 0)
WHERE source IN ('agent','supervisor','telemetry');

UPDATE device_removal_receipts
SET enrollment_generation = COALESCE((
    SELECT registry.enrollment_generation
    FROM device_enrollment_registry AS registry
    WHERE registry.device_id=device_removal_receipts.device_id
), 1);

CREATE INDEX IF NOT EXISTS idx_device_enrollment_generation
    ON device_enrollment_registry(device_id,enrollment_generation,removal_status);
CREATE INDEX IF NOT EXISTS idx_lite_system_health_incident_generation
    ON lite_system_health_incidents(target_id,enrollment_generation,last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_lite_system_health_observation_generation
    ON lite_system_health_observations(target_id,enrollment_generation,observed_at DESC);
