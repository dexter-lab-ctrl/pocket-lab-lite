#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODE="${1:---check}"
shift || true
INCLUDE_OPTIONAL=0
OFFLINE=0
while (($#)); do
  case "$1" in
    --include-optional) INCLUDE_OPTIONAL=1 ;;
    --offline) OFFLINE=1 ;;
    *) echo "ERROR: unsupported option: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$MODE" in --plan|--check|--install-missing|--update) ;; *) echo "Usage: $0 [--plan|--check|--install-missing|--update] [--include-optional] [--offline]" >&2; exit 2;; esac

if [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == *"com.termux"* || "$(uname -o 2>/dev/null || true)" == "Android" ]]; then
  echo "ERROR: Enterprise documentation/security tooling belongs on WSL2/Ubuntu/CI; Termux remains lightweight." >&2
  exit 3
fi

security_args=()
((INCLUDE_OPTIONAL)) && security_args+=(--include-optional)
((OFFLINE)) && security_args+=(--offline)

case "$MODE" in
  --plan)
    echo "Pocket Lab Lite Documentation Platform enterprise tool plan"
    echo "- Core docs: Java 17+, Graphviz, SchemaSpy, SQLite JDBC"
    echo "- Security/supply chain: Syft, Trivy, OSV-Scanner, Grype, Gitleaks, Semgrep, ScanCode, Scorecard, Cosign"
    echo "- Optional review/services: Threat Dragon, Dependency-Track"
    echo "- Architecture assets: pinned repository-owned icon registry"
    bash "$ROOT/scripts/dev/lite/setup-documentation-security-tools.sh" --plan "${security_args[@]}"
    ;;
  --check)
    bash "$ROOT/scripts/dev/lite/setup-documentation-tools.sh" --check
    bash "$ROOT/scripts/dev/lite/setup-documentation-security-tools.sh" --check "${security_args[@]}"
    bash "$ROOT/scripts/dev/lite/setup-architecture-icons.sh" --check
    ;;
  --install-missing)
    bash "$ROOT/scripts/dev/lite/setup-documentation-tools.sh" --install-missing
    bash "$ROOT/scripts/dev/lite/setup-documentation-security-tools.sh" --install-missing "${security_args[@]}"
    bash "$ROOT/scripts/dev/lite/setup-architecture-icons.sh" --install-missing
    ;;
  --update)
    # Core docs tooling intentionally has install-missing semantics; reviewed security pins may be explicitly replaced.
    bash "$ROOT/scripts/dev/lite/setup-documentation-tools.sh" --install-missing
    bash "$ROOT/scripts/dev/lite/setup-documentation-security-tools.sh" --update "${security_args[@]}"
    bash "$ROOT/scripts/dev/lite/setup-architecture-icons.sh" --repair
    ;;
esac

echo "PASS Pocket Lab Lite enterprise documentation tool orchestration completed: $MODE"
