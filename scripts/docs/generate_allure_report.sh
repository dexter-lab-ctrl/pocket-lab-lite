#!/usr/bin/env bash
set -Eeuo pipefail

RESULTS_DIR="docs/validation/generated/allure-results"
REPORT_DIR="docs/validation/generated/allure-report"
HISTORY_DIR="docs/validation/generated/allure-history"

python3 scripts/docs/generate_validation_evidence.py
mkdir -p "$RESULTS_DIR" "$HISTORY_DIR"

if [ -d "$REPORT_DIR/history" ]; then
  rm -rf "$RESULTS_DIR/history"
  cp -R "$REPORT_DIR/history" "$RESULTS_DIR/history"
fi

if command -v allure >/dev/null 2>&1; then
  allure generate "$RESULTS_DIR" --clean -o "$REPORT_DIR"
elif command -v npx >/dev/null 2>&1; then
  npx -y allure-commandline generate "$RESULTS_DIR" --clean -o "$REPORT_DIR"
else
  echo "ERROR: Allure command line is required. Install allure or make npx available." >&2
  exit 1
fi

if [ -d "$REPORT_DIR/history" ]; then
  rm -rf "$HISTORY_DIR/allure-report-history"
  mkdir -p "$HISTORY_DIR"
  cp -R "$REPORT_DIR/history" "$HISTORY_DIR/allure-report-history"
fi

echo "Allure report generated at $REPORT_DIR/index.html"
