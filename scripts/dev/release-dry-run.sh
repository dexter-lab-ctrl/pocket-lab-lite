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
bash scripts/dev/check-architecture-contract.sh
bash scripts/dev/check-backend.sh
bash scripts/dev/check-bootstrap.sh
bash scripts/dev/check-iac.sh
bash scripts/dev/check-supply-chain.sh
[[ -f package.json ]] && npm run build
tar --exclude=".git" --exclude="node_modules" --exclude=".venv" --exclude=".pocketlab-dev/releases" -czf "$out/pocketlab-source-$version.tar.gz" .
[[ -d dist ]] && tar -czf "$out/pocketlab-pwa-$version.tar.gz" dist
[[ -d dist ]] && tar -czf "$out/pocketlab-pwa-dist-$version.tar.gz" dist
tar -czf "$out/pocketlab-runtime-$version.tar.gz" pocket-lab-final-structure/runtime
tar -czf "$out/pocketlab-iac-$version.tar.gz" pocket-lab-final-structure/pocket-lab-iac-api-compatible
tar -czf "$out/pocketlab-bootstrap-$version.tar.gz" pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
if command -v syft >/dev/null 2>&1; then syft dir:. -o spdx-json > "$out/sbom.spdx.json" || true; fi
(cd "$out" && sha256sum * > checksums.txt)
if command -v cosign >/dev/null 2>&1; then (cd "$out" && cosign sign-blob --yes --output-signature checksums.txt.sig checksums.txt) || true; else echo "WARN: cosign not installed; GitHub release can sign/attest later."; fi
echo "Release dry-run artifacts: $out"
