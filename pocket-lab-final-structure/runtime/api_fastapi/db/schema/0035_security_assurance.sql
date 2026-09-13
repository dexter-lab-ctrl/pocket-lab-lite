-- Durable state for the least-privileged runtime security assurance runner.
-- Values are normalized summaries only; raw scanner output never enters these
-- tables. Runtime assurance remains separate from the existing Security scan
-- lifecycle while reusing its worker-owned scanner path.

CREATE TABLE assurance_runs (
    run_id TEXT PRIMARY KEY CHECK (run_id GLOB 'assurance-*'),
    suite_id TEXT NOT NULL CHECK (suite_id IN ('smoke', 'standard', 'deep', 'adversarial')),
    profile TEXT NOT NULL CHECK (profile = 'security-assurance-runner'),
    scenario_id TEXT,
    baseline_run_id TEXT,
    principal_id TEXT NOT NULL,
    harness_session_id TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose = 'security.assurance'),
    target_scope TEXT NOT NULL CHECK (target_scope = 'local_server_host_only'),
    runtime_id TEXT NOT NULL,
    revision_sha TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'PASS', 'FAIL', 'PARTIAL', 'BLOCKED')),
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1)),
    preflight_json TEXT NOT NULL DEFAULT '{}',
    summary_json TEXT NOT NULL DEFAULT '{}',
    report_json TEXT NOT NULL DEFAULT '{}',
    failure_code TEXT,
    requested_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (baseline_run_id) REFERENCES assurance_runs(run_id) ON DELETE SET NULL,
    FOREIGN KEY (principal_id) REFERENCES synthetic_principals(principal_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_assurance_one_active
    ON assurance_runs(status)
    WHERE status IN ('QUEUED', 'RUNNING');

CREATE INDEX idx_assurance_runs_history
    ON assurance_runs(suite_id, status, updated_at DESC);

CREATE TABLE assurance_scenarios (
    scenario_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    safety_class TEXT NOT NULL CHECK (safety_class IN ('PASSIVE', 'SAFE_ACTIVE', 'CONTROLLED_MUTATION', 'DESTRUCTIVE_QUALIFICATION')),
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'PARTIAL', 'BLOCKED')),
    expected_invariant TEXT NOT NULL,
    observed_evidence TEXT NOT NULL DEFAULT '',
    stride_json TEXT NOT NULL DEFAULT '[]',
    owasp_json TEXT NOT NULL DEFAULT '[]',
    attack_paths_json TEXT NOT NULL DEFAULT '[]',
    controls_json TEXT NOT NULL DEFAULT '[]',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    failure_code TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (run_id) REFERENCES assurance_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, scenario_id)
);

CREATE INDEX idx_assurance_scenarios_status
    ON assurance_scenarios(run_id, status, scenario_id);

CREATE TABLE assurance_tool_results (
    tool_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'PARTIAL', 'BLOCKED', 'DEFERRED', 'MISSING', 'NOT_RUN')),
    tool_version TEXT,
    native_status TEXT,
    resource_class TEXT,
    execution_owner TEXT NOT NULL DEFAULT 'worker',
    finding_count INTEGER NOT NULL DEFAULT 0 CHECK (finding_count >= 0),
    duration_ms INTEGER,
    failure_code TEXT,
    evidence_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES assurance_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, tool_id)
);

CREATE INDEX idx_assurance_tool_results_run
    ON assurance_tool_results(run_id, status, tool_id);

CREATE TABLE assurance_findings (
    finding_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    stable_key TEXT NOT NULL,
    suite TEXT NOT NULL,
    scenario_id TEXT,
    tool TEXT NOT NULL,
    tool_version TEXT,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low', 'unknown')),
    title TEXT NOT NULL,
    safe_summary TEXT NOT NULL DEFAULT '',
    component TEXT NOT NULL DEFAULT '',
    asset TEXT NOT NULL DEFAULT '',
    trust_boundary TEXT NOT NULL DEFAULT '',
    stride_json TEXT NOT NULL DEFAULT '[]',
    owasp_json TEXT NOT NULL DEFAULT '[]',
    attack_paths_json TEXT NOT NULL DEFAULT '[]',
    controls_json TEXT NOT NULL DEFAULT '[]',
    cwe_json TEXT NOT NULL DEFAULT '[]',
    cve_json TEXT NOT NULL DEFAULT '[]',
    sanitized_file_reference TEXT,
    runtime_target TEXT NOT NULL DEFAULT 'local_server_host_only',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    baseline_state TEXT NOT NULL CHECK (baseline_state IN ('NEW', 'EXISTING', 'RESOLVED', 'REGRESSED', 'UNCHANGED')),
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'review', 'blocked')),
    remediation TEXT NOT NULL DEFAULT '',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (run_id) REFERENCES assurance_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_assurance_findings_run_severity
    ON assurance_findings(run_id, severity, baseline_state);

CREATE INDEX idx_assurance_findings_stable_key
    ON assurance_findings(stable_key, last_seen_at DESC);

CREATE INDEX idx_assurance_findings_scenario
    ON assurance_findings(run_id, scenario_id, tool);
