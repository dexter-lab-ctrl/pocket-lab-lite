#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"

pocketlab_dev_scratch_die() {
  printf 'ERROR %s\n' "$*" >&2
  return 2
}

pocketlab_dev_scratch_validate_namespace() {
  local namespace="${1:-default}"
  [[ "$namespace" =~ ^[A-Za-z0-9._-]+$ ]] \
    || pocketlab_dev_scratch_die "invalid scratch namespace: $namespace"
}

pocketlab_dev_scratch_root() {
  local configured="${POCKETLAB_DEV_TMPDIR:-$REPO_ROOT/.pocketlab-dev/tmp}"
  local root

  if [[ "$configured" = /* ]]; then
    root="$configured"
  else
    root="$REPO_ROOT/$configured"
  fi

  mkdir -p "$root"
  root="$(cd "$root" && pwd -P)"
  [[ -d "$root" && -w "$root" ]] \
    || pocketlab_dev_scratch_die "scratch root is not writable: $root"
  printf '%s\n' "$root"
}

pocketlab_dev_scratch_path() {
  local namespace="${1:-default}"
  pocketlab_dev_scratch_validate_namespace "$namespace"

  local root path
  root="$(pocketlab_dev_scratch_root)"
  path="$root/$namespace"
  mkdir -p "$path"
  path="$(cd "$path" && pwd -P)"
  [[ -d "$path" && -w "$path" ]] \
    || pocketlab_dev_scratch_die "scratch namespace is not writable: $path"
  printf '%s\n' "$path"
}

pocketlab_dev_scratch_activate() {
  local namespace="${1:-default}"
  local root path
  root="$(pocketlab_dev_scratch_root)"
  path="$(pocketlab_dev_scratch_path "$namespace")"

  export POCKETLAB_DEV_TMPDIR="$root"
  export POCKETLAB_DEV_SCRATCH_NAMESPACE="$namespace"
  export TMPDIR="$path"
  export TMP="$path"
  export TEMP="$path"
}

pocketlab_dev_scratch_check() {
  local namespace="${1:-check}"
  pocketlab_dev_scratch_activate "$namespace"

  local root_fs tmp_fs
  root_fs="$(df -P "$POCKETLAB_DEV_TMPDIR" | awk 'NR==2 {print $1}')"
  tmp_fs="$(df -P "$TMPDIR" | awk 'NR==2 {print $1}')"

  [[ -n "$root_fs" && -n "$tmp_fs" ]] \
    || pocketlab_dev_scratch_die "unable to resolve scratch filesystem"
  [[ "$root_fs" == "$tmp_fs" ]] \
    || pocketlab_dev_scratch_die "scratch namespace is not on scratch-root filesystem"

  printf 'PASS Pocket Lab dev scratch root: %s\n' "$POCKETLAB_DEV_TMPDIR"
  printf 'PASS Pocket Lab dev scratch namespace: %s\n' "$TMPDIR"
  printf 'PASS Pocket Lab dev scratch filesystem: %s\n' "$tmp_fs"
}

pocketlab_dev_scratch_usage() {
  cat <<'EOF'
Usage:
  dev-scratch.sh check [namespace]
  dev-scratch.sh path [namespace]
  dev-scratch.sh run <namespace> -- <command> [args...]

Contract:
  POCKETLAB_DEV_TMPDIR
      Optional development/CI scratch-root override.
      Relative values resolve from the repository root.
      Default: <repo>/.pocketlab-dev/tmp

Namespaces:
  pytest, playwright, schemaspy, security-tools, docs, gate-<tier>, etc.

This helper is development/CI-only. It does not modify Pocket Lab runtime,
Termux state, FastAPI state, NATS/JetStream state, promoted evidence,
device identity, or release identity.
EOF
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

command="${1:-check}"
case "$command" in
  check)
    pocketlab_dev_scratch_check "${2:-check}"
    ;;
  path)
    pocketlab_dev_scratch_path "${2:-default}"
    ;;
  run)
    namespace="${2:-}"
    [[ -n "$namespace" ]] || pocketlab_dev_scratch_die "run requires a namespace"
    [[ "${3:-}" == "--" ]] || pocketlab_dev_scratch_die "run requires -- before the command"
    shift 3
    (($# > 0)) || pocketlab_dev_scratch_die "run requires a command"
    pocketlab_dev_scratch_activate "$namespace"
    exec "$@"
    ;;
  -h|--help|help)
    pocketlab_dev_scratch_usage
    ;;
  *)
    pocketlab_dev_scratch_usage >&2
    pocketlab_dev_scratch_die "unknown command: $command"
    ;;
esac
