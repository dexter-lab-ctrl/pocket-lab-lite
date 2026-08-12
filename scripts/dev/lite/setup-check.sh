#!/usr/bin/env bash
set -euo pipefail

fail=0
check_cmd() {
  local label="$1"; shift
  local output

  if output="$("$@" 2>&1)"; then
    printf 'PASS %-24s %s\n' \
      "$label" \
      "$(printf '%s\n' "$output" | head -n1)"
  else
    printf 'FAIL %-24s missing or unusable\n' \
      "$label" >&2
    fail=1
  fi
}

check_cmd node node --version
check_cmd npm npm --version
check_cmd python python3 --version
check_cmd java java -version
check_cmd task task --version
if grep -qi microsoft /proc/version 2>/dev/null; then
  check_cmd chrome /usr/bin/google-chrome --version
elif [[ -n "${CI:-}" ]]; then
  echo 'PASS chrome                   Playwright-managed Chromium allowed in CI'
else
  node scripts/dev/lite/resolve-browser.mjs --json >/dev/null || fail=1
fi
check_cmd playwright node -p "require('./node_modules/@playwright/test/package.json').version"
check_cmd storybook node -p "require('./node_modules/storybook/package.json').version"
check_cmd redocly node -p "require('./node_modules/@redocly/cli/package.json').version"

if [[ ! -x .venv/bin/python ]]; then
  echo 'FAIL .venv: existing virtual environment is missing. Run python3 -m venv .venv only if the repository environment was not provisioned.' >&2
  fail=1
else
  .venv/bin/python - <<'PY' || fail=1
import importlib
required = ['mkdocs', 'yaml', 'jinja2', 'jsonschema', 'pytest']
missing = []
for name in required:
    try:
        importlib.import_module(name)
    except Exception:
        missing.append(name)
if missing:
    raise SystemExit('FAIL Python modules: ' + ', '.join(missing))
print('PASS Python documentation/test modules')
PY
fi

if [[ ! -d node_modules ]]; then
  echo 'FAIL node_modules: run task lite:setup to restore the committed npm lockfile.' >&2
  fail=1
fi

node scripts/dev/lite/resolve-browser.mjs --json >/dev/null || fail=1

python3 scripts/dev/lite/tool_versions.py --output "${VALIDATION_DIR:-.pocketlab-dev/validation}/protected-tool-versions.json" || fail=1
exit "$fail"
