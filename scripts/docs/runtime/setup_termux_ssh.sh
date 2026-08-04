#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(CDPATH='' cd -- "$SCRIPT_DIR/../../.." && pwd)"
ALIAS_NAME="${POCKETLAB_TERMUX_SSH_ALIAS:-pocketlab-termux}"
MODE=""
DRY_RUN=0
DISCOVER=0
USE_DISCOVERED=0
ASSUME_YES=0
HOST_VALUE="${POCKETLAB_TERMUX_SSH_HOST:-}"
USER_VALUE="${POCKETLAB_TERMUX_SSH_USER:-}"
PORT_VALUE="${POCKETLAB_TERMUX_SSH_PORT:-}"
IDENTITY_VALUE="${POCKETLAB_TERMUX_SSH_IDENTITY:-}"
EXPECTED_FINGERPRINT="${POCKETLAB_TERMUX_HOST_KEY_FINGERPRINT:-}"
SSH_DIR="${HOME}/.ssh"
CONFIG_FILE="${SSH_DIR}/config"
KNOWN_HOSTS_FILE="${SSH_DIR}/known_hosts"
LOCAL_STATE_DIR="${POCKETLAB_RUNTIME_SSH_STATE_DIR:-$ROOT/.pocketlab-dev/runtime-ssh}"
BEGIN_MARKER="# BEGIN POCKET LAB LITE TERMUX RUNTIME"
END_MARKER="# END POCKET LAB LITE TERMUX RUNTIME"

usage() {
  cat <<'EOF'
Usage:
  setup_termux_ssh.sh --prepare-key [options]
  setup_termux_ssh.sh --check [options]
  setup_termux_ssh.sh --configure [options]

Options:
  --host VALUE                 Private/Tailscale host supplied by the operator
  --user VALUE                 Existing Termux SSH user
  --port VALUE                 Verified SSH port
  --identity PATH              WSL-only private key path
  --fingerprint SHA256:VALUE   Expected host-key fingerprint
  --alias VALUE                Managed local SSH alias (default: pocketlab-termux)
  --discover                   Probe an already approved connection for safe private candidates
  --use-discovered-host        Use the highest-ranked discovered host after explicit approval
  --yes                        Noninteractive confirmation for config write only
  --dry-run                    Show actions without changing local files
  --help                       Show this help

The generated public key must be authorized through an already trusted phone session
before --configure can complete. The private key never leaves WSL.
EOF
}

fail() { printf 'ERROR %s\n' "$*" >&2; exit 2; }
info() { printf '%s\n' "$*"; }

while (($#)); do
  case "$1" in
    --prepare-key) MODE="prepare-key"; shift ;;
    --check) MODE="check"; shift ;;
    --configure) MODE="configure"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --discover) DISCOVER=1; shift ;;
    --use-discovered-host) USE_DISCOVERED=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --host|--user|--port|--identity|--fingerprint|--alias)
      [[ $# -ge 2 ]] || fail "$1 requires a value"
      case "$1" in
        --host) HOST_VALUE="$2" ;;
        --user) USER_VALUE="$2" ;;
        --port) PORT_VALUE="$2" ;;
        --identity) IDENTITY_VALUE="$2" ;;
        --fingerprint) EXPECTED_FINGERPRINT="$2" ;;
        --alias) ALIAS_NAME="$2" ;;
      esac
      shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unsupported option: $1" ;;
  esac
done

[[ "$MODE" =~ ^(prepare-key|check|configure)$ ]] || { usage >&2; exit 2; }
[[ "$ALIAS_NAME" =~ ^[A-Za-z0-9._-]+$ ]] || fail "SSH alias contains unsupported characters"
[[ "$USER_VALUE" != *$'\n'* && "$HOST_VALUE" != *$'\n'* ]] || fail "connection metadata contains a newline"

require_wsl() {
  grep -qi microsoft /proc/sys/kernel/osrelease /proc/version 2>/dev/null || \
    fail "Termux runtime SSH orchestration must run from the WSL2 repository terminal"
}

require_wsl

mkdir_safe() {
  if ((DRY_RUN)); then return 0; fi
  umask 077
  mkdir -p "$1"
  chmod 700 "$1"
}

is_safe_host() {
  python3 "$SCRIPT_DIR/runtime_ssh_candidates.py" validate-host "$1"
}

extract_alias_config() {
  [[ -f "$CONFIG_FILE" ]] || return 1
  awk -v host="$ALIAS_NAME" '
    BEGIN {capture=0}
    /^[[:space:]]*Host[[:space:]]+/ {
      capture=0
      for(i=2;i<=NF;i++) if($i==host) capture=1
    }
    capture {print}
  ' "$CONFIG_FILE"
}

