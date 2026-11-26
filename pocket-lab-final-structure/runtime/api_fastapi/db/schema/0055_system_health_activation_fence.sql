-- A production preference is not an activation authority by itself.  The
-- source qualification revision and the runtime rollout revision are recorded
-- only when the current Owner confirms the corresponding mode.  This table is
-- intentionally unseeded: deployment must never enable a mode.
CREATE TABLE lite_system_health_activation_fence (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    assisted_source_revision TEXT NOT NULL DEFAULT '',
    assisted_runtime_revision TEXT NOT NULL DEFAULT '',
    assisted_preference_revision INTEGER NOT NULL DEFAULT 0 CHECK(assisted_preference_revision>=0),
    automatic_source_revision TEXT NOT NULL DEFAULT '',
    automatic_runtime_revision TEXT NOT NULL DEFAULT '',
    automatic_policy_revision INTEGER NOT NULL DEFAULT 0 CHECK(automatic_policy_revision>=0),
    updated_at TEXT NOT NULL
);
INSERT INTO lite_system_health_activation_fence(
    singleton_id, assisted_source_revision, assisted_runtime_revision,
    assisted_preference_revision, automatic_source_revision,
    automatic_runtime_revision, automatic_policy_revision, updated_at
) VALUES(1, '', '', 0, '', '', 0, '1970-01-01T00:00:00Z');
