-- Device runtime truth is persisted independently from PM2 discovery and volatile
-- fleet JSON. This preserves last-good supervisor evidence across API restarts.
CREATE TABLE IF NOT EXISTS device_supervisor_state (
    device_id TEXT PRIMARY KEY,
    evidence_schema_version INTEGER NOT NULL DEFAULT 1 CHECK(evidence_schema_version BETWEEN 1 AND 100),
    supervisor_status TEXT NOT NULL DEFAULT 'unknown',
    supervisor_version TEXT NOT NULL DEFAULT '',
    supervisor_process_status TEXT NOT NULL DEFAULT 'unknown',
    agent_process_status TEXT NOT NULL DEFAULT 'unknown',
    nats_reachable INTEGER NOT NULL DEFAULT 0 CHECK(nats_reachable IN (0,1)),
    repair_status TEXT NOT NULL DEFAULT 'not_needed',
    repair_reason_code TEXT NOT NULL DEFAULT '',
    repair_count INTEGER NOT NULL DEFAULT 0 CHECK(repair_count >= 0),
    checked_at TEXT,
    checked_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    canonical_hash TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_device_supervisor_freshness
    ON device_supervisor_state(checked_at_epoch_ms DESC, device_id);

-- Preserve raw platform reporting while exposing one normalized architecture family.
ALTER TABLE device_system_profiles ADD COLUMN architecture_raw TEXT NOT NULL DEFAULT '';
ALTER TABLE device_system_profiles ADD COLUMN architecture_family TEXT NOT NULL DEFAULT '';
ALTER TABLE device_health_current ADD COLUMN dimensions_json TEXT NOT NULL DEFAULT '{}' CHECK(length(dimensions_json) <= 16384);

-- Normalize pre-existing profile rows immediately; fresh agent reports will keep
-- these columns current without requiring a device reconnect.
UPDATE device_system_profiles
SET architecture_raw = CASE
        WHEN TRIM(COALESCE(android_abi, '')) <> '' THEN LOWER(TRIM(android_abi))
        ELSE LOWER(TRIM(COALESCE(architecture, '')))
    END,
    architecture_family = CASE LOWER(TRIM(CASE
        WHEN TRIM(COALESCE(android_abi, '')) <> '' THEN android_abi
        ELSE COALESCE(architecture, '')
    END))
        WHEN 'aarch64' THEN 'arm64'
        WHEN 'arm64' THEN 'arm64'
        WHEN 'arm64-v8a' THEN 'arm64'
        WHEN 'armeabi-v7a' THEN 'arm32'
        WHEN 'armv7l' THEN 'arm32'
        WHEN 'amd64' THEN 'x86_64'
        WHEN 'x86_64' THEN 'x86_64'
        WHEN 'i686' THEN 'x86'
        WHEN 'x86' THEN 'x86'
        ELSE LOWER(TRIM(CASE
            WHEN TRIM(COALESCE(android_abi, '')) <> '' THEN android_abi
            ELSE COALESCE(architecture, '')
        END))
    END
WHERE architecture_raw = '' OR architecture_family = '';
