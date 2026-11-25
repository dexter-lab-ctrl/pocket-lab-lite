#!/usr/bin/env bash
set -Eeuo pipefail
scripts="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"
expected=(install-termux-packages install-proot-ubuntu install-binaries install-tailscale install-pwa-ui start-dashboard install-fleet-agent smoke-test install-boot-recovery)
plan="$($scripts/bootstrap.sh --list || true)"
printf '%s\n' "$plan"
for stage in "${expected[@]}"; do
  if ! grep -q "$stage" <<<"$plan"; then echo "Missing Day 0 stage in --list: $stage" >&2; exit 1; fi
done
bash "$scripts/bootstrap.sh" --dry-run
