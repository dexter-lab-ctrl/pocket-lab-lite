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
NATS_SERVER_BIN="${NATS_SERVER_BIN:-$(command -v nats-server)}"
OPA_BIN="${OPA_BIN:-$(command -v opa)}"
test -x "$NATS_SERVER_BIN"
test -x "$OPA_BIN"
task lite:photo-backup:candidate:full \
  CANDIDATE_SHA="$CANDIDATE_SHA" \
  NATS_SERVER_BIN="$NATS_SERVER_BIN" \
  OPA_BIN="$OPA_BIN"
```

The full lane exits successfully only after the candidate API, worker,
isolated NATS/JetStream broker, node agent, supervisor, HTTPS WebDAV fixture,
synthetic media transfer, owned-process recovery, NATS reconnect, WebDAV fault
retry, resource-budget sampling, and cleanup have all produced the expected
observations. Evidence is
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
lane observes the command, event, and audit streams, creates a run-unique
durable pull consumer, proves unacknowledged redelivery after client reconnect,
then stops and restarts the broker and requires an agent heartbeat after
reconnect. No production NATS credential is inherited or reused.

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
under the run root. The manifest records a point-in-time CPU, RSS,
live-process, run-root, and synthetic-destination sample against explicit
qualification-only budgets (`8` live owned processes, `256 MiB` run root,
`64 MiB` destination). The controller does not install packages or change
host services.

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

## Android modes and physical candidate lane

The available Android command is intentionally read-only:

```bash
task lite:photo-backup:candidate:android-preflight CANDIDATE_SHA="$(git rev-parse HEAD)"
```

It records bounded source-checkout, architecture, PM2 count, storage,
listener-count, Tailscale-state, and best-effort PhotoPrism-health
observations for `pocketlab-termux` and `pocketlab-secondary`. It never starts
candidate code, changes PM2, starts Tailscale, changes Caddy/NATS/PhotoPrism,
installs packages, writes media, or changes production state. Its top-level
result remains `BLOCKED` by design. A successful read-only baseline is not
Android candidate qualification evidence.

The separately authorized physical mode is opt-in and reuses the same
run-scoped identity and evidence contract:

```bash
task lite:photo-backup:candidate:android:qualify \
  CANDIDATE_SHA="$(git rev-parse HEAD)" \
  NATS_SERVER_BIN="/approved/path/to/nats-server" \
  OPA_BIN="$(command -v opa)"
```

The controller first requires a clean exact-SHA Dev-PC checkout, both SSH
aliases, Termux ARM64/Python dependencies, production PM2/listener/Git
baselines, the secondary phone's existing `rclone` and PM2, and disposable
Dev-PC `nats-server` and OPA binaries. If any prerequisite is missing it
returns `BLOCKED` before creating a phone run root or starting candidate code.

On an authorized run, the controller creates a minimal Git archive containing
only the selected runtime and candidate OPA policy, verifies a SHA-256 manifest
and no symlinks/production configuration, transfers it into a fresh
`$HOME/.pocketlab-qualification/<run-id>` root on each phone, and locks the
candidate tree read-only. No phone checkout is switched and no phone source is
edited.

Each phone receives independently owned SSH reverse forwards bound to
`127.0.0.1` for the Dev-PC NATS and HTTPS WebDAV fixture. The server phone
also receives the isolated OPA forward; a local SSH forward exposes only the
candidate API to the controller, and a secondary reverse forward exposes that
API to the secondary agent. Dynamic server-side ports are recorded from the
OpenSSH allocation evidence. The secondary phone receives the server-selected
NATS/WebDAV ports only after a bounded loopback reservation/forwarding check.
`ClearAllForwardings=no`, `GatewayPorts=no`, `ExitOnForwardFailure=yes`, and
no wildcard/public bind are mandatory. Tunnel PIDs, start ticks, mappings,
run IDs, and health are retained in sanitized evidence; tunnel loss is a
candidate-run failure.

The test CA and loopback leaf certificate include `localhost`, `127.0.0.1`,
and `::1`. The Dev-PC controller, remote Python clients, and the secondary
phone's run-owned `rclone` wrapper trust only that CA. The controller proves
untrusted-CA and hostname-mismatch rejection. Android/global trust stores are
not changed and `--no-check-certificate` is never used.

The server phone runs the exact candidate API and worker on private ports and
state; the secondary phone runs the exact candidate supervisor and PM2 agent
with a run-owned `PM2_HOME`, synthetic storage identity, and archived media
fixtures. The signed non-destructive harness and server-owned fleet-role
profile are used for one-time synthetic enrollment. The physical lane proves
real NATS/JetStream delivery/redelivery, heartbeat/capability projection,
synthetic WebDAV transfer, size/hash read-back, API/worker/agent recovery,
NATS and SSH-forward reconnection, and bounded WebDAV retry. It does not use
production NATS, Caddy, PhotoPrism, credentials, Tailscale on the secondary,
or real media.

Cleanup cancels command admission, revokes synthetic principals, stops the
candidate supervisor/agent/API/worker, deletes only the run-owned PM2 name,
stops the run's SSH forwards and Dev-PC services, compares both production
baselines, removes only the two run roots, and removes the local temporary
root. Incomplete cleanup or production drift is `FAIL`; missing safe
preconditions are `BLOCKED`. Resource defaults are explicit and conservative:
256 MiB per run root, 1 MiB fixture archive, eight owned processes, 32 MiB
minimum free space, three transport retries, and a 20-minute run limit.

Physical Android evidence is not substituted by a mock or read-only
observation. The final manifest records separate Server Phone, secondary
phone, transport, TLS, NATS/JetStream, WebDAV, recovery, resource,
production-preservation, and cleanup statuses.

The secondary phone is never asked to start Tailscale. Exact SHA execution on
either physical device remains gated by this explicit command and its
fail-closed preflight; the read-only command remains the safe default.

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
- If `nats-server` or `opa` is missing, install/use the pinned CI releases or
  pass their approved executable paths through `NATS_SERVER_BIN` and `OPA_BIN`;
  do not point the lane at a production broker or policy endpoint.
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
| Candidate NATS/JetStream path | Real command/event/audit streams, durable redelivery, and reconnect | PASS |
| Candidate agent/supervisor | Synthetic identity, heartbeat, owned recovery | PASS |
| Synthetic WebDAV transfer | Real HTTPS transfer; partial capacity outcome | PASS |
| Credential revocation and placement rejection | Terminal revocation plus negative destination admission | PASS |
| API/worker/agent crash recovery | Owned process crash/restart observations | PASS |
| Remote cryptographic integrity | Fixture has no trusted remote hash | NOT APPLICABLE |
| Physical Server Phone candidate | No safe isolated remote lane exists | BLOCKED |
| Physical secondary candidate | No safe isolated remote lane exists | BLOCKED |
| Cross-device Android qualification | Requires both physical candidate lanes | BLOCKED |
| Production media/process preservation | Dev-PC run targets no production services | NOT APPLICABLE |

The matrix is evidence-bound: source implementation or a successful API-only
test does not close the NATS, WebDAV, Android, or cryptographic-integrity
rows.
