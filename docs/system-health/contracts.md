# System Health contracts — source-authored; unvalidated

## Incident and freshness

Canonical incident: incident_id = hash(source + target), source, target_id, kind, state, severity, generation, recurrence_count, observation_count, first_seen_at, last_seen_at, resolved_at, evidence_revision, summary, suspected_cause and verified_cause. States: detected, diagnosing, diagnosed, repair_available, repairing, verifying, resolved, blocked, failed, manual_attention_required.

Supported status mapping: healthy/normal/online/ready/running/connected vs explicit unhealthy/critical/pressure/offline/stopped vs unknown/stale. Unknown never closes an incident. An observed healthy state may mark a problem resolved but is NOT a verified repair outcome.

## Diagnose

POST /api/lite/system-health/incidents/{id}/diagnose requires authenticated write permission, writes sanitized diagnosis, returns observed_symptom, suspected_cause, verified_cause, cause_confidence, evidence_freshness, supporting_signals, safe_next_step, what_changes, what_does_not_change, diagnosis_id. A suspected cause is not a verified root cause.

## Preflight and repair

Risk A: existing independently owned worker/NATS/agent supervisor self-recovery; no new executor. Risk B: existing protected Apps/Devices/Recovery guided actions. Risk C: restore/data/identity operations; never automatic.

Preflight checks allowlist, expected incident generation, incident terminal state and freshness. Currently every new System Health repair is blocked by the unqualified-executor gate. Actual repair endpoint responds 409, records bounded sanitized denial and SHA256 digest of idempotency key, never raw key, with no execution or false success.

## Dependency authority

verified_runtime = persisted recent observation; verified_contract = repo-defined design relation, not live connectivity proof; inferred = potential upstream symptom relation; unknown = insufficient evidence. Optional AI provider disabled. Resource forecast states Not enough information without adequate evidence.

## Security / resource

All UI reads via same-origin FastAPI, no browser shell/NATS/secret storage, no command cache. Worker-only projection ingest; SQLite read-only prepared GET, bounded metadata and pagination. Existing authenticated policies and agent/worker/supervisor execution boundaries remain authoritative.

**All source content UNVALIDATED; no production-readiness assertion.**
