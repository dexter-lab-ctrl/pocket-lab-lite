#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOLS_ROOT="${POCKETLAB_PARITY_TOOLS_DIR:-$ROOT/.pocketlab-dev/tools/parity}"
BIN_DIR="$TOOLS_ROOT/bin"
SCHEMATHESIS_VENV="$TOOLS_ROOT/schemathesis-venv"
SCHEMATHESIS_VERSION="${POCKETLAB_SCHEMATHESIS_VERSION:-4.23.0}"
OASDIFF_VERSION="${POCKETLAB_OASDIFF_VERSION:-1.17.0}"
K6_VERSION="${POCKETLAB_K6_VERSION:-2.0.0}"
MODE="${1:---check}"

usage() {
  cat <<'EOF'
Usage: setup-parity-tools.sh --check | --install-missing | --help

Installs development-only parity tools under .pocketlab-dev/tools/parity.
It does not upgrade system Python, Node, npm, Java, Go, or repository dependencies.
EOF
}

case "$MODE" in
  --check|--install-missing) ;;
  --help|-h) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

arch_name() {
  case "$(uname -m)" in
    x86_64|amd64) printf amd64 ;;
    aarch64|arm64) printf arm64 ;;
    *) printf 'unsupported' ;;
  esac
}

require_base_tools() {
  local missing=0
  for tool in python3 curl tar sha256sum; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      printf 'MISSING base tool: %s\n' "$tool" >&2
      missing=1
    fi
  done
  ((missing == 0))
}

check_tool() {
  local name="$1" expected="$2" command_path="$3"
  if [[ ! -x "$command_path" ]]; then
    printf 'MISSING %s %s at %s\n' "$name" "$expected" "$command_path"
    return 1
  fi
  local output
  output="$({ "$command_path" --version 2>/dev/null || "$command_path" version 2>/dev/null; } | head -n 1 || true)"
  if [[ "$output" != *"$expected"* ]]; then
    printf 'MISMATCH %s expected %s; observed %s\n' "$name" "$expected" "${output:-unknown}" >&2
    return 1
  fi
  printf 'PASS %s %s available at %s\n' "$name" "$expected" "$command_path"
}

install_schemathesis() {
  python3 -m venv "$SCHEMATHESIS_VENV"
  "$SCHEMATHESIS_VENV/bin/python" -m pip install --disable-pip-version-check --no-input \
    "schemathesis==$SCHEMATHESIS_VERSION"
  if [[ -x "$SCHEMATHESIS_VENV/bin/schemathesis" ]]; then
    ln -sfn "$SCHEMATHESIS_VENV/bin/schemathesis" "$BIN_DIR/schemathesis"
  elif [[ -x "$SCHEMATHESIS_VENV/bin/st" ]]; then
    ln -sfn "$SCHEMATHESIS_VENV/bin/st" "$BIN_DIR/schemathesis"
  else
    printf 'ERROR Schemathesis CLI was not installed by the pinned package\n' >&2
    return 2
  fi
}

verify_checksum_file() {
  local archive="$1" checksums="$2"
  local archive_name
  archive_name="$(basename "$archive")"
  local expected
  expected="$(awk -v name="$archive_name" '$2==name || $2=="*"name {print $1; exit}' "$checksums")"
  [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || {
    printf 'ERROR checksum for %s was not found\n' "$archive_name" >&2
    return 2
  }
  printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
}

install_oasdiff() {
  local arch="$1" temp archive sums url
  temp="$(mktemp -d)"; trap 'rm -rf "$temp"' RETURN
  archive="$temp/oasdiff_${OASDIFF_VERSION}_linux_${arch}.tar.gz"
  sums="$temp/checksums.txt"
  url="https://github.com/oasdiff/oasdiff/releases/download/v${OASDIFF_VERSION}"
  curl -fL --retry 3 --connect-timeout 10 -o "$archive" "$url/$(basename "$archive")"
  curl -fL --retry 3 --connect-timeout 10 -o "$sums" "$url/checksums.txt"
  verify_checksum_file "$archive" "$sums"
  tar -xzf "$archive" -C "$temp"
  install -m 0755 "$temp/oasdiff" "$BIN_DIR/oasdiff"
}

install_k6() {
  local arch="$1" temp archive sums url extracted
  temp="$(mktemp -d)"; trap 'rm -rf "$temp"' RETURN
  archive="$temp/k6-v${K6_VERSION}-linux-${arch}.tar.gz"
  sums="$temp/k6-v${K6_VERSION}-checksums.txt"
  url="https://github.com/grafana/k6/releases/download/v${K6_VERSION}"
  curl -fL --retry 3 --connect-timeout 10 -o "$archive" "$url/$(basename "$archive")"
  curl -fL --retry 3 --connect-timeout 10 -o "$sums" "$url/$(basename "$sums")"
  verify_checksum_file "$archive" "$sums"
  tar -xzf "$archive" -C "$temp"
  extracted="$(find "$temp" -type f -name k6 -perm -u+x -print -quit)"
  [[ -n "$extracted" ]] || { printf 'ERROR k6 binary was not found in archive\n' >&2; return 2; }
  install -m 0755 "$extracted" "$BIN_DIR/k6"
}

mkdir -p "$BIN_DIR"
arch="$(arch_name)"
[[ "$arch" != unsupported ]] || { printf 'ERROR unsupported architecture: %s\n' "$(uname -m)" >&2; exit 2; }

missing=0
check_tool Schemathesis "$SCHEMATHESIS_VERSION" "$BIN_DIR/schemathesis" || missing=1
check_tool oasdiff "$OASDIFF_VERSION" "$BIN_DIR/oasdiff" || missing=1
check_tool k6 "$K6_VERSION" "$BIN_DIR/k6" || missing=1

if [[ "$MODE" == "--check" ]]; then
  if ((missing)); then
    printf 'Parity tools are incomplete. Run: bash scripts/dev/lite/setup-parity-tools.sh --install-missing\n' >&2
    exit 2
  fi
  exit 0
fi

require_base_tools
[[ -x "$BIN_DIR/schemathesis" ]] || install_schemathesis
[[ -x "$BIN_DIR/oasdiff" ]] || install_oasdiff "$arch"
[[ -x "$BIN_DIR/k6" ]] || install_k6 "$arch"
printf 'PASS parity tools installed locally under %s\n' "$TOOLS_ROOT"
