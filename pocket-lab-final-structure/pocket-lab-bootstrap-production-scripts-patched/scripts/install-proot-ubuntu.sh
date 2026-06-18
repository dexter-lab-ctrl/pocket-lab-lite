#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
UBUNTU_NAME="${UBUNTU_NAME:-ubuntu}"

main() {
  SCRIPT_NAME="install-proot-ubuntu.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd proot-distro
  if proot-distro login "$UBUNTU_NAME" -- true >/dev/null 2>&1; then
    log INFO "PRoot distro already installed and login-ready: $UBUNTU_NAME"
  else
    log INFO "Installing PRoot distro: $UBUNTU_NAME"
    proot-distro install "$UBUNTU_NAME"
  fi

  log INFO "Ensuring Ansible/tooling inside PRoot Ubuntu"
  proot-distro login "$UBUNTU_NAME" -- bash -lc '
    set -Eeuo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ansible python3 python3-pip python3-venv python3-yaml openssh-client sshpass curl jq git ca-certificates gnupg lsb-release rsync unzip tar gzip
    python3 -m pip install --break-system-packages --no-cache-dir --upgrade pip >/dev/null 2>&1 || python3 -m pip install --no-cache-dir --upgrade pip >/dev/null 2>&1 || true
    python3 -m pip install --break-system-packages --no-cache-dir jmespath netaddr >/dev/null 2>&1 || python3 -m pip install --no-cache-dir jmespath netaddr >/dev/null 2>&1 || true
  '

  proot-distro login "$UBUNTU_NAME" -- true >/dev/null 2>&1 || die "PRoot Ubuntu login validation failed: $UBUNTU_NAME"

  ensure_dir_perm "$PREFIX/bin" 755
  cat > "$PREFIX/bin/ansible" <<EOF
#!/usr/bin/env bash
exec proot-distro login ${UBUNTU_NAME} -- ansible "\$@"
EOF
  chmod +x "$PREFIX/bin/ansible"
  cat > "$PREFIX/bin/ansible-playbook" <<EOF
#!/usr/bin/env bash
exec proot-distro login ${UBUNTU_NAME} -- ansible-playbook "\$@"
EOF
  chmod +x "$PREFIX/bin/ansible-playbook"
  mark_done proot_ubuntu_ready
  log INFO "PRoot Ubuntu guest OS and wrappers are ready"
}
main "$@"
