#!/usr/bin/env bash
set -Eeuo pipefail
scripts="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"
expected=(install-termux-packages install-proot-ubuntu install-binaries init-vault init-mariadb start-gitea seed-gitops-repo install-tailscale install-pwa-ui start-dashboard smoke-test)
plan="$($scripts/bootstrap.sh --list || true)"
printf '%s\n' "$plan"
for stage in "${expected[@]}"; do
  if ! grep -q "$stage" <<<"$plan"; then echo "Missing Day 0 stage in --list: $stage" >&2; exit 1; fi
done
bash "$scripts/bootstrap.sh" --dry-run
