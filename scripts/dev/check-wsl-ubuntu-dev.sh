#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_ROOT="${POCKETLAB_WSL_REPO_PATH:-$(pwd -P)}"
if [[ "$TARGET_ROOT" == '/home/$USER/pocket-lab-lite' ]]; then TARGET_ROOT="$HOME/pocket-lab-lite"; fi
REPORT_PATH="${POCKETLAB_WSL_CHECK_REPORT_PATH:-$TARGET_ROOT/.pocketlab-dev/reports/wsl-ubuntu-check.json}"
mkdir -p "$(dirname "$REPORT_PATH")"

required_failures=0
warnings=0
results=()

check_ok(){ printf '[OK] %s\n  %s\n' "$1" "$2"; results+=("{\"name\":\"$1\",\"status\":\"OK\",\"details\":\"$2\"}"); }
check_warn(){ printf '[WARN] %s\n  %s\n' "$1" "$2"; warnings=$((warnings+1)); results+=("{\"name\":\"$1\",\"status\":\"WARN\",\"details\":\"$2\"}"); }
check_fail(){ printf '[FAIL] %s\n  %s\n' "$1" "$2"; required_failures=$((required_failures+1)); results+=("{\"name\":\"$1\",\"status\":\"FAIL\",\"details\":\"$2\"}"); }
have(){ command -v "$1" >/dev/null 2>&1; }

printf '\nPocket Lab WSL2 Ubuntu development environment check\n'
printf '====================================================\n'

if [[ "$(uname -s)" == "Linux" ]]; then check_ok "Linux kernel" "$(uname -a)"; else check_fail "Linux kernel" "Not running on Linux"; fi
if grep -qi microsoft /proc/version 2>/dev/null; then check_ok "WSL kernel" "Microsoft WSL kernel detected"; else check_warn "WSL kernel" "Microsoft WSL marker not detected"; fi
if [[ -f /etc/os-release ]]; then . /etc/os-release; check_ok "Ubuntu release" "${PRETTY_NAME:-unknown}"; else check_fail "Ubuntu release" "/etc/os-release missing"; fi

if [[ -d "$TARGET_ROOT" && -f "$TARGET_ROOT/Taskfile.yml" ]]; then check_ok "Pocket Lab repo" "$TARGET_ROOT"; else check_fail "Pocket Lab repo" "Taskfile.yml not found under $TARGET_ROOT"; fi
cd "$TARGET_ROOT" 2>/dev/null || true

if [[ -x scripts/dev/check-wsl-filesystem-standard.sh ]]; then
  if bash scripts/dev/check-wsl-filesystem-standard.sh >/tmp/pocketlab-wsl-filesystem-check.out 2>&1; then
    check_ok "wsl filesystem standard" "$TARGET_ROOT"
  else
    check_fail "wsl filesystem standard" "$(tail -n 1 /tmp/pocketlab-wsl-filesystem-check.out)"
  fi
else
  check_fail "wsl filesystem standard" "scripts/dev/check-wsl-filesystem-standard.sh missing"
fi

if have python3; then check_ok "python3" "$(python3 --version)"; else check_fail "python3" "python3 not found"; fi
if [[ -x .venv/bin/python ]]; then check_ok "Python virtualenv" "$(.venv/bin/python --version)"; else check_fail "Python virtualenv" ".venv/bin/python missing"; fi

# nvm is not automatically loaded in non-interactive WSL shells launched from Windows.
# Load it explicitly so Taskfile-based Windows checks see the same Node runtime as interactive Ubuntu shells.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
  nvm use "${POCKETLAB_NODE_MAJOR:-24}" >/dev/null 2>&1 || true
fi

if have node; then check_ok "node" "$(node --version)"; else check_fail "node" "node not found"; fi
if have npm; then check_ok "npm" "$(npm --version)"; else check_fail "npm" "npm not found"; fi
if have task; then check_ok "task" "$(task --version | head -n1)"; else check_fail "task" "Taskfile CLI not found"; fi
if have docker; then
  if docker version >/dev/null 2>&1; then check_ok "docker" "$(docker version --format '{{.Server.Version}}' 2>/dev/null || docker --version)"; else check_fail "docker" "Docker CLI cannot reach engine"; fi
else check_fail "docker" "docker CLI not found"; fi
if docker compose version >/dev/null 2>&1; then check_ok "docker compose" "$(docker compose version)"; else check_warn "docker compose" "docker compose plugin unavailable"; fi

[[ -d node_modules ]] && check_ok "node_modules" "present" || check_fail "node_modules" "missing; run npm ci"
[[ -f package.json ]] && check_ok "package.json" "present" || check_fail "package.json" "missing"
[[ -f requirements-dev.txt ]] && check_ok "requirements-dev.txt" "present" || check_warn "requirements-dev.txt" "missing"
[[ -f docker-compose.dev.yml ]] && check_ok "docker-compose.dev.yml" "present" || check_fail "docker-compose.dev.yml" "missing"

if [[ -x .venv/bin/mkdocs ]] || have mkdocs; then check_ok "mkdocs" "available"; else check_warn "mkdocs" "not found in PATH; may exist after venv activation"; fi
if [[ -x .venv/bin/pytest ]] || have pytest; then check_ok "pytest" "available"; else check_warn "pytest" "not found in PATH; may exist after venv activation"; fi

PLAYWRIGHT_BROWSER_REPORT=".pocketlab-dev/reports/playwright-browser.json"
if [[ -f "$PLAYWRIGHT_BROWSER_REPORT" ]]; then
  if have jq; then
    playwright_status="$(jq -r '.status // "UNKNOWN"' "$PLAYWRIGHT_BROWSER_REPORT")"
    playwright_mode="$(jq -r '.browser_mode // "unknown"' "$PLAYWRIGHT_BROWSER_REPORT")"
    playwright_version="$(jq -r '.browser_version // "unknown"' "$PLAYWRIGHT_BROWSER_REPORT")"
    if [[ "$playwright_status" == "OK" ]]; then
      check_ok "playwright browser" "${playwright_mode} ${playwright_version}"
    else
      check_fail "playwright browser" "report status is ${playwright_status}"
    fi
  else
    check_warn "playwright browser" "report exists but jq is unavailable"
  fi
else
  check_fail "playwright browser" "missing $PLAYWRIGHT_BROWSER_REPORT; run scripts/dev/install-playwright-browser.sh"
fi

status="PASS"
if [[ "$required_failures" -gt 0 ]]; then status="FAIL"; fi
{
  printf '{\n'
  printf '  "schema": "pocketlab.wslUbuntuCheck/v1",\n'
  printf '  "generated_at_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "target_root": "%s",\n' "$TARGET_ROOT"
  printf '  "overall_status": "%s",\n' "$status"
  printf '  "required_failures": %s,\n' "$required_failures"
  printf '  "warnings": %s\n' "$warnings"
  printf '}\n'
} > "$REPORT_PATH"
printf '\nReport: %s\n' "$REPORT_PATH"
if [[ "$required_failures" -gt 0 ]]; then
  printf 'WSL Ubuntu development environment check failed.\n' >&2
  exit 1
fi
printf 'WSL Ubuntu development environment check passed.\n'
