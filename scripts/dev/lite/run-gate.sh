#!/usr/bin/env bash
set -euo pipefail

TIER="${1:-quick}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/dev-scratch.sh"
pocketlab_dev_scratch_activate "gate-${TIER}"

VALIDATION_DIR="${VALIDATION_DIR:-.pocketlab-dev/validation}"
PYTHON="${POCKETLAB_DEV_PYTHON:-${PYTHON:-.venv/bin/python}}"
if [[ ! -x "$PYTHON" ]]; then PYTHON=python3; fi
mkdir -p "$VALIDATION_DIR/commands"
printf 'INFO dev scratch: %s\n' "$TMPDIR"

record() {
  local name="$1"; shift
  "$PYTHON" scripts/dev/lite/validation_evidence.py run --name "$name" --validation-dir "$VALIDATION_DIR" -- "$@"
}

record protected-versions bash scripts/dev/lite/setup-check.sh
record shell-syntax bash -lc 'find scripts/dev/lite -maxdepth 1 -type f -name "*.sh" -print0 | xargs -0 -r -n1 bash -n'
record browser-resolver node --test tests/dev/browser-resolver.test.mjs
record python-compile "$PYTHON" -m py_compile \
  scripts/docs/lite/generate_contracts.py \
  scripts/docs/lite/generate_docs.py \
  scripts/dev/lite/har_tool.py \
  scripts/dev/lite/redaction_check.py \
  scripts/dev/lite/validation_evidence.py \
  scripts/dev/lite/release_artifact_check.py
record focused-backend bash -lc "PYTHONPATH=tests:pocket-lab-final-structure/runtime PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 '$PYTHON' -m pytest -q tests/backend/test_lite_api.py -k 'status or catalog or fleet or security or recovery or identity or policy'"
record frontend-unit npm run test:unit
record contracts bash scripts/dev/lite/check-contracts.sh
record pwa-build npm run build
record diff-check git diff --check
record docs-development-drift "$PYTHON" scripts/docs/lite/generate_docs.py check --audience development
record docs-production-drift "$PYTHON" scripts/docs/lite/generate_docs.py check --audience production

if [[ "$TIER" == "quick" ]]; then
  record allure-results "$PYTHON" scripts/dev/lite/validation_evidence.py allure --validation-dir "$VALIDATION_DIR" --output allure-results
  exit 0
fi

record backend-full task lite:test:backend
record storybook task lite:test:storybook
record e2e-mocked task lite:test:e2e:mocked
record accessibility task lite:test:a11y
record docs-browser task lite:test:docs
record redaction task lite:test:redaction
record docs-strict task lite:docs:check

if [[ "$TIER" == "full" ]]; then
  record allure-results "$PYTHON" scripts/dev/lite/validation_evidence.py allure --validation-dir "$VALIDATION_DIR" --output allure-results
  exit 0
fi

if [[ "$TIER" != "release" ]]; then
  echo "Unknown Lite gate tier: $TIER" >&2
  exit 2
fi

if [[ "${LITE_E2E_LIVE:-0}" != "1" ]]; then
  echo 'Release gate requires LITE_E2E_LIVE=1 and a running isolated Caddy/FastAPI/SQLite/NATS/worker/PWA stack.' >&2
  exit 2
fi
record e2e-live task lite:test:e2e:live
record runtime task lite:test:runtime
record visual task lite:test:visual
if [[ "${LITE_ANDROID_GATE:-0}" == "1" ]]; then
  record android task lite:test:android
else
  echo 'INFO Android/Termux gate not requested. Set LITE_ANDROID_GATE=1 only with an explicitly configured test device.'
fi
record release-dry-run task lite:release:dry-run
record allure-results "$PYTHON" scripts/dev/lite/validation_evidence.py allure --validation-dir "$VALIDATION_DIR" --output allure-results
