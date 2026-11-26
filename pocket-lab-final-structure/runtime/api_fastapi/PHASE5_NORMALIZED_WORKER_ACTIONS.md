# Phase 5 Normalized Worker Actions

This archive has removed the legacy `retired update compatibility endpoint` compatibility endpoint and its `retired compatibility intent field` payload field. Frontend, scripts, and external automation must use typed operation requests through `POST /api/operations/execute` or typed domain command routes.

Examples:

- Supported release/source sync: `operation=git_sync`
- Blueprint deploy: `operation=deploy_blueprint`
- Drift scan: `operation=drift_scan`
- Fleet join: `operation=fleet_join`
- Policy deployment: `operation=policy_deploy`

`rotate_secret` and `secret_read_dynamic` are retired compatibility names. They
return a deterministic `410` rejection with `accepted=false` and
`executed=false`; they cannot reach generic operation dispatch, domain command
handlers, or the worker.

All write paths require FastAPI + NATS/JetStream + worker execution in production mode.
