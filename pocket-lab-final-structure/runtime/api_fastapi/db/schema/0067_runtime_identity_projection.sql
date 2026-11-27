-- Independently observed runtime identity.  This is a prepared projection:
-- GET requests only validate and read it; they never probe processes or start
-- external services.
CREATE TABLE lite_runtime_identity_projection (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    status TEXT NOT NULL CHECK(status IN ('stable','transitioning','degraded','unknown')),
    reason_code TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    stale_after TEXT NOT NULL,
    coordinated_generation TEXT NOT NULL,
    authenticated_source_commit TEXT NOT NULL,
    installed_artifact_sha256 TEXT NOT NULL,
    installed_source_inventory_sha256 TEXT NOT NULL,
    fastapi_process_identity_sha256 TEXT NOT NULL,
    worker_process_identity_sha256 TEXT NOT NULL,
    core_supervisor_identity_sha256 TEXT NOT NULL,
    runtime_reconciler_identity_sha256 TEXT NOT NULL,
    loaded_policy_revision TEXT NOT NULL,
    loaded_policy_module_sha256 TEXT NOT NULL,
    loaded_policy_data_sha256 TEXT NOT NULL,
    frontend_generation TEXT NOT NULL,
    sqlite_schema_version INTEGER NOT NULL CHECK(sqlite_schema_version>0),
    sqlite_migration_ledger_sha256 TEXT NOT NULL,
    identity_sha256 TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
