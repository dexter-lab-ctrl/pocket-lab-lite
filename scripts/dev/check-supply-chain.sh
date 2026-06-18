#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p .pocketlab-dev
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3

SECRET_SCAN_FILE_LIST=".pocketlab-dev/secret-scan-files.txt"
DETECT_SECRETS_OUT=".pocketlab-dev/detect-secrets.json"
GITLEAKS_OUT=".pocketlab-dev/gitleaks.json"
SBOM_OUT=".pocketlab-dev/sbom.spdx.json"

echo "Python dependency audit..."
"$PYTHON" -m pip_audit || true

echo "Safety audit..."
"$PYTHON" -m safety check || true

echo "Preparing active-code secret scan scope..."
python3 - <<'PY'
from pathlib import Path

roots = [
    Path("src"),
    Path("runbooks"),
    Path("architecture/structurizr"),
    Path("contracts"),
    Path("scripts/dev"),
    Path("scripts/docs"),
    Path("pocket-lab-final-structure/runtime"),
    Path("pocket-lab-final-structure/pocket-lab-iac-api-compatible"),
]

excluded_parts = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "site",
    "storybook-static",
    ".pocketlab-dev",
    "__pycache__",
    "migrations",
    "archive",
    "history",
    "allure-results",
    "allure-history",
}

excluded_suffixes = {
    ".bak",
    ".orig",
    ".rej",
    ".patch",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pyc",
    ".sqlite",
    ".db",
}

text_suffixes = {
    "",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".mdx",
    ".sh",
    ".ps1",
    ".toml",
    ".ini",
    ".cfg",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".dsl",
    ".rego",
}

files = []

for root in roots:
    if not root.exists():
        continue

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        parts = set(path.parts)
        if parts & excluded_parts:
            continue

        if path.suffix in excluded_suffixes:
            continue

        if path.suffix not in text_suffixes:
            continue

        files.append(str(path))

Path(".pocketlab-dev/secret-scan-files.txt").write_text(
    "\n".join(sorted(set(files))) + "\n",
    encoding="utf-8",
)

print(f"Active files selected for secret scan: {len(set(files))}")
PY

echo "Secret scan..."
if [[ -s "$SECRET_SCAN_FILE_LIST" ]]; then
  if command -v detect-secrets >/dev/null 2>&1; then
    timeout --kill-after=15s 180s \
      detect-secrets scan $(cat "$SECRET_SCAN_FILE_LIST") \
      > "$DETECT_SECRETS_OUT" || true
  elif [[ -x .venv/bin/detect-secrets ]]; then
    timeout --kill-after=15s 180s \
      .venv/bin/detect-secrets scan $(cat "$SECRET_SCAN_FILE_LIST") \
      > "$DETECT_SECRETS_OUT" || true
  else
    echo "WARN: detect-secrets not installed; CI should run secret scanning."
  fi
else
  echo "WARN: no active files found for secret scan."
fi

if command -v gitleaks >/dev/null 2>&1; then
  timeout --kill-after=15s 180s \
    gitleaks detect \
      --no-banner \
      --redact \
      --no-git \
      --source . \
      --report-path "$GITLEAKS_OUT" \
      --log-opts="-- . ':!.venv' ':!node_modules' ':!dist' ':!site' ':!storybook-static' ':!.pocketlab-dev' ':!docs/history' ':!docs/archive' ':!scripts/dev/migrations'" \
    || true
else
  echo "WARN: gitleaks not installed; CI should run gitleaks."
fi

if [[ -f package.json ]]; then
  echo "npm audit..."
  npm audit --audit-level=moderate || true
fi

if command -v trivy >/dev/null 2>&1; then
  echo "Trivy filesystem scan..."
  timeout --kill-after=15s 300s \
    trivy fs \
      --scanners vuln,secret,misconfig \
      --skip-dirs .git \
      --skip-dirs .venv \
      --skip-dirs node_modules \
      --skip-dirs dist \
      --skip-dirs site \
      --skip-dirs storybook-static \
      --skip-dirs .pocketlab-dev \
      --skip-dirs docs/history \
      --skip-dirs docs/archive \
      --skip-dirs scripts/dev/migrations \
      --format table . \
    || true
else
  echo "WARN: trivy not installed; CI workflow runs Trivy."
fi

if command -v syft >/dev/null 2>&1; then
  echo "SBOM generation..."
  timeout --kill-after=15s 180s syft dir:. -o spdx-json > "$SBOM_OUT" || true
else
  echo "WARN: syft not installed; release workflow generates SBOM."
fi

echo "Supply-chain check completed."
