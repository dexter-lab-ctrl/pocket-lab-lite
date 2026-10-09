# Isolated runtime qualification lane

The isolated runtime qualification lane validates one exact Pocket Lab Lite
candidate commit in a disposable Dev-PC environment. It is a qualification
environment, not a production deployment and not a replacement for the
normal lightweight candidate runner.

The lightweight command remains available:

```bash
task lite:photo-backup:candidate CANDIDATE_SHA="$(git rev-parse HEAD)"
```

The full lane is explicitly selected:

```bash
CANDIDATE_SHA="$(git rev-parse HEAD)"
command -v nats-server
task lite:photo-backup:candidate:full CANDIDATE_SHA="$CANDIDATE_SHA"
```

The full lane exits successfully only after the candidate API, worker,
isolated NATS/JetStream broker, node agent, supervisor, HTTPS WebDAV fixture,
synthetic media transfer, owned-process recovery, NATS reconnect, WebDAV fault
retry, and cleanup have all produced the expected observations. Evidence is
written to `/tmp/pocket-lab-lite-qualification-evidence/<run-id>/` with mode
`0700`; the manifest and summary inside it are mode `0600`.

## Architecture and trust boundaries

The lane preserves the normal control flow:

```text
candidate FastAPI
    -> run-owned NATS/JetStream
    -> candidate worker
    -> candidate node agent / run-owned supervisor
    -> synthetic source and HTTPS WebDAV fixture
    -> sanitized events and prepared API reads
```

The frontend is not involved. It cannot execute shell commands, connect to
NATS, select a filesystem path, or receive qualification credentials. The
qualification controller owns the disposable resources and talks to the
candidate API over loopback HTTPS. The API remains the control plane and the
agent owns transfer execution.

The production destination adapter remains
`server-photoprism-originals`. The test destination is accepted only when all
of the following are present and valid in the child process:

- `POCKETLAB_ENVIRONMENT=qualification`;
- context version `isolated-runtime-v1`;
- a 24-character run identity and explicit 40-character candidate SHA;
- a run-bound context token and synthetic WebDAV credential;
- a writable destination below the run root with no symlink escape; and
- an HTTPS loopback WebDAV origin with an explicit port.

Any partial or malformed context fails closed. Normal production startup does
not accept the qualification destination binding and retains its existing
origin, credential, adapter, and placement behavior.

## Candidate provenance and lifecycle

Every full run:

1. verifies a clean authorized repository origin and explicit commit SHA;
2. creates a detached temporary Git worktree and verifies its `HEAD`;
3. creates a restrictive run root, state/database roots, synthetic media, a
   local test CA, and a loopback server certificate;
4. scrubs production NATS, cloud, release, and state environment variables;
5. starts the disposable broker, HTTPS WebDAV fixture, candidate FastAPI,
   candidate worker, and candidate supervisor;
6. bootstraps the repository-owned signed synthetic-principal harness;
7. waits for a stable run-scoped agent heartbeat and source-storage capability;
8. starts the real Photo Backup admission and transfer path;
9. crashes and restarts owned API, worker, and agent processes, restarts the
   owned broker, and injects one WebDAV `503` fault; and
10. writes sanitized evidence, stops only owned processes, removes the
    temporary worktree and run root, and records cleanup results.

The API, worker, node agent, and supervisor are all started from the same
candidate worktree. The manifest records the candidate SHA for each component
and process-level ownership/source-tree observations. A process name alone is
never sufficient for cleanup: the controller checks the run environment
marker, `/proc` start time, process group, and candidate worktree.

## NATS and JetStream isolation

The broker is a real `nats-server` process with JetStream enabled. It binds
only to a dynamically selected loopback client port and a loopback monitor
port. Its credentials, config, server name, subjects, stream storage, and
consumer state are run-scoped. The qualification broker uses bounded 16 MiB
stream limits inside a 128 MiB file-store budget; production stream defaults
are unchanged.

The candidate continues to use its normal production subject conventions, but
only against the run-owned broker. This tests the production message path
without allowing a candidate subscription to reach production NATS. The full
lane observes the command, event, and audit streams, then stops and restarts
the broker and requires an agent heartbeat after reconnect. No production NATS
credential is inherited or reused.

