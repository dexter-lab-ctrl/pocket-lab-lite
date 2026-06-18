#!/usr/bin/env bash
set -Eeuo pipefail

log(){ printf '[INFO] %s\n' "$*"; }
ok(){ printf '[OK] %s\n' "$*"; }
warn(){ printf '[WARN] %s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

REPORT_PATH="${POCKETLAB_PLAYWRIGHT_REPORT_PATH:-.pocketlab-dev/reports/playwright-browser.json}"
mkdir -p "$(dirname "$REPORT_PATH")"

OS_ID="unknown"
OS_VERSION="unknown"
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VERSION="${VERSION_ID:-unknown}"
fi

IS_WSL="false"
if grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL="true"
fi

status="UNKNOWN"
browser_mode="unknown"
browser_version="unknown"

write_report(){
  cat > "$REPORT_PATH" <<JSON
{
  "schema": "pocketlab.playwrightBrowser/v1",
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "$status",
  "os_id": "$OS_ID",
  "os_version": "$OS_VERSION",
  "is_wsl": "$IS_WSL",
  "browser_mode": "$browser_mode",
  "browser_version": "$browser_version"
}
JSON
}

validate_system_chrome(){
  if ! have google-chrome; then
    return 1
  fi

  browser_version="$(google-chrome --version | sed 's/"/\\"/g')"
  export POCKETLAB_PLAYWRIGHT_CHANNEL="${POCKETLAB_PLAYWRIGHT_CHANNEL:-chrome}"

  node - <<'NODE'
const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({
    channel: process.env.POCKETLAB_PLAYWRIGHT_CHANNEL || 'chrome',
    headless: true,
    args: ['--no-sandbox']
  });
  console.log(await browser.version());
  await browser.close();
})();
NODE
}

install_google_chrome(){
  log "Installing system Google Chrome fallback"
  sudo install -d -m 0755 /etc/apt/keyrings

  if [[ ! -f /etc/apt/keyrings/google-linux-signing-keyring.gpg ]]; then
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | sudo gpg --dearmor -o /etc/apt/keyrings/google-linux-signing-keyring.gpg
  fi

  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    | sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null

  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y google-chrome-stable
}

log "Preparing Playwright browser support"

if [[ "$OS_ID" == "ubuntu" && "$OS_VERSION" == "26.04" ]]; then
  warn "Ubuntu 26.04 detected. Using system Chrome fallback because Playwright-managed Chromium is not supported here yet."

  if ! have google-chrome; then
    install_google_chrome
  fi

  validate_system_chrome >/tmp/pocketlab-playwright-browser-version.txt
  browser_version="$(cat /tmp/pocketlab-playwright-browser-version.txt | tail -n1 | sed 's/"/\\"/g')"
  browser_mode="system-chrome"
  status="OK"
  write_report
  ok "Playwright launched system Chrome successfully: $browser_version"
  ok "Browser report written to $REPORT_PATH"
  exit 0
fi

log "Using Playwright-managed Chromium install"
if npx playwright install --with-deps chromium; then
  browser_mode="playwright-managed-chromium"
  browser_version="$(npx playwright --version | sed 's/"/\\"/g')"
  status="OK"
  write_report
  ok "Playwright-managed Chromium installed"
  ok "Browser report written to $REPORT_PATH"
else
  status="FAILED"
  browser_mode="playwright-managed-chromium"
  write_report
  fail "Playwright-managed Chromium install failed"
fi
