# System Health contracts — source-authored; qualified with explicit runtime boundaries

**Qualification provenance:** Gate B continuation started at feature SHA `1ce603d5524824e11b6b47da415569452f2bc93c`; prior UI candidate SHA `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; backend-promotion candidate SHA `0b767dc662c8f7c37accb4bc5fbad71a5f31564f`; final documentation-synchronized feature SHA `613fab662f62c090f2fa7d7930315b4cb6c1e814`; base SHA `cfd4194fd338aeae07580fa7f227d118bebdd907`. The exact candidate backend, isolated schema-42→44 migration, security harness, real route contracts and narrow Android Chrome-to-candidate UI path passed on a run-owned ARM64/Termux phone runtime. Production `main` was intentionally left unchanged and remains a separate runtime identity; candidate qualification does not authorize production activation.

## Incident and freshness

Canonical incident: incident_id = hash(source + target), source, target_id, kind, state, severity, generation, recurrence_count, observation_count, first_seen_at, last_seen_at, resolved_at, evidence_revision, summary, suspected_cause and verified_cause. States: detected, diagnosing, diagnosed, repair_available, repairing, verifying, resolved, blocked, failed, manual_attention_required.

Supported status mapping: healthy/normal/online/ready/running/connected vs explicit unhealthy/critical/pressure/offline/stopped vs unknown/stale. Unknown never closes an incident. An observed healthy state may mark a problem resolved but is NOT a verified repair outcome.

UI freshness mapping is deliberately distinct: `current` may present observed health or attention; `stale`/saved snapshot data presents “Showing saved information”; `unavailable` or otherwise non-current evidence without a saved snapshot presents “System status needs confirmation”. None of these states authorize repair.

## Diagnose

POST /api/lite/system-health/incidents/{id}/diagnose requires authenticated write permission, writes sanitized diagnosis, returns observed_symptom, suspected_cause, verified_cause, cause_confidence, evidence_freshness, supporting_signals, safe_next_step, what_changes, what_does_not_change, diagnosis_id. A suspected cause is not a verified root cause.

## Preflight and repair

Risk A: existing independently owned worker/NATS/agent supervisor self-recovery; no new executor. Risk B: existing protected Apps/Devices/Recovery guided actions. Risk C: restore/data/identity operations; never automatic.

Preflight checks allowlist, expected incident generation, incident terminal state and freshness. Currently every new System Health repair is blocked by the unqualified-executor gate. Actual repair endpoint responds 409, records bounded sanitized denial and SHA256 digest of idempotency key, never raw key, with no execution or false success.

## Dependency authority

verified_runtime = persisted recent observation; verified_contract = repo-defined design relation, not live connectivity proof; inferred = potential upstream symptom relation; unknown = insufficient evidence. Optional AI provider disabled. Resource forecast states Not enough information without adequate evidence.

## Security / resource

All UI reads via same-origin FastAPI, no browser shell/NATS/secret storage, no command cache. Worker-only projection ingest; SQLite read-only prepared GET, bounded metadata and pagination. Existing authenticated policies and agent/worker/supervisor execution boundaries remain authoritative.

## Qualification assertions

- Anonymous reads are rejected by the authenticated API boundary; service and synthetic Owner qualification reads are target-bound.
- Human diagnosis writes require CSRF; expired sessions are rejected. Diagnosis is sanitized and persisted.
- Preflight is fail-closed and repair returns a recorded 409 denial because no new System Health executor is qualified. Duplicate denial requests do not execute work or claim recovery.
- GET paths are read-only prepared reads; migration 0043/0044 registration and integrity were exercised in isolated DEV-PC tests.
- Raw logs, evidence paths, secrets, command payloads and private runtime data remain outside the browser contract.

**Production-readiness boundary:** these contracts do not claim that the installed Server Phone has the PR #649 backend or that isolated candidate qualification authorizes production activation. The Android Chrome evidence is exact-SHA candidate evidence through the repository-owned loopback proxy and short-lived browser bridge, not fixture-only evidence. The repository-owned promotion workflow now covers artifact transfer, backup/restore rehearsal, schema 0043/0044 migration, atomic cutover/abort and explicit authorization. Live activation still requires a passing production admission snapshot, a verified production backup/restore receipt and separate authorization; the current phone is blocked by its absent external guardian.

## Backend promotion contract

`scripts/dev/lite/backend_runtime_promotion.py` owns the backend-runtime promotion lifecycle outside FastAPI. Its artifact contract is immutable and exact-SHA-bound: deterministic inventory, SHA256 sidecars, target `android-termux/aarch64/proot-ubuntu`, schema 44, migration checksums 0043/0044, service ownership, safe extraction and no secrets, environment files, symlinks or path traversal. The PWA `dist.zip` release contract remains unchanged.

Admission is fail-closed and read-only until the explicit cutover confirmation. It verifies the protected Server Phone identity from SQLite, current production SHA, schema/integrity/quick-check/foreign keys, storage, memory, battery, thermal state, required services, Caddy/FastAPI health, the worker-owned sanitized runtime contract and the external runtime guardian. PM2 `online` alone is not a heartbeat. At the final physical run, every check passed except `external_guardian`; the installed phone therefore remains `BLOCKED` for production activation.

Promotion uses a consistent SQLite backup, independent restore rehearsal and a 42→44 migration rehearsal. Because the `main` runtime knows only through migration 0042, code-only rollback is not assumed. The permitted recovery strategy is code-and-database restore at a known write-quiescence boundary; automatic rollback after newer writes is disabled and uncertain recovery becomes a durable manual-recovery state. Promotion and recovery use distinct short-lived single-use Ed25519 authorizations, exact receipt/preflight bindings, an exclusive lock, durable journals, atomic pointer/database transition and bounded consecutive health/convergence observations.

The physical Android/Termux qualifier at `0b767dc662c8f7c37accb4bc5fbad71a5f31564f` verified the 284-entry artifact, isolated lifecycle commit, 0043/0044 application, health-failure rollback, write-observed fail-closed behavior, replay rejection and restart reconciliation. It transferred no source into the checkout, did not touch the production database or PM2, and removed its temporary cache. A separate explicit production-promotion authorization and a verified external guardian are still required.