CI installs the pinned `nats-server` release used by the lane and verifies its
SHA-256 before running the full task. A missing broker is a blocked/failed
qualification prerequisite; the controller never falls back to a production
NATS endpoint.

## WebDAV fixture and synthetic media

The fixture is an HTTPS FastAPI WebDAV server bound to loopback. Its private
CA is trusted only through the run environment (`SSL_CERT_FILE`); the Android
or host system CA store is never changed. Basic authentication is synthetic,
short-lived, and scoped to the run. The fixture exposes a controller-only
fault endpoint; the control token is never written to evidence.

The generated source contains deterministic JPEG, PNG, MP4, Unicode,
duplicate-name, case-collision, hidden, `.nomedia`, and symlink cases. The
agent's normal inventory and transfer implementation remains responsible for
excluding unsafe source entries, planning capacity, checkpointing, staging,
finalizing, and revoking credentials. The destination is below the run root;
it is not a PhotoPrism originals path and cannot be configured as an ordinary
production destination.

The fixture supports bounded `401`, `403`, `404`, `409`, `429`, `500`, `503`,
connection/finalization and delayed-response fault classes through its
run-owned controller state. The full lane currently executes the `503` retry
scenario. Other fault classes are available for focused extensions and are
not represented as passed evidence unless a scenario actually runs.

Remote WebDAV does not provide a trusted checksum in this fixture. Therefore
the successful transfer is reported honestly as `size_only`; it is not a
cryptographic remote-integrity PASS. A future trusted-hash fixture or bounded
authorized read-back scenario must produce separate evidence before changing
that classification.

## Destination contract and identity

The test binding reuses the versioned `server-photoprism-originals`
destination contract, immutable placement, node binding, backup binding,
volume/namespace identity, transport, scoped credential, capacity, and reserve
checks. It does not add arbitrary user URLs or filesystem paths to the normal
control plane.

The full lane exercises a rejected untrusted destination ID before starting a
transfer. Destination identity enrollment and mismatch behavior are covered
by the isolated context and existing destination-identity unit contracts; no
production volume is enrolled or rebound by this lane.

## Synthetic authentication

Authentication uses the existing signed challenge, public-key bootstrap,
short-lived session, capability profile, audit path, and revocation behavior.
The full lane uses the non-destructive `security-assurance-runner` synthetic
profile. It does not enable the ordinary test-auth bypass and does not
impersonate a human Owner. Credential values, private keys, session tokens,
passwords, and internal credential references are excluded from evidence.

Qualification credentials use a bounded TTL (120 seconds by default in the
controller), are scoped to the synthetic node/backup/destination, and are
revoked or deleted at terminal transfer handling. Incorrect destination or
node bindings fail closed.

## Fault injection and recovery

Fault actions are controller-owned and bounded:

- API process crash followed by exact-command restart;
- worker process crash followed by exact-command restart;
- agent process-group kill after start-time and run-marker verification;
- supervisor-owned agent recovery;
- isolated NATS stop/start and agent reconnect;
- one WebDAV `PUT` `503` response and retry; and
- destination authorization rejection before transfer.

The controller never uses `pm2 restart all`, broad process-name matching,
unscoped `kill`, or a production PM2 home. Every cleanup or fault operation
checks the run-owned PM2 state, process marker, and PID start time immediately
before acting. A stale PID or missing ownership proof is a hard stop.

## Resource and low-power policy

The Dev-PC run uses bounded readiness and subprocess timeouts, loopback-only
ports, a 128 MiB JetStream file-store cap, 16 MiB per-stream limits, limited
synthetic media, one WebDAV fixture, one worker, one supervisor, and one
synthetic agent. Temporary files, ledgers, configs, logs, and evidence live
under the run root. The controller does not install packages or change host
services.

Physical Android resource limits and battery/thermal thresholds are not
invented by this lane. Physical execution is blocked unless a separately
authorized private transport, isolated broker, isolated WebDAV destination,
temporary state root, and sufficient resource headroom are proven.

## Evidence and result classes

The machine-readable `qualification-manifest.json` contains the repository,
candidate SHA, run ID, mode, host platform, component SHA bindings, endpoint
classes, preflight results, authentication profile, scenario outcomes,
process provenance, and cleanup. The human summary contains only the run
status, candidate SHA, and run ID.

