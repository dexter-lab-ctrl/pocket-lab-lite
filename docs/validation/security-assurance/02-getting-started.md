# 2. Getting started

This procedure is for a published revision that the operator is authorized to
qualify. It is deliberately split between the DEV PC, the Server Phone, and
the approved client.

## 1. Establish the candidate

**[DEV PC]** The reviewer records the exact revision without changing `main`:

```bash
git fetch origin --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
task lite:security:assurance:tools:check
```

The exact-head rule is in [18 — release qualification](18-exact-head-release-qualification.md).

## 2. Establish the phone consumer

**[SERVER PHONE]** The phone must consume the already-published candidate
revision through the established deployment workflow. Do not edit tracked
files or create development commits on the phone. Record:

```bash
git status --short --branch
git rev-parse HEAD
pm2 status
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready

task lite:harness:status
task lite:harness:profiles
task lite:harness:verify-off
```

The three Task commands above are supported phone-side commands. They resolve
the installed Termux Python automatically and do not require a
`PYTHON=python3` override. They also do not project `.pocketlab-dev/state` into
the runtime. See [22 — Server Phone Task Runtime](22-server-phone-task-runtime.md).

`/ready` is the admission proof; PM2 `online` is only process posture.

## 3. Prepare the disposable identity

**[APPROVED CLIENT / DEV PC]** Keep the private key outside the repository:

```bash
task lite:harness:keygen KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.key
```

The command prints only the public key, fingerprint, path, and modes. The
private file must be mode `0600`; the public file may be staged for the
operator-approved phone startup path. Never print or paste private bytes.

## 4. Start explicit qualification

**[SERVER PHONE / operator]** The operator approval is the key-bound launcher
invocation. The public key file contains only one base64url Ed25519 public key:

```bash
task lite:qualification:start:key-bound \
  PRINCIPAL_ID=codex-security-assurance \
  PUBLIC_KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.pub
```

The phone wrapper removes DEV-PC scratch variables before starting the
qualification launcher. `start-qualification.sh` then explicitly sets
`POCKETLAB_ENVIRONMENT=qualification`, while `start-dashboard.sh` owns the
runtime `POCKETLAB_STATE_DIR` and OPA active-policy path. The startup output
must not show `.pocketlab-dev/state`.

For fixed non-destructive service-fault controls, the operator must explicitly
choose the separate `:faults` task. It is not part of normal startup.

## 5. Bootstrap and run

**[APPROVED CLIENT]** The bounded qualification client performs the one-use
key-bound bootstrap, obtains a normal short-lived session, renews it, tracks
continuity, and cleans up on a normal terminal result:

```bash
task lite:security:assurance:qualify
```

Use the explicit full workflow only with manual intent:

```bash
task lite:security:assurance:qualify:full
```

The client never persists `POCKETLAB_HARNESS_SESSION`. If a client process is
interrupted, use its continuity record and the [reattachment procedure](11-fault-recovery-playbook.md#client-disconnect-and-reattach),
not a second run submission.

## 6. Inspect, publish, and clean up

**[APPROVED CLIENT / DEV PC]** Use only sanitized `run_id` values returned by
the client:

```bash
task lite:security:assurance:report RUN_ID=<sanitized-run-id>
task lite:security:assurance:compare RUN_ID=<sanitized-run-id>
```

When the bound session is still authorized to read the completed normalized
report bundle, publication into the MkDocs source tree is explicit and
qualification-ID specific:

```bash
task lite:security:assurance:report:publish \
  QUALIFICATION_ID=<sanitized-run-id>

task lite:security:assurance:report:check \
  QUALIFICATION_ID=<sanitized-run-id>
```

Publication is a DEV-PC/repository workflow; do not edit tracked documentation
on the Server Phone. See [23 — Report Publication](23-report-publication.md).

Then follow [16 — cleanup and default-off](16-cleanup-default-off.md). If a
source defect is found, stop qualification and apply the documented DEV-PC
remediation loop. Never patch the phone checkout.

## What this does not do

This path does not perform destructive Recovery, user-media scanning, public
network scanning, credential attacks, or human WebAuthn/Owner ceremonies. The
coverage classification for those areas is explicit in the [human-review
playbook](19-human-review-playbook.md) and [attack-path catalog](13-stride-owasp-attack-paths.md).
