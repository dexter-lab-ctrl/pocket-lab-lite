-- Durable execution lease and checkpoint state for Runtime Security Assurance.
-- Bootstrap grants remain process-ephemeral; this migration stores only the
-- non-secret lifetime and progress metadata required to resume admitted work.

ALTER TABLE assurance_runs ADD COLUMN admission_key TEXT;
ALTER TABLE assurance_runs ADD COLUMN admitted_at TEXT;
ALTER TABLE assurance_runs ADD COLUMN run_deadline TEXT;
ALTER TABLE assurance_runs ADD COLUMN heartbeat_at TEXT;
ALTER TABLE assurance_runs ADD COLUMN worker_instance_id TEXT;
ALTER TABLE assurance_runs ADD COLUMN worker_operation_id TEXT;
ALTER TABLE assurance_runs ADD COLUMN current_scenario TEXT;
ALTER TABLE assurance_runs ADD COLUMN current_tool TEXT;
ALTER TABLE assurance_runs ADD COLUMN checkpoint_generation INTEGER NOT NULL DEFAULT 0 CHECK (checkpoint_generation >= 0);
ALTER TABLE assurance_runs ADD COLUMN last_event_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_event_sequence >= 0);

CREATE INDEX idx_assurance_runs_lease
    ON assurance_runs(status, run_deadline, heartbeat_at);

CREATE UNIQUE INDEX idx_assurance_runs_active_admission
    ON assurance_runs(admission_key)
    WHERE admission_key IS NOT NULL AND status IN ('QUEUED', 'RUNNING');

CREATE TABLE assurance_execution_checkpoints (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    unit_kind TEXT NOT NULL CHECK (unit_kind IN ('suite', 'scenario', 'tool')),
    unit_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'PASS', 'FAIL', 'PARTIAL', 'BLOCKED', 'SKIPPED')),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    retry_safe INTEGER NOT NULL DEFAULT 0 CHECK (retry_safe IN (0, 1)),
    resume_supported INTEGER NOT NULL DEFAULT 0 CHECK (resume_supported IN (0, 1)),
    started_at TEXT,
    completed_at TEXT,
    heartbeat_at TEXT,
    result_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES assurance_runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, unit_kind, unit_id)
);

CREATE INDEX idx_assurance_checkpoints_run_status
    ON assurance_execution_checkpoints(run_id, status, unit_kind, unit_id);
