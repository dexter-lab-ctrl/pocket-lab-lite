# System Health contracts — source-authored; qualified with explicit runtime boundaries

**Qualification provenance:** Gate B continuation started at feature SHA `1ce603d5524824e11b6b47da415569452f2bc93c` and final candidate SHA is `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; base SHA `cfd4194fd338aeae07580fa7f227d118bebdd907`. The exact candidate backend, isolated schema-42→44 migration, security harness, real route contracts and narrow Android Chrome-to-candidate UI path passed on a run-owned ARM64/Termux phone runtime. Production `main` was intentionally left unchanged and remains a separate runtime identity; candidate qualification does not authorize production activation.

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

**Production-readiness boundary:** these contracts do not claim that the installed Server Phone has the PR #649 backend or that isolated candidate qualification authorizes production activation. The Android Chrome evidence is exact-SHA candidate evidence through the repository-owned loopback proxy and short-lived browser bridge, not fixture-only evidence. Production promotion still requires reviewed artifact transfer, backup/restore proof for schema 0043/0044, atomic cutover/abort and explicit authorization.
