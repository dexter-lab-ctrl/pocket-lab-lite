# Phase 5 Normalized Worker Actions

This archive has removed the legacy `retired update compatibility endpoint` compatibility endpoint and its `retired compatibility intent field` payload field. Frontend, scripts, and external automation must use typed operation requests through `POST /api/operations/execute` or typed domain command routes.

Examples:

- GitOps sync: `operation=git_sync`
- Blueprint deploy: `operation=deploy_blueprint`
- Drift scan: `operation=drift_scan`
- Fleet join: `operation=fleet_join`
- Vault rotation: `operation=rotate_secret`
- Dynamic secret read: `operation=secret_read_dynamic`
- Policy deployment: `operation=policy_deploy`

All write paths require FastAPI + NATS/JetStream + worker execution in production mode.