managed_block_present() {
  [[ -f "$CONFIG_FILE" ]] && grep -Fqx "$BEGIN_MARKER" "$CONFIG_FILE" && grep -Fqx "$END_MARKER" "$CONFIG_FILE"
}

resolve_existing() {
  command -v ssh >/dev/null 2>&1 || fail "OpenSSH client is required in WSL"
  extract_alias_config >/dev/null 2>&1 || return 0
  local expanded
  if expanded="$(ssh -G "$ALIAS_NAME" 2>/dev/null)"; then
    [[ -n "$HOST_VALUE" ]] || HOST_VALUE="$(awk '$1=="hostname"{print $2; exit}' <<<"$expanded")"
    [[ -n "$USER_VALUE" ]] || USER_VALUE="$(awk '$1=="user"{print $2; exit}' <<<"$expanded")"
    [[ -n "$PORT_VALUE" ]] || PORT_VALUE="$(awk '$1=="port"{print $2; exit}' <<<"$expanded")"
    [[ -n "$IDENTITY_VALUE" ]] || IDENTITY_VALUE="$(awk '$1=="identityfile"{print $2; exit}' <<<"$expanded" | sed "s#^~#${HOME}#")"
  fi
}

validate_managed_block() {
  [[ -f "$CONFIG_FILE" ]] || return 0
  local block
  block="$(awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0==begin {inside=1; print; next}
    inside {print}
    $0==end {inside=0}
  ' "$CONFIG_FILE")"
  [[ -n "$block" ]] || return 0
  local unsupported
  unsupported="$(awk '
    /^[[:space:]]*#/ || NF==0 {next}
    {key=tolower($1)}
    key !~ /^(host|hostname|user|port|identityfile|identitiesonly|batchmode|preferredauthentications|passwordauthentication|kbdinteractiveauthentication|stricthostkeychecking|userknownhostsfile|connecttimeout|serveraliveinterval|serveralivecountmax)$/ {print key}
  ' <<<"$block" | sort -u)"
  [[ -z "$unsupported" ]] || fail "existing managed SSH block contains unsupported directives"
}

remote_termux_check() {
  local target=(ssh -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o ConnectTimeout=8 -o ConnectionAttempts=1)
  if [[ "$1" == "alias" ]]; then
    target+=("$ALIAS_NAME")
  else
    target+=(-p "$PORT_VALUE" -i "$IDENTITY_VALUE" -o IdentitiesOnly=yes -o "UserKnownHostsFile=$KNOWN_HOSTS_FILE" "${USER_VALUE}@${HOST_VALUE}")
  fi
  "${target[@]}" 'case "${PREFIX:-}" in /data/data/com.termux/files/usr) printf TERMUX_OK;; *) exit 73;; esac' 2>/dev/null | grep -qx TERMUX_OK
}

discover_candidates() {
  local target=(ssh -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o ConnectTimeout=8 -o ConnectionAttempts=1)
  if extract_alias_config >/dev/null 2>&1; then
    target+=("$ALIAS_NAME")
  else
    target+=(-p "$PORT_VALUE" -i "$IDENTITY_VALUE" -o IdentitiesOnly=yes -o "UserKnownHostsFile=$KNOWN_HOSTS_FILE" "${USER_VALUE}@${HOST_VALUE}")
  fi
  local output
  output="$("${target[@]}" 'for c in "tailscale-cli ip -4" "tailscale ip -4" "ip -4 addr show wlan0" "ifconfig wlan0"; do sh -c "$c" 2>/dev/null || true; done' 2>/dev/null || true)"
  python3 "$SCRIPT_DIR/runtime_ssh_candidates.py" rank-candidates <<<"$output"
}

prepare_key() {
  mkdir_safe "$SSH_DIR"
  if [[ ! -f "$IDENTITY_VALUE" ]]; then
    if ((DRY_RUN)); then
      info "DRY RUN would create a WSL-only Ed25519 key"
      return 0
    fi
    ssh-keygen -q -t ed25519 -a 64 -N '' -C 'pocketlab-termux-wsl' -f "$IDENTITY_VALUE"
  fi
  [[ -f "$IDENTITY_VALUE" ]] || fail "private key could not be created"
  [[ -f "${IDENTITY_VALUE}.pub" ]] || fail "public key file is missing"
  chmod 600 "$IDENTITY_VALUE"
  chmod 644 "${IDENTITY_VALUE}.pub"
  info "PASS WSL-only Ed25519 key is ready; authorize its .pub file through the already trusted phone session"
}

