#!/usr/bin/env bash
set -Eeuo pipefail

log(){ printf '[INFO] %s\n' "$*"; }
ok(){ printf '[OK] %s\n' "$*"; }
warn(){ printf '[WARN] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

SOURCE_ROOT="${POCKETLAB_WSL_SOURCE_ROOT:-$(pwd -P)}"
TARGET_ROOT="${POCKETLAB_WSL_REPO_PATH:-$HOME/pocket-lab-lite}"
SKIP_REPO_SYNC="${POCKETLAB_WSL_SKIP_REPO_SYNC:-0}"
REPORT_PATH="${POCKETLAB_WSL_REPORT_PATH:-$TARGET_ROOT/.pocketlab-dev/reports/wsl-ubuntu-bootstrap.json}"
NODE_MAJOR="${POCKETLAB_NODE_MAJOR:-24}"
TASK_VERSION="${POCKETLAB_TASK_VERSION:-v3.50.0}"

printf '\nPocket Lab Phase 2 WSL2 Ubuntu bootstrap\n'
printf '========================================\n'

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "This script must run inside WSL2 Ubuntu/Linux."
fi

if ! grep -qi microsoft /proc/version 2>/dev/null; then
  warn "This does not look like WSL. Continuing because it is Linux, but Phase 2 targets WSL2 Ubuntu."
fi

if [[ ! -f "$SOURCE_ROOT/Taskfile.yml" ]]; then
  fail "Source root does not contain Taskfile.yml: $SOURCE_ROOT"
fi
ok "Source repo detected at $SOURCE_ROOT"

log "Installing Ubuntu apt dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential ca-certificates curl git gnupg jq lsb-release make \
  python3 python3-dev python3-pip python3-venv pipx rsync unzip wget zip \
  shellcheck yamllint
ok "Base Ubuntu packages installed"

if ! have docker; then
  warn "docker CLI is not currently available inside WSL. Attempting Docker CLI install through apt."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-plugin || true
fi

if have docker; then
  if docker version >/dev/null 2>&1; then
    ok "Docker CLI can reach Docker engine"
  else
    warn "Docker CLI exists but cannot reach Docker engine. Confirm Docker Desktop WSL integration is enabled."
  fi
else
  warn "docker CLI still not found. Phase 2 check will report this."
fi

install_task(){
  if have task; then ok "Taskfile already installed: $(task --version | head -n1)"; return 0; fi
  local arch os tmp url
  os="linux"
  case "$(uname -m)" in
    x86_64|amd64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) fail "Unsupported architecture for Taskfile install: $(uname -m)" ;;
  esac
  tmp="$(mktemp -d)"
  url="https://github.com/go-task/task/releases/download/${TASK_VERSION}/task_${os}_${arch}.tar.gz"
  log "Installing Taskfile ${TASK_VERSION} from $url"
  curl -fsSL "$url" -o "$tmp/task.tar.gz"
  tar -xzf "$tmp/task.tar.gz" -C "$tmp" task
  sudo install -m 0755 "$tmp/task" /usr/local/bin/task
  rm -rf "$tmp"
  ok "Taskfile installed: $(task --version | head -n1)"
}
install_task

install_node(){
  if have node && node --version | grep -qE "^v${NODE_MAJOR}\."; then
    ok "Node.js already matches major ${NODE_MAJOR}: $(node --version)"
    return 0
  fi
  export NVM_DIR="$HOME/.nvm"
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    log "Installing nvm for Node.js ${NODE_MAJOR}"
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  fi
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
  nvm install "$NODE_MAJOR"
  nvm alias default "$NODE_MAJOR"
  nvm use "$NODE_MAJOR"
  ok "Node.js installed: $(node --version), npm $(npm --version)"
}
install_node

# shellcheck disable=SC1091
[[ -s "$HOME/.nvm/nvm.sh" ]] && source "$HOME/.nvm/nvm.sh" && nvm use "$NODE_MAJOR" >/dev/null || true

if [[ "$SKIP_REPO_SYNC" != "1" ]]; then
  log "Syncing repository into Linux filesystem: $TARGET_ROOT"
  mkdir -p "$TARGET_ROOT"
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    --exclude 'site/' \
    --exclude '.pocketlab-dev/logs/' \
    --exclude '.pocketlab-dev/pids/' \
    --exclude 'pocketlab_*_patch_package/' \
    --exclude '*.zip' \
    "$SOURCE_ROOT/" "$TARGET_ROOT/"
  ok "Repository synced to $TARGET_ROOT"
else
  log "Repository sync skipped by request."
fi

cd "$TARGET_ROOT"
mkdir -p .pocketlab-dev/logs .pocketlab-dev/pids .pocketlab-dev/state .pocketlab-dev/reports

log "Creating Python virtual environment"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

if [[ -f requirements-dev.txt ]]; then
  log "Installing root Python dev requirements"
  python -m pip install -r requirements-dev.txt
fi
if [[ -f pocket-lab-final-structure/runtime/requirements-dev.txt ]]; then
  log "Installing runtime Python dev requirements"
  python -m pip install -r pocket-lab-final-structure/runtime/requirements-dev.txt
elif [[ -f pocket-lab-final-structure/runtime/requirements.txt ]]; then
  log "Installing runtime Python requirements"
  python -m pip install -r pocket-lab-final-structure/runtime/requirements.txt
fi
ok "Python environment ready: $(python --version)"

log "Installing Node dependencies"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
ok "Node dependencies installed"

if [[ -f package.json ]]; then
  log "Installing Playwright browser support"
  if [[ -x scripts/dev/install-playwright-browser.sh ]]; then
    bash scripts/dev/install-playwright-browser.sh || warn "Playwright browser setup reported a warning/failure. Review .pocketlab-dev/reports/playwright-browser.json."
  else
    npx playwright install --with-deps chromium || warn "Playwright browser dependency install reported a warning/failure. Re-run after reviewing apt/network output."
  fi
fi

if have docker && docker version >/dev/null 2>&1; then
  log "Pulling core development container images"
  docker pull nats:2.10-alpine || warn "Could not pull nats:2.10-alpine"
  docker pull structurizr/structurizr:latest || warn "Could not pull structurizr/structurizr:latest"
  docker pull owasp/threat-dragon:stable || warn "Could not pull owasp/threat-dragon:stable"
fi

bash scripts/dev/check-wsl-ubuntu-dev.sh || fail "WSL Ubuntu development environment check failed."

cat > "$REPORT_PATH" <<JSON
{
  "schema": "pocketlab.wslUbuntuBootstrap/v1",
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source_root": "$SOURCE_ROOT",
  "target_root": "$TARGET_ROOT",
  "node_major": "$NODE_MAJOR",
  "task_version": "$TASK_VERSION",
  "status": "OK"
}
JSON
ok "Bootstrap report written to $REPORT_PATH"
printf '\nPhase 2 WSL2 Ubuntu bootstrap completed.\n'
