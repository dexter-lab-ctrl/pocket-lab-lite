CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL
);

CREATE TABLE security_scan_runs (
    run_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL CHECK (profile IN ('quick', 'full', 'app')),
    app_id TEXT NOT NULL DEFAULT '',
    app_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (
        status IN (
            'queued', 'accepted', 'running', 'working', 'in_progress',
            'succeeded', 'degraded', 'failed', 'cancelled'
        )
    ),
    active_key TEXT UNIQUE,
    summary TEXT NOT NULL DEFAULT '',
    score INTEGER,
    partial_results INTEGER NOT NULL DEFAULT 0 CHECK (partial_results IN (0, 1)),
    requested_at TEXT NOT NULL,
    accepted_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    requested_at_epoch_ms INTEGER NOT NULL,
    started_at_epoch_ms INTEGER,
    completed_at_epoch_ms INTEGER,
    updated_at_epoch_ms INTEGER NOT NULL,
    current_stage TEXT,
    current_percent INTEGER CHECK (current_percent BETWEEN 0 AND 100),
    current_message TEXT,
    current_tool TEXT,
    checks_reviewed INTEGER NOT NULL DEFAULT 0,
    items_to_review INTEGER NOT NULL DEFAULT 0,
    critical_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    info_count INTEGER NOT NULL DEFAULT 0,
    timeout_reason TEXT,
    failure_code TEXT,
    failure_message TEXT,
    command_id TEXT,
    correlation_id TEXT,
    source TEXT NOT NULL DEFAULT 'security-worker',
    revision INTEGER NOT NULL DEFAULT 1,
    evidence_saved INTEGER NOT NULL DEFAULT 0 CHECK (evidence_saved IN (0, 1)),
    metadata_json TEXT,
    CHECK (
        (status IN ('queued', 'accepted', 'running', 'working', 'in_progress') AND active_key IS NOT NULL)
        OR
        (status NOT IN ('queued', 'accepted', 'running', 'working', 'in_progress') AND active_key IS NULL)
    )
);

CREATE TABLE security_scan_progress_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    status TEXT NOT NULL,
    stage TEXT,
    percent INTEGER CHECK (percent BETWEEN 0 AND 100),
    message TEXT,
    tool TEXT,
    created_at TEXT NOT NULL,
    created_at_epoch_ms INTEGER NOT NULL,
    payload_json TEXT,
    fingerprint TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES security_scan_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, sequence_no),
    UNIQUE (run_id, fingerprint)
);

CREATE TABLE security_scan_findings (
    finding_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    finding_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    source TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    component TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'present',
    first_seen_at TEXT,
    last_seen_at TEXT,
    resolved_at TEXT,
    remediation_json TEXT,
    technical_json TEXT,
    FOREIGN KEY (run_id) REFERENCES security_scan_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, finding_key)
);

CREATE TABLE security_scan_evidence_refs (
    evidence_ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (run_id) REFERENCES security_scan_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, relative_path)
);

CREATE TABLE security_scan_tool_runs (
    tool_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    finding_count INTEGER NOT NULL DEFAULT 0,
    timed_out INTEGER NOT NULL DEFAULT 0 CHECK (timed_out IN (0, 1)),
    timeout_reason TEXT,
    metadata_json TEXT,
    FOREIGN KEY (run_id) REFERENCES security_scan_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, tool_name)
);

CREATE TABLE security_profile_snapshots (
    profile TEXT NOT NULL CHECK (profile IN ('quick', 'full', 'app')),
    app_id TEXT NOT NULL DEFAULT '',
    latest_run_id TEXT NOT NULL,
    latest_status TEXT NOT NULL,
    latest_score INTEGER,
    latest_summary TEXT NOT NULL DEFAULT '',
    latest_completed_at TEXT,
    latest_evidence_at TEXT,
    updated_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (profile, app_id),
    FOREIGN KEY (latest_run_id) REFERENCES security_scan_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE domain_revisions (
    domain TEXT PRIMARY KEY,
    revision INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE security_store_metadata (
    metadata_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_security_runs_profile_completed
    ON security_scan_runs(profile, app_id, completed_at_epoch_ms DESC);
CREATE INDEX idx_security_runs_status_updated
    ON security_scan_runs(status, updated_at_epoch_ms DESC);
CREATE INDEX idx_security_progress_run_event
    ON security_scan_progress_events(run_id, event_id DESC);
CREATE INDEX idx_security_progress_created
    ON security_scan_progress_events(created_at_epoch_ms DESC);
CREATE INDEX idx_security_findings_run_severity
    ON security_scan_findings(run_id, severity, status);
CREATE INDEX idx_security_findings_fingerprint
    ON security_scan_findings(fingerprint);
CREATE INDEX idx_security_evidence_run_kind
    ON security_scan_evidence_refs(run_id, kind);
CREATE INDEX idx_security_tool_runs_run
    ON security_scan_tool_runs(run_id);

INSERT OR IGNORE INTO domain_revisions(domain, revision, updated_at)
VALUES ('security', 0, '1970-01-01T00:00:00Z');
