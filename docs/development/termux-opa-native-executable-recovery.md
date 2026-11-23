# Termux OPA native executable recovery

Date: 2026-11-23

Status: `VALIDATED` for the Dev-PC source and test contract; physical
Server Phone deployment remains `BLOCKED` until a separately authorized
release is produced after this fix is merged.

## Incident boundary

The production Server Phone had a valid OPA v1.19.0 ARM64 payload under the
Pocket Lab managed binary directory. Its package launcher was a Bash script
with a `#!/usr/bin/env bash` shebang. Native Termux does not provide
`/usr/bin/env`, so policy preparation failed before `opa fmt`, `opa check`, or
`opa test` could run. The existing `pocket-opa` PM2 process remained online
because its prior projection launched the versioned payload directly; the
failure was in source reconciliation and policy validation.

The recovery implementation keeps the existing policy lifecycle authority,
activation lock, active/known-good pointers, readiness probe, and exact
revision proof. It adds one shared, fail-closed resolver that:

- accepts a native ELF OPA executable;
- resolves a wrapper's trusted native interpreter without executing the
  wrapper through `/usr/bin/env`;
- unwraps only a literal absolute-path `exec ... "$@"` hand-off to a trusted
  managed payload;
- launches a script wrapper with its resolved interpreter only when no literal
  native payload is available;
- rejects missing payloads, unexpected formats, path escapes, and resolution
  cycles; and
- passes a native payload to PM2 with the repository's existing
  `interpreter: "none"` contract.

OPA policy staging still requires `fmt --check-result`, `check --strict`, and
`test --fail-on-empty`. The runtime still activates a bounded revision only
under the existing lock and advances `known-good` only after loopback health
and metadata revision proof.

## Production backup authorization boundary

`POST /api/lite/recovery/database/backup` is a protected write. The supported
production paths are:

1. a real local Owner browser session, including the same-site CSRF proof for
   the write; or
2. an already-configured service API token supplied as a bearer token through
   the normal control API boundary.

The qualification-owner harness is isolated qualification infrastructure. It
is not a production authorization mechanism and must not be enabled or used
to create a production backup. Human credentials, cookies, CSRF values,
tokens, and process environments must not be copied into qualification
evidence. A production backup attempt without one of the supported proofs
must remain a truthful HTTP 401 `authentication_required` result.

## Future release and deployment strategy

This fix branch does not publish a release and does not mutate the Server
Phone. After review and merge:

1. fast-forward `main` to the merged commit and select the pinned toolchain;
2. dispatch the repository-owned `release-dist.yml` workflow from that exact
   `main` SHA with the next approved Lite tag;
3. verify the peeled tag, release manifest `source_commit`, artifact checksums,
   `dist.zip`, and release workflow conclusion before installation;
4. obtain separate production authorization, create and independently verify
   the repository-owned online SQLite backup through an authenticated Owner or
   configured service-token path;
5. fast-forward the Server Phone checkout only, install the approved release
   with `install-pwa-ui.sh`, and let the normal reconciler/guardian converge;
6. verify the native OPA executable, PM2 `interpreter: "none"` projection,
   loopback readiness, active/known-good/observed revision equality, and all
   required service health; and
7. stop and restore from recorded evidence if any identity, backup, policy,
   PM2, or readiness gate fails. A physical reboot remains a separate
   operator-owned acceptance test.

No historical database rows, PM2 PID files, sockets, lock files, or installed
package files are to be deleted or rewritten as part of this recovery.

## Qualification commands

The focused contract is covered by:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  tests/backend/test_lite_opa_bootstrap_reconciliation.py \
  tests/backend/test_opa_policy_staging.py \
  tests/backend/test_lite_pm2_version_projection.py
```

The broader repository gates remain authoritative. Physical Android and
production deployment evidence are intentionally not claimed by this branch.
