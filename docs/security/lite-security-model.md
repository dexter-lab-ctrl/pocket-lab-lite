# Lite Security Model

Pocket Lab Lite keeps the safety model of Pocket Lab while presenting it in simpler language.

Machine qualification is documented separately in [Qualification & maintenance harness](../validation/qualification-maintenance-harness.md). It is a synthetic, capability-scoped backend surface and is not projected into the Lite UI or human Identity flow.

## Preserved controls

- FastAPI remains the only frontend-facing control API.
- Write actions flow through NATS / JetStream and workers.
- Typed Operations remain the execution contract.
- Risky actions require clear confirmation.
- Restore and destructive workflows must not run silently.
- Approval, auto-approval, rejection, resume, and audit evidence remain explicit internally.

## Low-power scanner intelligence

Lite owns a bounded Trivy database lifecycle on Android/Termux. Each scan records the local database revision, update time, freshness deadline, scanner version, and scanner executable-artifact revision. A fresh database is consumed with Trivy's in-scan updater disabled so every target in the run uses the same known revision.

The default maximum stale grace is 259,200 seconds (72 hours) and is bounded to seven days. During that grace period, the unchanged local database may be used and exact-revision results may be reused, but evidence is labeled `stale_within_grace`. Once the grace expires, Lite attempts one bounded database-only refresh. A failed refresh leaves the vulnerability scan partial with `scanner_intelligence_hard_expired`; Lite does not silently scan or reuse with intelligence older than policy permits. `POCKETLAB_SECURITY_TRIVY_DB_MAX_STALE_SECONDS` can tighten the grace, and `POCKETLAB_SECURITY_TRIVY_DB_MANAGED` can explicitly select lifecycle ownership.

Java-specific, VEX, or other optional intelligence is not claimed unless its metadata is present and incorporated into the target contract. Current filesystem scans use the vulnerability database and local policy metadata exposed by the installed Trivy runtime.

## Exact target identity and reuse

Reusable scanner work is profile-independent only when an exact target contract is shared. The contract includes:

- target fingerprint and target ID;
- scanner version and executable-artifact revision;
- scanner database revision and freshness deadline;
- scanner set and secret mode;
- policy, exclusion, and scanner-configuration revisions;
- SBOM generator, format, and schema.

Quick and Full share one canonical Pocket Lab source contract. App and Full share separately fingerprinted PhotoPrism app-files, binary, and settings contracts. A settings-only change invalidates settings reuse without invalidating an unchanged binary; a binary change invalidates the binary target. Unknown identity, symbolic links, oversized identity input, dirty source, changed policy, changed scanner intelligence, or changed scanner artifact all fail closed to execution.

Reuse evidence distinguishes `executed`, `reused`, and `resumed`, including the producer run/profile and whether the reuse crossed profiles. Reuse never claims newly executed scanner or SBOM work. A cache entry is usable only when its complete compatibility identity, checkpoint, and durable run-local target evidence reference all validate; unknown, failed, partial, malformed, or incompatible provenance is a cache miss.

## Full checkpoints and resume

Full Local Check writes an atomic per-run checkpoint ledger under private Security state. Each compatible completed target records its target ID, tool, result state, evidence reference, completion time, target fingerprint, scanner and database revisions, policy and exclusion revisions, scanner configuration, and SBOM identity. Raw secrets are never checkpointed. A worker restart reopens an existing `running` or `paused_at_checkpoint` ledger for the same run instead of replacing its completed target records; terminal or malformed ledgers cannot be restarted.

The exact target cache is the restartable result store. A later Full run automatically resumes targets produced by an interrupted or resource-paused run only when the entire compatibility identity matches and the current checkpoint is structurally valid; incompatible, malformed, or unknown checkpoints execute normally. A completed resumed run promotes itself as the current provenance owner so later unchanged runs are reported as ordinary reuse. No generic resume, shell, filesystem, or Owner harness capability is introduced.

## Resource telemetry and scan budgets

