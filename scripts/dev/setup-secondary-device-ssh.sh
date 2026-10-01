#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Configure a stable SSH alias from the Pocket Lab Dev PC (WSL/Linux) to a
secondary Android/Termux test device.

Usage:
  bash scripts/dev/setup-secondary-device-ssh.sh \
    --host <tailnet-hostname-or-ip> \
    --user <termux-user> \
    [--alias pocketlab-secondary] \
    [--port 8022] \
    [--identity-file ~/.ssh/id_ed25519]

Example:
  bash scripts/dev/setup-secondary-device-ssh.sh \
    --host secondary-phone8-test.example-tailnet.ts.net \
    --user u0_a123

Then connect with:
  ssh pocketlab-secondary

Notes:
  - Prefer a Tailscale MagicDNS name or Tailnet IPv4. Do not commit it.
  - Termux OpenSSH commonly listens on port 8022; override --port if needed.
  - This script updates only the local Dev-PC SSH config.
  - It never copies private keys and never writes Pocket Lab backend secrets.
EOF
}

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

info() {
  printf '[INFO] %s\n' "$*"
}

ok() {
  printf '[OK] %s\n' "$*"
}

alias_name="pocketlab-secondary"
host_name=""
remote_user=""
port="8022"
identity_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alias)
      [[ $# -ge 2 ]] || fail "--alias requires a value"
      alias_name="$2"
      shift 2
      ;;
    --host)
      [[ $# -ge 2 ]] || fail "--host requires a value"
      host_name="$2"
      shift 2
      ;;
    --user)
      [[ $# -ge 2 ]] || fail "--user requires a value"
      remote_user="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || fail "--port requires a value"
      port="$2"
      shift 2
      ;;
    --identity-file)
      [[ $# -ge 2 ]] || fail "--identity-file requires a value"
      identity_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$host_name" ]] || fail "--host is required"
[[ -n "$remote_user" ]] || fail "--user is required"
[[ "$alias_name" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Alias contains unsupported characters"
[[ "$host_name" =~ ^[A-Za-z0-9._:-]+$ ]] || fail "Host contains unsupported characters"
[[ "$remote_user" =~ ^[A-Za-z0-9._-]+$ ]] || fail "User contains unsupported characters"
[[ "$port" =~ ^[0-9]+$ ]] || fail "Port must be numeric"
(( port >= 1 && port <= 65535 )) || fail "Port must be between 1 and 65535"

ssh_dir="\${HOME}/.ssh"
ssh_config="\${ssh_dir}/config"
start_marker="# >>> pocket-lab-lite:\${alias_name} >>>"
end_marker="# <<< pocket-lab-lite:\${alias_name} <<<"

mkdir -p "$ssh_dir"
chmod 700 "$ssh_dir"
touch "$ssh_config"
chmod 600 "$ssh_config"

if [[ -n "$identity_file" ]]; then
  if [[ "$identity_file" == "~/"* ]]; then
    identity_file="\${HOME}/\${identity_file#~/}"
  fi
  [[ -f "$identity_file" ]] || fail "Identity file does not exist: $identity_file"
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp" "\${tmp}.new"' EXIT

awk -v start="$start_marker" -v end="$end_marker" '
  $0 == start { skip=1; next }
  $0 == end   { skip=0; next }
  !skip       { print }
' "$ssh_config" > "$tmp"

{
  cat "$tmp"
  [[ ! -s "$tmp" ]] || printf '\n'
  printf '%s\n' "$start_marker"
  printf 'Host %s\n' "$alias_name"
  printf '  HostName %s\n' "$host_name"
  printf '  User %s\n' "$remote_user"
  printf '  Port %s\n' "$port"
  printf '  ServerAliveInterval 30\n'
  printf '  ServerAliveCountMax 3\n'
  printf '  TCPKeepAlive yes\n'
  printf '  IdentitiesOnly yes\n'
  if [[ -n "$identity_file" ]]; then
    printf '  IdentityFile %s\n' "$identity_file"
  fi
  printf '%s\n' "$end_marker"
} > "\${tmp}.new"

backup="\${ssh_config}.pocketlab-backup"
cp "$ssh_config" "$backup"
mv "\${tmp}.new" "$ssh_config"
chmod 600 "$ssh_config"

info "SSH alias written to $ssh_config"
info "Previous config backed up to $backup"

if command -v ssh >/dev/null 2>&1; then
  if ssh -G "$alias_name" >/dev/null 2>&1; then
    ok "SSH configuration parses for alias: $alias_name"
  else
    cp "$backup" "$ssh_config"
    chmod 600 "$ssh_config"
    fail "SSH rejected the generated config; restored $backup"
  fi
else
  info "ssh client not found; install openssh-client before connecting."
fi

printf '\nConnect from the Dev PC with:\n  ssh %s\n' "$alias_name"
printf '\nOptional connectivity check (does not alter Pocket Lab state):\n'
printf '  ssh -o BatchMode=yes -o ConnectTimeout=8 %s true\n' "$alias_name"
