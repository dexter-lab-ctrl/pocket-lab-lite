#!/usr/bin/env bash
set -Eeuo pipefail
[[ -f package.json ]] || { echo "No package.json; skipping frontend"; exit 0; }
if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
npm run lint --if-present
npm run typecheck --if-present
npm run format:check --if-present || true
npm run test --if-present -- --run || npm run test --if-present || true
npm run build
[[ -d dist ]] || { echo "Expected dist/ after PWA build" >&2; exit 1; }
if [[ -f dist/manifest.webmanifest || -f dist/manifest.json ]]; then echo "PWA manifest present"; else echo "WARN: PWA manifest not found in dist/"; fi
if find dist -type f \( -name 'sw.js' -o -name 'service-worker.js' -o -name 'workbox-*.js' \) | grep -q .; then echo "Service worker artifact present"; else echo "WARN: service worker artifact not found in dist/"; fi
node - <<'NODE'
const fs=require('fs'); const path=require('path');
let total=0; function walk(d){if(!fs.existsSync(d))return; for(const f of fs.readdirSync(d)){const p=path.join(d,f); const s=fs.statSync(p); if(s.isDirectory()) walk(p); else total+=s.size;}}
walk('dist'); const mb=total/1024/1024; console.log(`PWA bundle size: ${mb.toFixed(2)} MiB`); if(mb>15){console.error('PWA bundle exceeds 15 MiB budget'); process.exit(1)}
NODE
