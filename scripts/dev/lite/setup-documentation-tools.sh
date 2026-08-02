#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---check}"
case "$MODE" in
  --check|--install-missing) ;;
  *)
    echo "Usage: $0 [--check|--install-missing]" >&2
    exit 2
    ;;
esac

if [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == *"com.termux"* || "$(uname -o 2>/dev/null || true)" == "Android" ]]; then
  echo "ERROR: Documentation tooling is development-only and must not be installed in Android/Termux." >&2
  exit 3
fi

SCHEMASPY_VERSION="6.2.4"
SQLITE_JDBC_VERSION="3.46.1.0"
SCHEMASPY_SHA256="e96030a4a9700247e52199689ffab8ccf88ff72bc74161c28bf3c4f54f350e3c"
SQLITE_JDBC_SHA256="6dc7464e3803648d3ff18a7359bab6adf079fcd8495b18991f6f5edcb8ac6e3b"
SCHEMASPY_URL="https://repo.maven.apache.org/maven2/org/schemaspy/schemaspy/${SCHEMASPY_VERSION}/schemaspy-${SCHEMASPY_VERSION}-app.jar"
SQLITE_JDBC_URL="https://repo.maven.apache.org/maven2/org/xerial/sqlite-jdbc/${SQLITE_JDBC_VERSION}/sqlite-jdbc-${SQLITE_JDBC_VERSION}.jar"
CACHE_ROOT="${POCKETLAB_DOCS_TOOLS_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/pocket-lab-lite/docs-tools}"
SCHEMASPY_JAR="$CACHE_ROOT/schemaspy-${SCHEMASPY_VERSION}-app.jar"
SQLITE_JDBC_JAR="$CACHE_ROOT/sqlite-jdbc-${SQLITE_JDBC_VERSION}.jar"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_DIR="$REPO_ROOT/.pocketlab-dev"
ENV_FILE="$ENV_DIR/docs-tools.env"

is_ubuntu_family() {
  [[ -r /etc/os-release ]] || return 1
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" || "${ID_LIKE:-}" == *"ubuntu"* || "${ID_LIKE:-}" == *"debian"* ]]
}

run_apt() {
  local -a command=(apt-get "$@")
  if [[ "$(id -u)" -eq 0 ]]; then
    DEBIAN_FRONTEND=noninteractive "${command[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive "${command[@]}"
  else
    echo "ERROR: Missing system packages and neither root nor sudo is available." >&2
    return 1
  fi
}

java_major() {
  local version
  version="$(java -version 2>&1 | awk -F'"' '/version/ {print $2; exit}')"
  if [[ "$version" == 1.* ]]; then
    printf '%s\n' "$version" | cut -d. -f2
  else
    printf '%s\n' "$version" | cut -d. -f1
  fi
}

verify_file() {
  local path="$1" expected="$2"
  [[ -f "$path" ]] || return 1
  printf '%s  %s\n' "$expected" "$path" | sha256sum --check --status
}

install_system_tools_if_needed() {
  local -a packages=()
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  command -v sha256sum >/dev/null 2>&1 || packages+=(coreutils)
  command -v dot >/dev/null 2>&1 || packages+=(graphviz)
  command -v java >/dev/null 2>&1 || packages+=(openjdk-17-jre-headless)
  if ((${#packages[@]} == 0)); then
    return 0
  fi
  if [[ "$MODE" != "--install-missing" ]]; then
    echo "MISSING system tools: ${packages[*]}" >&2
    return 1
  fi
  if ! is_ubuntu_family; then
    echo "ERROR: Automatic system-package installation is supported only on Ubuntu/WSL2 or Debian-compatible development hosts." >&2
    return 1
  fi
  echo "Installing missing documentation packages only: ${packages[*]}"
  run_apt update
  run_apt install -y --no-install-recommends "${packages[@]}"
}

download_verified() {
  local url="$1" destination="$2" expected="$3" label="$4"
  if verify_file "$destination" "$expected"; then
    echo "OK $label: cached and checksum verified"
    return 0
  fi
  if [[ -e "$destination" ]]; then
    echo "Removing invalid cached $label artifact" >&2
    rm -f "$destination"
  fi
  if [[ "$MODE" != "--install-missing" ]]; then
    echo "MISSING $label: $destination" >&2
    return 1
  fi
  mkdir -p "$CACHE_ROOT"
  local temporary
  temporary="$(mktemp "$CACHE_ROOT/.download.XXXXXX")"
  echo "Downloading pinned $label"
  if ! curl --fail --location --proto '=https' --tlsv1.2 --retry 3 --output "$temporary" "$url"; then
    rm -f "$temporary"
    echo "ERROR: Download failed for $label. Existing valid cache entries are preserved." >&2
    return 1
  fi
  if ! printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check --status; then
    rm -f "$temporary"
    echo "ERROR: Checksum verification failed for $label." >&2
    return 1
  fi
  chmod 0644 "$temporary"
  mv -f "$temporary" "$destination"
  echo "OK $label: installed and checksum verified"
}

status=0
install_system_tools_if_needed || status=1

if command -v java >/dev/null 2>&1; then
  major="$(java_major || true)"
  if [[ -z "$major" || ! "$major" =~ ^[0-9]+$ || "$major" -lt 17 ]]; then
    echo "ERROR: Java 17 or newer is required; existing Java was not upgraded automatically." >&2
    status=1
  else
    echo "OK Java major version: $major"
  fi
fi

if command -v dot >/dev/null 2>&1; then
  echo "OK Graphviz: $(dot -V 2>&1)"
fi

if command -v curl >/dev/null 2>&1 && command -v sha256sum >/dev/null 2>&1; then
  download_verified "$SCHEMASPY_URL" "$SCHEMASPY_JAR" "$SCHEMASPY_SHA256" "SchemaSpy ${SCHEMASPY_VERSION}" || status=1
  download_verified "$SQLITE_JDBC_URL" "$SQLITE_JDBC_JAR" "$SQLITE_JDBC_SHA256" "SQLite JDBC ${SQLITE_JDBC_VERSION}" || status=1
fi

if [[ "$status" -eq 0 ]]; then
  mkdir -p "$ENV_DIR"
  umask 077
  cat > "$ENV_FILE.tmp" <<EOF
# Generated by scripts/dev/lite/setup-documentation-tools.sh
export POCKETLAB_SCHEMASPY_JAR="$SCHEMASPY_JAR"
export POCKETLAB_SQLITE_JDBC_JAR="$SQLITE_JDBC_JAR"
export POCKETLAB_SCHEMASPY_VERSION="$SCHEMASPY_VERSION"
export POCKETLAB_SQLITE_JDBC_VERSION="$SQLITE_JDBC_VERSION"
EOF
  mv -f "$ENV_FILE.tmp" "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
  echo "PASS documentation tools are ready"
  echo "Environment file: .pocketlab-dev/docs-tools.env"
else
  echo "FAIL documentation tools are not ready" >&2
  echo "Run: bash scripts/dev/lite/setup-documentation-tools.sh --install-missing" >&2
fi

exit "$status"
