-- Phase D1: bounded, sanitized current system identity and health metadata.
-- Agent heartbeats remain authoritative; this table is a prepared read projection only.
CREATE TABLE IF NOT EXISTS device_system_profiles (
    node_id TEXT PRIMARY KEY,
    profile_schema_version INTEGER NOT NULL DEFAULT 1 CHECK (profile_schema_version BETWEEN 1 AND 100),
    os_family TEXT NOT NULL DEFAULT '',
    os_name TEXT NOT NULL DEFAULT '',
    os_version TEXT NOT NULL DEFAULT '',
    android_api_level INTEGER,
    security_patch TEXT NOT NULL DEFAULT '',
    manufacturer TEXT NOT NULL DEFAULT '',
    technical_model TEXT NOT NULL DEFAULT '',
    device_codename TEXT NOT NULL DEFAULT '',
    consumer_model_name TEXT NOT NULL DEFAULT '',
    architecture TEXT NOT NULL DEFAULT '',
    android_abi TEXT NOT NULL DEFAULT '',
    kernel TEXT NOT NULL DEFAULT '',
    runtime_type TEXT NOT NULL DEFAULT 'unknown',
    termux_version TEXT NOT NULL DEFAULT '',
    python_version TEXT NOT NULL DEFAULT '',
    agent_version TEXT NOT NULL DEFAULT '',
    supervisor_version TEXT NOT NULL DEFAULT '',
    profile_fingerprint TEXT NOT NULL DEFAULT '',
    profile_status TEXT NOT NULL DEFAULT 'unavailable',
    uptime_seconds INTEGER,
    load_average_1m REAL,
    load_average_5m REAL,
    load_average_15m REAL,
    load_status TEXT NOT NULL DEFAULT 'unavailable',
    uptime_status TEXT NOT NULL DEFAULT 'unavailable',
    profile_collected_at TEXT,
    profile_collected_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    health_collected_at TEXT,
    health_collected_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    FOREIGN KEY(node_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_system_profiles_updated
    ON device_system_profiles(updated_at_epoch_ms DESC, node_id);
