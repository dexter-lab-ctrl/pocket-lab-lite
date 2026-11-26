#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
TRIVY_VERSION="${TRIVY_VERSION:-0.70.0}"; LYNIS_VERSION="${LYNIS_VERSION:-3.1.6}"
OPA_VERSION="${OPA_VERSION:-1.19.0}"; OPA_LINUX_ARM64_STATIC_SHA256="${OPA_LINUX_ARM64_STATIC_SHA256:-06680087ed236c8c6aaa021660d83178db829a2ad30bdb3482481fada6791b2a}"
TASK_VERSION="${TASK_VERSION:-latest}"; GO_GETTER_VERSION="${GO_GETTER_VERSION:-latest}"; ORAS_VERSION="${ORAS_VERSION:-latest}"
ARCH="${ARCH:-linux_arm64}"; STATE_BIN_DIR="${STATE_BIN_DIR:-$STATE_DIR/bin}"; CHECKSUM_DIR="${CHECKSUM_DIR:-$STATE_DIR/checksums}"

install_go_binary() {
  local cmd="$1" module="$2" version="$3"
  if have "$cmd"; then log INFO "$cmd already installed"; return 0; fi
  require_cmd go
  log INFO "Installing $cmd with go install"
  GOBIN="$PREFIX/bin" GO111MODULE=on go install "${module}@${version}"
}

install_lite_trivy() {
  if have trivy && trivy --version >/dev/null 2>&1; then log INFO "Trivy already installed and usable"; return 0; fi
  if have trivy; then
    log WARN "Existing Trivy command is not usable; reinstalling Lite-managed Trivy"
    rm -f "$PREFIX/bin/trivy"
  fi
  require_cmd go
  ensure_dir_perm "$STATE_BIN_DIR" 755
  ensure_dir_perm "$STATE_DIR/trivy-cache" 700
  log INFO "Lite profile: installing Trivy with Go into managed state bin dir"
  GOEXPERIMENT="${GOEXPERIMENT:-jsonv2}" GOBIN="$STATE_BIN_DIR" GO111MODULE=on go install "github.com/aquasecurity/trivy/cmd/trivy@v${TRIVY_VERSION}"
  [[ -x "$STATE_BIN_DIR/trivy" ]] || die "Trivy install did not produce $STATE_BIN_DIR/trivy"
  cat > "$PREFIX/bin/trivy" <<SH
#!/usr/bin/env bash
export TRIVY_CACHE_DIR="\${TRIVY_CACHE_DIR:-$STATE_DIR/trivy-cache}"
exec "$STATE_BIN_DIR/trivy" "\$@"
SH
  chmod 0755 "$PREFIX/bin/trivy"
}

install_lite_lynis() {
  if have lynis && lynis show version >/dev/null 2>&1; then log INFO "Lynis already installed and usable"; return 0; fi
  if have lynis; then
    log WARN "Existing Lynis command is not usable; reinstalling Lite-managed Lynis"
    rm -f "$PREFIX/bin/lynis"
  fi
  require_cmd curl tar
  local archive="$STATE_DIR/lynis-${LYNIS_VERSION}.tar.gz"
  local install_dir="$STATE_DIR/lynis-${LYNIS_VERSION}"
  log INFO "Lite profile: installing Lynis into managed state dir"
  download_if_missing "https://github.com/CISOfy/lynis/archive/refs/tags/${LYNIS_VERSION}.tar.gz" "$archive"
  rm -rf "$install_dir" "$STATE_DIR/lynis"
  mkdir -p "$install_dir"
  tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$install_dir" --strip-components=1
  [[ -x "$install_dir/lynis" ]] || die "Lynis install did not produce $install_dir/lynis"
  local lynis_tmp_dir="$STATE_DIR/lynis-tmp"
  ensure_dir_perm "$lynis_tmp_dir" 700
  if [[ -f "$install_dir/include/functions" ]]; then
    sed -i "s|mktemp /tmp/lynis.XXXXXXXXXX|mktemp ${lynis_tmp_dir}/lynis.XXXXXXXXXX|g" "$install_dir/include/functions"
  fi
  if [[ -f "$install_dir/default.prf" ]] && ! grep -q '^skip-test=NETW-3014$' "$install_dir/default.prf"; then
    cat >> "$install_dir/default.prf" <<'EOF'

# Pocket Lab Lite / Android Termux:
# Android restricts /proc/net/dev for the Termux app user.
# Skip Lynis network interface discovery to avoid a non-actionable platform warning.
skip-test=NETW-3014
EOF
  fi
  ln -sfn "$install_dir" "$STATE_DIR/lynis"
  cat > "$PREFIX/bin/lynis" <<SH
#!/usr/bin/env bash
set -Eeuo pipefail
export TMPDIR="\${TMPDIR:-$PREFIX/tmp}"
mkdir -p "\$TMPDIR" 2>/dev/null || true
cd "$STATE_DIR/lynis"
exec ./lynis "\$@"
SH
  chmod 0755 "$PREFIX/bin/lynis"
  rm -f "$archive"
}

