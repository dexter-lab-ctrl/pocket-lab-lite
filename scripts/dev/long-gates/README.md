# Pocket Lab Lite Phase 5 long-duration gates

This directory is the extension surface for resumable Phase 5 production gates.
Group 1 owns run identity, locking, atomic checkpoints, baselines, sanitization,
checksums, and final aggregation. Group 2 adds three non-disruptive gates through
that same framework:

```text
idle
repeated-scans
progress-soak
```

Later disruptive or pressure-oriented gates remain registered as unavailable.

## Architecture and safety boundary

Gate scripts are external server-side validation tooling. They do not add frontend
execution, do not connect the frontend to NATS, do not restart production services,
and do not inject faults. Security lifecycle truth remains in SQLite; compatibility
JSON remains derived. Quick scans are submitted only through FastAPI and remain
worker-owned.

## Registration contract

Each registry row in
`scripts/dev/check-lite-long-duration-gates-server-phone.sh` contains:

```text
gate name | script path | risk | implemented | resume | description | defaults | capabilities
```

A gate must:

1. live in this directory;
2. use the shared `long_gate_stage_*` checkpoint helpers;
3. write sanitized evidence below `$LONG_GATE_RUN_DIR/gates/<gate-id>/`;
4. preserve a gate-local atomic state file for safe resume;
5. return nonzero with a non-empty sanitized failure reason on failure;
6. never claim later Phase 5 gates are complete;
7. avoid hardcoded `/tmp`, private media, raw environments, and secret-bearing output;
8. use bounded timeouts, bounded evidence, and calm sampling defaults.

## Implemented Group 2 gates

### Idle stability

Production defaults are 24 hours, 60-second light samples, 3600-second heavy
checks, and a 900-second warm-up exclusion. Light samples collect compact HTTP,
PM2, resource, and lifecycle state. Heavy checks run SQLite health/parity,
scanner inventory, and log/evidence sizing. Resource budgets use stable-window
medians so transient spikes do not fail the gate.

### Repeated Quick scans

Quick scans run sequentially through `/api/lite/security/check`. A new scan is not
submitted until the previous run is terminal, its active key is cleared, scanner
processes are gone, and post-run checks complete. Resume inspects the existing
logical submission and tracked SQLite run before deciding to monitor or finalize;
an ambiguous submission is never retried automatically.

### Active Progress soak

A real Quick scan is observed through paired direct FastAPI and Caddy Progress
reads. The sampler is implemented in Python to avoid spawning curl for every
500 ms pair. It records p50/p95/max latency, projection age, monotonic progress,
ETag/304 behavior, bounded direct/proxy races, read degradation, and compact
resource diagnostics. Sampling below 200 ms is refused.

## Shared helper API

Gate scripts sourced by the orchestrator can call:

```text
long_gate_stage_begin <gate> <stage> [resume-safe]
long_gate_stage_pass <gate> <stage> [evidence-refs]
long_gate_stage_fail <gate> <stage> <reason> [retryable] [resume-safe]
long_gate_resume_stage_status <gate> <stage>
long_gate_gate_failure_reason <gate>
long_gate_proxy_base_url
long_gate_direct_base_url
```

Structured Group 2 sampling and analysis lives in:

```text
scripts/dev/lib/long_gate_group2.py
```

The Group 1 orchestrator remains the only run coordinator.

## Short qualification

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate idle \
  --duration-seconds 600 \
  --sample-interval-seconds 10 \
  --heavy-check-interval-seconds 120 \
  --warmup-seconds 60

bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate repeated-scans \
  --count 2 \
  --cooldown-seconds 5

bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate progress-soak \
  --scan-count 1 \
  --sample-interval-ms 500
```

## Lock and interruption recovery

The Group 1 atomic lock prevents two samplers from using one run. After terminating
only the validation shell and confirming no prior validation process remains, resume
with the same run ID:

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --resume \
  --run-id <run-id> \
  --gate <same-gate>
```

Use `--recover-stale-lock` only after reviewing the preserved lock metadata and
confirming the old validation PID is gone. A tracked scan is monitored or finalized;
it is not blindly resubmitted.

## Framework self-test

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --framework-self-test \
  --report-dir "${TMPDIR:-$HOME/.cache}/pocketlab-long-gates-test"
```

The self-test result is `framework_validated`, not Phase 5 ready.

## Group 3 — controlled disruption and recovery

Group 3 adds three explicitly disruptive, resumable gates:

```text
submission-recovery
nats-restart
worker-restart
```

They never run through `--all` unless `--allow-disruptive` is also present.
Explicit gate selection also requires `--allow-disruptive`. Dry-run prints the
planned precise process action without creating evidence or changing services.

The submission gate uses a short-lived, owner-only activation file and a random
loopback request token. Normal UI requests cannot activate the delay. The file
is removed in `finally` cleanup and on resume ambiguity.

The NATS and worker gates use only verified PM2 process names. They never use
numeric PM2 IDs, `pm2 kill`, `restart all`, stream deletion, or JetStream purge.
Completed process actions are recorded in gate-local atomic state with
`safe_to_repeat: false`, so resume verifies current state instead of repeating a
completed disruption.

## Group 4 — storage pressure and Android lifecycle

Group 4 completes the registered Phase 5 gate set:

```text
wal-pressure
low-storage
android-resume
```

`wal-pressure` has an isolated repository-backed writer/reader stage and a
bounded live Quick-scan observation stage. Checkpoint observation uses only
`PRAGMA wal_checkpoint(PASSIVE)`. An optional final `TRUNCATE` checkpoint is off
by default and is refused until isolated writers and readers have stopped.
`VACUUM` is not used.

`low-storage` defaults to deterministic ENOSPC probes in a run-owned isolated
state directory. Failpoints are allowlisted, process-local, disabled by default,
and require an isolated root. The live scenario additionally requires
`--allow-disruptive`, `--allow-storage-pressure`, and an explicit positive
`--max-allocation-bytes`. It writes only below the run directory, preserves an
emergency reserve, enforces absolute and percentage floors, and removes the
run-owned allocation through cleanup before a recovery scan.

`android-resume` is operator-assisted and is excluded from `--all`. A short-lived
backend activation allows the existing PWA to submit only sanitized lifecycle
counters. The frontend closes SSE and fallback timers while hidden or offline,
reconciles saved state with FastAPI on resume, and does not submit a scan as a
lifecycle side effect. Missing optional Android automation degrades to bounded
operator checkpoints rather than pretending the lifecycle action occurred.

Short safe examples:

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate wal-pressure --scenario isolated --duration-seconds 300

bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate low-storage --scenario deterministic

bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --gate android-resume --scenario background-active
```

The live low-storage gate must be run last and only after its dry run displays a
safe, device-specific cap. Group 4 does not make a selected-gate `ready` result a
full Phase 5 claim; `full_phase5_ready` is true only when all nine real gates are
selected and pass with final invariants, baselines, and sanitization.
