#!/usr/bin/env bash
set -Eeuo pipefail
# POCKETLAB_LIGHTHOUSE_WSL_CHROME_FIX
# In WSL2, Lighthouse/chrome-launcher can discover Windows Chrome through the
# inherited Windows PATH. Force Linux Chrome so DevTools is reachable from WSL.
if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
  for chrome_candidate in \
    /usr/bin/google-chrome \
    /usr/bin/google-chrome-stable \
    /usr/bin/chromium \
    /usr/bin/chromium-browser
  do
    if [[ -x "$chrome_candidate" ]]; then
      export CHROME_PATH="${POCKETLAB_LIGHTHOUSE_CHROME_PATH:-$chrome_candidate}"
      export LHCI_CHROME_PATH="$CHROME_PATH"
      break
    fi
  done

  if [[ -z "${CHROME_PATH:-}" || ! -x "$CHROME_PATH" ]]; then
    echo "ERROR: Linux Chrome not found for Lighthouse in WSL2." >&2
    echo "Install Google Chrome or set POCKETLAB_LIGHTHOUSE_CHROME_PATH." >&2
    exit 1
  fi

  export POCKETLAB_LIGHTHOUSE_CHROME_FLAGS="${POCKETLAB_LIGHTHOUSE_CHROME_FLAGS:---headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-extensions --remote-debugging-address=127.0.0.1}"
  echo "Using Lighthouse Chrome: $CHROME_PATH"
fi
if ! command -v npx >/dev/null 2>&1; then echo 'npx required' >&2; exit 1; fi
npx lhci autorun --config=lighthouserc.json