Evidence is classified separately as:

- `DEV-PC CANDIDATE` — this full disposable lane;
- `ISOLATED NATS` — broker and JetStream observations inside the run;
- `ISOLATED WEBDAV` — synthetic destination observations;
- `PHYSICAL ANDROID CANDIDATE` — only if a separately authorized physical
  lane actually executes;
- `PRODUCTION READ-ONLY OBSERVATION` — baseline observations only; and
- `NOT QUALIFIED` — no evidence of candidate execution.

The manifest is sanitized and does not contain tokens, passwords, private
keys, real media paths, personal filenames, device fingerprints, or private
network configuration.

## Android model and current limitation

The available Android command is intentionally read-only:

```bash
task lite:photo-backup:candidate:android-preflight CANDIDATE_SHA="$(git rev-parse HEAD)"
```

It records bounded source-checkout, architecture, PM2 count, storage,
listener-count, Tailscale-state, and best-effort PhotoPrism-health
observations for `pocketlab-termux` and `pocketlab-secondary`. It never starts
candidate code, changes PM2, starts Tailscale, changes Caddy/NATS/PhotoPrism,
installs packages, writes media, or changes production state. Its top-level
result remains `BLOCKED` because the repository does not currently have a
separately authorized private Android candidate transport and isolated remote
destination. A successful read-only baseline is not Android candidate
qualification evidence.

The secondary phone is never asked to start Tailscale. Exact SHA execution on
either physical device must remain a separately gated future operation until
the preflight can prove all candidate NATS, WebDAV, state, identity, process,
credential, and cleanup boundaries without touching production resources.

## CI integration

The `isolated-devpc-qualification` job in `.github/workflows/lite-quality.yml`
downloads and verifies the pinned NATS server, then runs the full task with
the pull request head SHA (or push SHA). It uses synthetic media and loopback
services only, uploads the sanitized evidence directory, and never requires
Android devices, Tailscale credentials, production NATS, PhotoPrism, or user
media. Physical Android qualification is not a pull-request prerequisite.

## Troubleshooting and recovery

- If the run reports that the candidate is dirty, commit or discard the local
  change through the normal authorized workflow; the controller will not
  qualify an ambiguous working tree.
- If `nats-server` is missing, install/use the pinned CI release or place the
  approved binary on `PATH`; do not point the lane at a production broker.
- If the fixture cannot start, inspect only the bounded retained manifest and
  rerun after fixing the local prerequisite. The fixture uses its own CA and
  loopback port; do not disable TLS verification globally.
- If cleanup is not all `true`, treat the run as failed. Use only the run ID
  and retained evidence to locate owned residuals; do not run broad PM2 or
  process cleanup commands.
- A `size_only` integrity result is expected for this WebDAV fixture and must
  not be upgraded to cryptographic equality by interpretation.

Rollback for this infrastructure change is a normal branch/PR revert. It does
not require a release tag, `dist.zip`, PWA deployment, phone checkout change,
production credential rotation, or media migration.

## PR #602 deferred-item matrix

| Deferred area | Current evidence | Classification |
| --- | --- | --- |
| Exact Dev-PC API and worker SHA | Full lane process and manifest provenance | PASS |
| Candidate NATS/JetStream path | Real command/event/audit streams and reconnect | PASS |
| Candidate agent/supervisor | Synthetic identity, heartbeat, owned recovery | PASS |
| Synthetic WebDAV transfer | Real HTTPS transfer; partial capacity outcome | PASS |
| Credential revocation and placement rejection | Terminal revocation plus negative destination admission | PASS |
| API/worker/agent crash recovery | Owned process crash/restart observations | PASS |
| Remote cryptographic integrity | Fixture has no trusted remote hash | NOT APPLICABLE |
| Physical Server Phone candidate | No safe isolated remote lane exists | BLOCKED |
| Physical secondary candidate | No safe isolated remote lane exists | BLOCKED |
| Cross-device Android qualification | Requires both physical candidate lanes | BLOCKED |
| Production media/process preservation | Dev-PC run targets no production services | PASS |

The matrix is evidence-bound: source implementation or a successful API-only
test does not close the NATS, WebDAV, Android, or cryptographic-integrity
rows.
