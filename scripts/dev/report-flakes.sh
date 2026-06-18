#!/usr/bin/env bash
set -Eeuo pipefail
WORKERS="${POCKETLAB_FLAKES_WORKERS:-${POCKETLAB_FLAKE_WORKERS:-2}}"
ROUNDS="${POCKETLAB_FLAKES_REPEAT:-${POCKETLAB_FLAKE_ROUNDS:-3}}"

REPORT_DIR=".pocketlab-dev/reports/flakes"
QUARANTINE_DIR="tests/e2e/quarantine"

mkdir -p "$REPORT_DIR" "$QUARANTINE_DIR"

SUMMARY_MD="$REPORT_DIR/flaky-tests.md"
SUMMARY_JSON="$REPORT_DIR/flaky-tests.json"
: > "$SUMMARY_MD"

SPECS=(
  "tests/e2e/golden-path.spec.ts"
  "tests/e2e/fault-degraded-mode.spec.ts"
  "tests/e2e/control-plane-readiness.spec.ts"
  "tests/e2e/network-contracts.spec.ts"
  "tests/e2e/websocket-events.spec.ts"
  "tests/e2e/telemetry.spec.ts"
  "tests/e2e/accessibility.spec.ts"
)

echo "# Pocket Lab Enterprise Flaky Test Report" | tee -a "$SUMMARY_MD"
echo | tee -a "$SUMMARY_MD"
echo "Rounds: $ROUNDS" | tee -a "$SUMMARY_MD"
echo "Workers: $WORKERS" | tee -a "$SUMMARY_MD"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" | tee -a "$SUMMARY_MD"
echo | tee -a "$SUMMARY_MD"

echo "## Scope" | tee -a "$SUMMARY_MD"
for spec in "${SPECS[@]}"; do
  echo "- $spec" | tee -a "$SUMMARY_MD"
done
echo | tee -a "$SUMMARY_MD"

quarantined_count="$(find "$QUARANTINE_DIR" -type f -name '*.spec.ts' 2>/dev/null | wc -l | tr -d ' ')"

echo "## Quarantine" | tee -a "$SUMMARY_MD"
echo "Quarantined specs: $quarantined_count" | tee -a "$SUMMARY_MD"
find "$QUARANTINE_DIR" -type f -name '*.spec.ts' -printf '- %p\n' 2>/dev/null | tee -a "$SUMMARY_MD" || true
echo | tee -a "$SUMMARY_MD"

echo "## Static Flake Guards" | tee -a "$SUMMARY_MD"

static_failures=0

if grep -R "test\.only\|describe\.only\|it\.only" -n tests/e2e tests/backend 2>/dev/null | tee "$REPORT_DIR/only-markers.txt"; then
  if [ -s "$REPORT_DIR/only-markers.txt" ]; then
    echo "❌ Found focused test markers." | tee -a "$SUMMARY_MD"
    static_failures=$((static_failures + 1))
  else
    echo "✅ No focused test markers found." | tee -a "$SUMMARY_MD"
  fi
else
  echo "✅ No focused test markers found." | tee -a "$SUMMARY_MD"
fi

if grep -R "test\.skip\|describe\.skip\|it\.skip\|test\.fixme" -n tests/e2e tests/backend 2>/dev/null | grep -v "$QUARANTINE_DIR" | tee "$REPORT_DIR/skip-markers.txt"; then
  if [ -s "$REPORT_DIR/skip-markers.txt" ]; then
    echo "❌ Found skipped/fixme tests outside quarantine." | tee -a "$SUMMARY_MD"
    static_failures=$((static_failures + 1))
  else
    echo "✅ No skipped/fixme tests outside quarantine." | tee -a "$SUMMARY_MD"
  fi
else
  echo "✅ No skipped/fixme tests outside quarantine." | tee -a "$SUMMARY_MD"
fi

echo | tee -a "$SUMMARY_MD"
echo "## Repeated Playwright Stability Runs" | tee -a "$SUMMARY_MD"

overall_failures=0