install_lite_opa() {
  ensure_dir_perm "$STATE_BIN_DIR" 755
  local managed="$STATE_BIN_DIR/opa-v${OPA_VERSION}-linux-arm64-static"
  local archive="$STATE_DIR/opa-v${OPA_VERSION}-linux-arm64-static"
  if [[ -x "$managed" ]] && printf '%s  %s\n' "$OPA_LINUX_ARM64_STATIC_SHA256" "$managed" | sha256sum -c - >/dev/null 2>&1; then
    log INFO "OPA v${OPA_VERSION} already installed and checksum verified"
  else
    rm -f "$archive"
    download_if_missing "https://github.com/open-policy-agent/opa/releases/download/v${OPA_VERSION}/opa_linux_arm64_static" "$archive"
    sha256_verify "$archive" "$OPA_LINUX_ARM64_STATIC_SHA256"
    local managed_tmp="$STATE_BIN_DIR/.opa-v${OPA_VERSION}-linux-arm64-static.$$.tmp"
    rm -f "$managed_tmp"
    install -m 0755 "$archive" "$managed_tmp"
    sha256_verify "$managed_tmp" "$OPA_LINUX_ARM64_STATIC_SHA256"
    mv -f "$managed_tmp" "$managed"
    rm -f "$archive"
  fi
  cat > "$PREFIX/bin/opa" <<SH
#!/usr/bin/env bash
exec "$managed" "\$@"
SH
  chmod 0755 "$PREFIX/bin/opa"
  local opa_version_output
  opa_version_output="$(opa version 2>/dev/null)" || die "OPA installed but version check failed"
  printf '%s\n' "$opa_version_output" | grep -Eq "(^|[[:space:]])Version:[[:space:]]*${OPA_VERSION}([[:space:]]|$)" \
    || die "OPA version mismatch after install; expected ${OPA_VERSION}"
}

install_security_tools() {
  log INFO "Installing native Security tools and the local policy engine"
  install_lite_lynis
  install_lite_trivy
  install_lite_opa
  lynis show version >/dev/null 2>&1 || die "Lynis installed but version check failed"
  trivy --version >/dev/null 2>&1 || die "Trivy installed but version check failed"
  opa version >/dev/null 2>&1 || die "OPA installed but version check failed"
}
ensure_python_runtime() {
  require_cmd python3
  log INFO "Ensuring Python runtime packages"
  python3 - <<'PYCHK' || python3 -m pip install --user --upgrade --no-cache-dir dulwich ansible-runner ansible-core "fastapi<0.111" uvicorn "pydantic<2" nats-py
import importlib.util, sys
required = ("dulwich", "ansible_runner", "fastapi", "uvicorn", "pydantic", "nats")
sys.exit(0 if all(importlib.util.find_spec(m) for m in required) else 1)
PYCHK
}

main() {
  SCRIPT_NAME="install-binaries.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux
  ensure_dir_perm "$STATE_BIN_DIR" 755; ensure_dir_perm "$CHECKSUM_DIR" 700
  require_cmd curl tar sha256sum
  install_security_tools
  ensure_python_runtime
  install_go_binary nats-server github.com/nats-io/nats-server/v2 latest
  install_go_binary task github.com/go-task/task/v3/cmd/task "$TASK_VERSION"
  install_go_binary go-getter github.com/hashicorp/go-getter/cmd/go-getter "$GO_GETTER_VERSION"
  install_go_binary oras oras.land/oras/cmd/oras "$ORAS_VERSION"
  mark_done lite_security_tools_ready
  mark_done lite_opa_ready
  mark_done binaries_ready
  log INFO "Native Lite binary layer is ready and safe to rerun"
}
main "$@"
