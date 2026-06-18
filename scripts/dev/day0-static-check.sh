#!/usr/bin/env bash
set -Eeuo pipefail
scripts="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"
[[ -d "$scripts" ]] || { echo "Missing bootstrap scripts dir: $scripts" >&2; exit 1; }
while IFS= read -r sh; do echo "bash -n $sh"; bash -n "$sh"; done < <(find "$scripts" -maxdepth 1 -type f -name "*.sh" | sort)
shellcheck "$scripts"/*.sh || true
