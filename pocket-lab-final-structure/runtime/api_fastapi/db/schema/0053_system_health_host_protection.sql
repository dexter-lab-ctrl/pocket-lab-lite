CREATE TABLE lite_system_health_host_protection (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    observed_at TEXT NOT NULL,
    metadata_observed_at TEXT,
    payload_json TEXT NOT NULL CHECK(length(payload_json)<=4096)
);
