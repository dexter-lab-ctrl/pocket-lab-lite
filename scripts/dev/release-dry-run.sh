#!/usr/bin/env bash
set -Eeuo pipefail

# POCKETLAB_RELEASE_DRY_RUN_ACTIVE_SCOPE_EXCLUDES
# Historical migration/fix scripts are retained for auditability, but they are not
# active runtime, contract, API, worker, frontend, docs, or validation code.
# Retired-symbol release blocking must apply to active code paths only.
ACTIVE_SCOPE_EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=.venv
  --exclude-dir=node_modules
  --exclude-dir=dist
  --exclude-dir=site
  --exclude-dir=storybook-static
  --exclude-dir=.pocketlab-dev
  --exclude-dir=__pycache__
  --exclude-dir=migrations
  --exclude='*.bak'
  --exclude='*.orig'
  --exclude='*.rej'
  --exclude='*.patch'
  --exclude='*.zip'
  --exclude='*.tar'
  --exclude='*.gz'
)

version="${1:-dev-$(date '+%Y%m%d-%H%M%S')}"; out=".pocketlab-dev/releases/$version"; mkdir -p "$out"
iac_dir="pocket-lab-final-structure/pocket-lab-iac-api-compatible"

bash scripts/dev/check-architecture-contract.sh
# Release qualification follows the current Lite backend contract rather than
# the historical blanket backend suite. The canonical task is bounded, timeout-
# protected, plugin-isolated, and shared with the normal Lite quality gate.
task lite:test:backend
bash scripts/dev/check-bootstrap.sh
# The current Lite repository no longer requires the historical full-profile IaC
# tree. If a checkout intentionally carries it, keep validating and packaging it;
# otherwise record the absence explicitly instead of failing a Lite release.
if [[ -d "$iac_dir" ]]; then
  bash scripts/dev/check-iac.sh
else
  echo "INFO Lite release: optional legacy/full-profile IaC tree is not present; skipping IaC validation/package."
fi
bash scripts/dev/check-supply-chain.sh
[[ -f package.json ]] && npm run build

tar --exclude=".git" --exclude="node_modules" --exclude=".venv" --exclude=".pocketlab-dev/releases" -czf "$out/pocketlab-source-$version.tar.gz" .
[[ -d dist ]] && tar -czf "$out/pocketlab-pwa-$version.tar.gz" dist
[[ -d dist ]] && tar -czf "$out/pocketlab-pwa-dist-$version.tar.gz" dist
tar -czf "$out/pocketlab-runtime-$version.tar.gz" pocket-lab-final-structure/runtime
if [[ -d "$iac_dir" ]]; then
  tar -czf "$out/pocketlab-iac-$version.tar.gz" "$iac_dir"
fi
tar -czf "$out/pocketlab-bootstrap-$version.tar.gz" pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
if command -v syft >/dev/null 2>&1; then syft dir:. -o spdx-json > "$out/sbom.spdx.json" || true; fi
(cd "$out" && sha256sum * > checksums.txt)
if command -v cosign >/dev/null 2>&1; then (cd "$out" && cosign sign-blob --yes --output-signature checksums.txt.sig checksums.txt) || true; else echo "WARN: cosign not installed; GitHub release can sign/attest later."; fi

# Mirror the canonical release-dist workflow artifact contract at the repository
# root so Taskfile.release can validate the exact Lite PWA asset shape locally.
# A dry run has no immutable release tag, so pocketlab-lite-release.json remains
# absent just as it does for a source-build workflow run.
[[ -d dist ]] || { echo "ERROR Lite release: dist directory was not produced" >&2; exit 2; }
for required in index.html manifest.webmanifest sw.js; do
  [[ -f "dist/$required" ]] || { echo "ERROR Lite release: missing dist/$required" >&2; exit 2; }
done
command -v zip >/dev/null 2>&1 || { echo "ERROR Lite release: zip is required to create dist.zip" >&2; exit 2; }
rm -f dist.zip checksums.txt pocketlab-lite-release.json
(cd dist && zip -q -r ../dist.zip .)
sha256sum dist.zip > checksums.txt

echo "Release dry-run artifacts: $out"
echo "Canonical Lite PWA artifacts: dist.zip checksums.txt"