The worker captures nullable backend-owned facts for available memory, free private storage, normalized system load, and—when `termux-battery-status` exists—battery percentage, charging state, and battery temperature. Unavailable values remain `null` with an unavailable source; they are never fabricated. Every budget decision carries telemetry freshness; the default maximum sample age is 30 seconds and is bounded to 15 minutes through `POCKETLAB_SECURITY_TELEMETRY_MAX_AGE_SECONDS`. Missing or stale age is handled as unknown/stale and defers the next heavy target rather than treating numeric readings as current.

Full scans evaluate a budget after durable source/runtime work and before the heavier PROot and app groups. Outcomes are `continue`, `pause_at_checkpoint`, or `partial_budget_exhausted`. A pause completes the current atomic work, preserves compatible checkpoints, marks remaining heavy targets `deferred_resource_pressure`, returns a truthful degraded result, and requires a later explicit scan to resume. There is no busy wait or hidden background continuation.

Elapsed and private-storage bounds are backend defaults. Battery, thermal, and memory thresholds are disabled unless explicitly configured for the device through `POCKETLAB_SECURITY_BATTERY_PAUSE_PERCENT`, `POCKETLAB_SECURITY_THERMAL_PAUSE_C`, and `POCKETLAB_SECURITY_MIN_MEMORY_AVAILABLE_PERCENT`. This avoids pretending that battery temperature is a universal CPU thermal limit. `POCKETLAB_SECURITY_MAX_ATOMIC_TARGETS` supports a deterministic bounded target budget and qualification scenario; the count is derived from distinct completed target/tool units, not a phase constant. Input target dependencies are backend-derived from resolved paths, and overlapping roots are executed once in deterministic plan order.

Heavy filesystem scanners remain sequential. Fingerprints and exact cache checks happen before expensive target execution, and PROot/app work follows durable source and posture phases to avoid concurrent scanner, PROot, SQLite, and evidence I/O.

## Persistence and progress

Terminal Security state, findings, evidence references, tool runs, profile snapshot, progress event, and domain revision are committed in one SQLite transaction. Findings, evidence references, and tool runs use bounded `executemany` writes. Terminal commit readback remains mandatory before compatibility JSON is projected.

Progress already coalesces exact equivalent run/fingerprint events and dirty notifications while preserving phase changes, target changes, errors, timeouts, reuse decisions, resource deferrals, and terminal states. Prepared reads use a dedicated SQLite reader, generation fencing, bounded fallback, ETags, SSE replay, and terminal snapshot reconciliation. The durable generation fence is the database instance identity, which rotates only when a different SQLite database is promoted; ordinary scan writes may advance the run id and domain revision without invalidating the prepared reader. An absent, malformed, or differently promoted database marker remains fail-closed with an explicit retryable response. Phase 2 keeps those semantics rather than adding polling retries.

Large run-specific evidence is intentionally not content-addressed in this phase. Deduplicating it safely requires retention-aware object/reference garbage collection so deleting one run cannot remove another run's evidence. Exact target-cache and shared SBOM reuse avoid repeated scanner execution while run-specific sanitized provenance remains intact.

## Current limitations

- Package-, Caddy-, NATS-, install-, repair-, restore-, and release-event scheduling remains backend future work. The combined source Trivy pass cannot be split safely without proving equivalent vulnerability, misconfiguration, and secret coverage; cheap runtime/config posture therefore continues to execute rather than being reused speculatively.
- The existing Termux Lynis profile skips only `NETW-3014`, backed by Android's restricted `/proc/net/dev`. Additional Lynis exclusions remain deferred until each test has platform evidence and replacement coverage; scan speed alone is not sufficient.
- Battery temperature is recorded as battery telemetry, not asserted as CPU temperature. Device-specific thresholds remain opt-in.
- Large immutable evidence blob deduplication remains deferred until retention and reference ownership are transactional.
- Risk/cost/age scheduling has no speculative score. Current ordering is deterministic and reuse-first; deeper prioritization requires authoritative target history and cost observations.

## Hidden by default

The lite UI should not expose:

- raw Vault tokens;
- raw secret paths;
- policy source internals;
- NATS or JetStream details;
- worker implementation details;
- backend file paths;
- raw event payloads;
- raw audit payloads.

## User-facing language

Use plain labels such as:

- Passwords & Access
- Change Password
- Protection enabled
- Requires confirmation
- Allowed actions
- Safety Check
- No critical issues