resolve_existing
validate_managed_block
if [[ "$MODE" == "configure" ]] && extract_alias_config >/dev/null 2>&1 && ! managed_block_present; then
  fail "an unmanaged SSH alias with this name already exists; preserve it and choose a different --alias"
fi
IDENTITY_VALUE="${IDENTITY_VALUE:-${SSH_DIR}/pocketlab-termux-ed25519}"
[[ "$IDENTITY_VALUE" == /* ]] || IDENTITY_VALUE="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$IDENTITY_VALUE")"

if [[ "$MODE" == "prepare-key" ]]; then
  prepare_key
  exit 0
fi

if [[ "$MODE" == "check" ]]; then
  [[ -f "$CONFIG_FILE" ]] || fail "SSH config is missing"
  [[ "$(stat -c '%a' "$CONFIG_FILE")" == "600" ]] || fail "SSH config permissions must be 0600"
  managed_block_present || fail "managed SSH marker block is not configured"
  local_block="$(extract_alias_config || true)"
  [[ -n "$local_block" ]] || fail "managed SSH alias is not configured"
  grep -qiE '^[[:space:]]*BatchMode[[:space:]]+yes$' <<<"$local_block" || fail "BatchMode is not enabled"
  grep -qiE '^[[:space:]]*StrictHostKeyChecking[[:space:]]+yes$' <<<"$local_block" || fail "StrictHostKeyChecking is not enabled"
  grep -qiE '^[[:space:]]*PasswordAuthentication[[:space:]]+no$' <<<"$local_block" || fail "password authentication is not disabled"
  [[ -n "$HOST_VALUE" ]] && is_safe_host "$HOST_VALUE" || fail "configured host is not a private/Tailscale target"
  [[ -f "$IDENTITY_VALUE" ]] || fail "configured WSL private key is missing"
  [[ -f "${IDENTITY_VALUE}.pub" ]] || fail "configured WSL public key is missing"
  [[ "$(stat -c '%a' "$IDENTITY_VALUE")" == "600" ]] || fail "private key permissions must be 0600"
  public_mode="$(stat -c '%a' "${IDENTITY_VALUE}.pub")"
  [[ "$public_mode" == "600" || "$public_mode" == "644" ]] || fail "public key permissions must be 0600 or 0644"
  remote_termux_check alias || fail "SSH alias did not verify a Termux target"
  info "PASS managed WSL SSH alias is private, key-only, host-key checked, bounded, and Termux verified"
  exit 0
fi

[[ -n "$HOST_VALUE" ]] || fail "--host or POCKETLAB_TERMUX_SSH_HOST is required for initial configuration"
[[ -n "$USER_VALUE" ]] || fail "--user or POCKETLAB_TERMUX_SSH_USER is required for initial configuration"
[[ "$USER_VALUE" =~ ^[A-Za-z0-9._-]+$ ]] || fail "SSH user contains unsupported characters"
is_safe_host "$HOST_VALUE" || fail "host must be a private address or Tailscale .ts.net name"
[[ -n "$PORT_VALUE" ]] || fail "--port or POCKETLAB_TERMUX_SSH_PORT is required unless an existing alias supplies it"
[[ "$PORT_VALUE" =~ ^[0-9]+$ ]] && ((PORT_VALUE >= 1 && PORT_VALUE <= 65535)) || fail "SSH port is invalid"
mkdir_safe "$SSH_DIR"
mkdir_safe "$LOCAL_STATE_DIR/backups"
prepare_key

if ((DISCOVER)); then
  candidates="$(discover_candidates || true)"
  count="$(grep -c . <<<"$candidates" || true)"
  info "Discovery found ${count} safe private candidate(s); identities remain redacted in normal output"
  if ((USE_DISCOVERED)) && [[ -n "$candidates" ]]; then
    proposed="$(head -n1 <<<"$candidates")"
    if ((ASSUME_YES)); then
      HOST_VALUE="$proposed"
    elif [[ -t 0 ]]; then
      read -r -p "Use the highest-ranked private candidate for the managed alias? [y/N] " answer
      [[ "$answer" =~ ^[Yy]$ ]] && HOST_VALUE="$proposed"
    else
      fail "--use-discovered-host requires --yes in noninteractive mode"
    fi
  fi
fi

mkdir_safe "$SSH_DIR"
if ((DRY_RUN)); then
  tmp_keyscan="$(mktemp "${TMPDIR:-/tmp}/pocketlab-keyscan.XXXXXX")"
else
  tmp_keyscan="$(mktemp "${LOCAL_STATE_DIR}/keyscan.XXXXXX")"
fi
trap 'rm -f "$tmp_keyscan" "${tmp_keyscan}.hash"' EXIT
if ! ssh-keyscan -T 5 -p "$PORT_VALUE" "$HOST_VALUE" >"$tmp_keyscan" 2>/dev/null; then
  fail "host key could not be retrieved within the bounded timeout"
fi
[[ -s "$tmp_keyscan" ]] || fail "host key response was empty"
discovered_fingerprint="$(ssh-keygen -lf "$tmp_keyscan" -E sha256 | awk 'NR==1{print $2}')"
[[ "$discovered_fingerprint" == SHA256:* ]] || fail "host key fingerprint could not be calculated"
if [[ -n "$EXPECTED_FINGERPRINT" ]]; then
  [[ "$discovered_fingerprint" == "$EXPECTED_FINGERPRINT" ]] || fail "host key fingerprint mismatch"
elif ((ASSUME_YES)); then
  fail "noninteractive configuration requires --fingerprint"
elif [[ -t 0 ]]; then
  info "Host-key fingerprint discovered locally: ${discovered_fingerprint}"
  read -r -p "Confirm this is the already trusted Termux phone? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || fail "host key was not approved"
else
  fail "provide --fingerprint in noninteractive mode"
fi

if ((DRY_RUN)); then
  info "DRY RUN would update known_hosts and one managed SSH config block"
  exit 0
fi

if ((!ASSUME_YES)); then
  if [[ -t 0 ]]; then
    read -r -p "Write the verified managed SSH alias block to ~/.ssh/config? [y/N] " answer
    [[ "$answer" =~ ^[Yy]$ ]] || fail "managed SSH config write was not approved"
  else
    fail "noninteractive config writes require --yes"
  fi
fi

# Record only the explicitly verified key. Preserve an identical existing entry.
host_token="$HOST_VALUE"
[[ "$PORT_VALUE" == "22" ]] || host_token="[${HOST_VALUE}]:${PORT_VALUE}"
existing_key="$(ssh-keygen -F "$host_token" -f "$KNOWN_HOSTS_FILE" 2>/dev/null | grep -v '^#' || true)"
if [[ -n "$existing_key" ]]; then
  existing_fingerprints="$(printf '%s\n' "$existing_key" | ssh-keygen -lf - -E sha256 2>/dev/null | awk '{print $2}' | sort -u)"
  grep -qx "$discovered_fingerprint" <<<"$existing_fingerprints" || fail "known_hosts contains a different key for the managed target"
else
  cat "$tmp_keyscan" >>"$KNOWN_HOSTS_FILE"
  chmod 600 "$KNOWN_HOSTS_FILE"
  ssh-keygen -H -f "$KNOWN_HOSTS_FILE" >/dev/null 2>&1
  rm -f "${KNOWN_HOSTS_FILE}.old"
fi

managed_block="$(cat <<EOF
${BEGIN_MARKER}
Host ${ALIAS_NAME}
  HostName ${HOST_VALUE}
  User ${USER_VALUE}
  Port ${PORT_VALUE}
  IdentityFile ${IDENTITY_VALUE}
  IdentitiesOnly yes
  BatchMode yes
  PreferredAuthentications publickey
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  StrictHostKeyChecking yes
  UserKnownHostsFile ${KNOWN_HOSTS_FILE}
  ConnectTimeout 8
  ServerAliveInterval 15
  ServerAliveCountMax 2
${END_MARKER}
EOF
)"

current=""
[[ -f "$CONFIG_FILE" ]] && current="$(cat "$CONFIG_FILE")"
without_block="$(awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
  $0==begin {inside=1; next}
  $0==end {inside=0; next}
  !inside {print}
' <<<"$current")"
backup="${LOCAL_STATE_DIR}/backups/ssh-config.$(date -u +%Y%m%dT%H%M%SZ).bak"
[[ ! -f "$CONFIG_FILE" ]] || cp -p "$CONFIG_FILE" "$backup"
temporary="$(mktemp "${SSH_DIR}/config.XXXXXX")"
{
  printf '%s\n' "$without_block" | sed -e :a -e '/^\n*$/{$d;N;ba}'
  [[ -z "$without_block" ]] || printf '\n'
  printf '%s\n' "$managed_block"
} >"$temporary"
chmod 600 "$temporary"
mv "$temporary" "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"
remote_termux_check direct || fail "configured connection did not verify a Termux target"
info "PASS managed WSL SSH alias configured without changing the phone SSH service"