for round in $(seq 1 "$ROUNDS"); do
  json_report="$REPORT_DIR/playwright-round-${round}.json"
  log_report="$REPORT_DIR/playwright-round-${round}.log"

  echo | tee -a "$SUMMARY_MD"
  echo "### Round $round" | tee -a "$SUMMARY_MD"

  set +e
  npx playwright test --repeat-each=${ROUNDS} "${SPECS[@]}" \
    --workers="$WORKERS" \
    --retries=0 \
    --reporter=json \
    > "$json_report" 2> "$log_report"
  exit_code=$?
  set -e

  if [ "$exit_code" -ne 0 ]; then
    echo "❌ Round $round failed with exit code $exit_code" | tee -a "$SUMMARY_MD"
    overall_failures=$((overall_failures + 1))
  else
    echo "✅ Round $round passed" | tee -a "$SUMMARY_MD"
  fi

  python3 - "$json_report" "$SUMMARY_MD" <<'PY'
import json
import sys
from pathlib import Path

json_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])

try:
    data = json.loads(json_path.read_text())
except Exception as exc:
    with summary_path.open("a") as fh:
        fh.write(f"\nUnable to parse Playwright JSON report: {exc}\n")
    raise SystemExit(0)

stats = data.get("stats", {})
suites = data.get("suites", [])

failed = []
flaky = []
unexpected = []
skipped = []

def walk_specs(suite, path=""):
    title = suite.get("title") or ""
    current = f"{path} / {title}".strip(" /")

    for spec in suite.get("specs", []):
        spec_title = spec.get("title", "")
        full_title = f"{current} / {spec_title}".strip(" /")
        ok = spec.get("ok", False)
        tests = spec.get("tests", [])

        if not ok:
            failed.append(full_title)

        for test in tests:
            expected = test.get("expectedStatus")
            status = test.get("status")
            if status == "flaky":
                flaky.append(full_title)
            if status not in (None, expected, "expected"):
                unexpected.append(f"{full_title} [{status}]")
            if status == "skipped" or expected == "skipped":
                skipped.append(full_title)

    for child in suite.get("suites", []):
        walk_specs(child, current)

for suite in suites:
    walk_specs(suite)

with summary_path.open("a") as fh:
    fh.write(f"- Expected: {stats.get('expected', 0)}\n")
    fh.write(f"- Unexpected: {stats.get('unexpected', 0)}\n")
    fh.write(f"- Flaky: {stats.get('flaky', 0)}\n")
    fh.write(f"- Skipped: {stats.get('skipped', 0)}\n")

    if failed:
        fh.write("- Failed specs:\n")
        for item in failed:
            fh.write(f"  - {item}\n")

    if flaky:
        fh.write("- Flaky specs:\n")
        for item in sorted(set(flaky)):
            fh.write(f"  - {item}\n")

    if unexpected:
        fh.write("- Unexpected statuses:\n")
        for item in sorted(set(unexpected)):
            fh.write(f"  - {item}\n")

    if skipped:
        fh.write("- Skipped specs:\n")
        for item in sorted(set(skipped)):
            fh.write(f"  - {item}\n")
PY

done

cat > "$SUMMARY_JSON" <<EOF_JSON
{
  "gate": "test:flakes",
  "rounds": $ROUNDS,
  "workers": $WORKERS,
  "quarantined_specs": $quarantined_count,
  "static_failures": $static_failures,
  "round_failures": $overall_failures,
  "status": "$([ "$static_failures" -eq 0 ] && [ "$overall_failures" -eq 0 ] && echo passed || echo failed)"
}
EOF_JSON

echo | tee -a "$SUMMARY_MD"
echo "## Gate Verdict" | tee -a "$SUMMARY_MD"

if [ "$quarantined_count" -ne 0 ]; then
  echo "❌ Quarantined specs exist. Review or remove quarantine before release." | tee -a "$SUMMARY_MD"
  overall_failures=$((overall_failures + 1))
fi

if [ "$static_failures" -ne 0 ]; then
  echo "❌ Static flake guards failed." | tee -a "$SUMMARY_MD"
fi

if [ "$overall_failures" -ne 0 ] || [ "$static_failures" -ne 0 ]; then
  echo "❌ Pocket Lab flaky-test gate failed." | tee -a "$SUMMARY_MD"
  echo "Report: $SUMMARY_MD"
  exit 1
fi

echo "✅ Pocket Lab flaky-test gate passed." | tee -a "$SUMMARY_MD"
echo "Report: $SUMMARY_MD"
