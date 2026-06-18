# Day-0 bootstrap hardening notes

The scripts in `scripts/` have been hardened for Android/Termux reruns.

## Common changes

- `scripts/lib/common.sh` now provides shared helpers for:
  - Android/Termux detection with optional `POCKET_LAB_ALLOW_NON_TERMUX=1` harness mode.
  - Per-script file locks under `$STATE_DIR/locks` to prevent concurrent runs.
  - Stage markers under `$STATE_DIR/markers` for safe bootstrap reruns.
  - Atomic file writes for configs/secrets.
  - Safer downloads with retries and temporary files.
  - PM2 start-or-restart semantics.
  - TCP wait fallback through Python when `nc` is unavailable.
  - Consistent state/log/run directories.

## Script-level changes

- `bootstrap.sh` now tracks completed stages and supports `--force-stage`.
- Package installation checks existing packages before install and avoids repeating upgrades.
- PRoot Ubuntu setup is rerunnable and recreates Ansible wrappers safely.
- Binary installation skips already-installed tools and stages guest tools only when PRoot is available.
- Vault initialization refuses to overwrite existing root artifacts and safely reuses initialized/unsealed state.
- MariaDB initialization reuses existing datadirs, sockets, users, and grants.
- Gitea/act_runner use PM2 start-or-restart and idempotent repo/admin bootstrap behavior.
- GitOps seeding refreshes local IaC content safely and commits only when changes exist.
- Tailscale setup preserves installer state and supports optional `TAILSCALE_AUTHKEY`.
- PWA UI install stages downloads before replacing the active UI and backs up existing assets.
- Dashboard startup regenerates configs deterministically and restarts PM2 services safely.
- Smoke tests skip optional checks when tools are absent and report all failures together.

## Useful environment switches

- `POCKET_LAB_ALLOW_NON_TERMUX=1`: allows syntax/harness execution outside Termux.
- `POCKET_LAB_NO_NETWORK=1`: prevents downloads.
- `POCKET_LAB_SKIP_TERMUX_UPGRADE=1`: skips package upgrade during reruns.
- `TAILSCALE_AUTHKEY=...`: performs non-interactive Tailscale enrollment when supported.
