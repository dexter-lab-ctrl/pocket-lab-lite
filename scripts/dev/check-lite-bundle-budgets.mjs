#!/usr/bin/env node
import { existsSync, readFileSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { join, resolve } from 'node:path';

const root = resolve(process.cwd());
const distDir = resolve(root, process.env.POCKETLAB_DIST_DIR || 'dist');
const manifestPath = join(distDir, '.vite', 'manifest.json');

const budgets = Object.freeze({
  initialJavaScript: { warning: 900_000, failure: 1_250_000 },
  initialCss: { warning: 650_000, failure: 850_000 },
  routeChunk: { warning: 650_000, failure: 900_000 },
  initialGzip: { warning: 340_000, failure: 480_000 },
});

const screenSources = Object.freeze([
  'src/lite/LiteCatalog.jsx',
  'src/lite/LiteIdentity.jsx',
  'src/lite/LiteSecurity.jsx',
  'src/lite/LiteDevices.jsx',
  'src/lite/LiteRules.jsx',
  'src/lite/LiteRecovery.jsx',
]);

function fail(message) {
  console.error(`[bundle-budget] ERROR: ${message}`);
  process.exitCode = 1;
}

function warn(message) {
  console.warn(`[bundle-budget] WARNING: ${message}`);
}

function assetBytes(relativePath) {
  const path = join(distDir, relativePath);
  return existsSync(path) ? statSync(path).size : 0;
}

function assetGzipBytes(relativePath) {
  const path = join(distDir, relativePath);
  return existsSync(path) ? gzipSync(readFileSync(path)).byteLength : 0;
}

function formatBytes(value) {
  return `${(value / 1024).toFixed(1)} KiB`;
}

function collectStaticGraph(manifest, startKey) {
  const seen = new Set();
  const visit = (key) => {
    if (!key || seen.has(key) || !manifest[key]) return;
    seen.add(key);
    for (const dependency of manifest[key].imports || []) visit(dependency);
  };
  visit(startKey);
  return seen;
}

function checkBudget(name, value, budget) {
  if (value > budget.failure) {
    fail(`${name} is ${formatBytes(value)}; hard limit is ${formatBytes(budget.failure)}.`);
  } else if (value > budget.warning) {
    warn(`${name} is ${formatBytes(value)}; warning threshold is ${formatBytes(budget.warning)}.`);
  }
}

if (!existsSync(manifestPath)) {
  fail(`Missing ${manifestPath}. Run npm run build first.`);
  process.exit();
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const entryKey = Object.keys(manifest).find((key) => manifest[key]?.isEntry)
  || Object.keys(manifest).find((key) => /src\/(?:main|index)\.(?:jsx?|tsx?)$/.test(key));

if (!entryKey) {
  fail('Could not identify the Vite entry in the build manifest.');
  process.exit();
}

const initialGraph = collectStaticGraph(manifest, entryKey);
const initialJsAssets = new Set();
const initialCssAssets = new Set();
for (const key of initialGraph) {
  const record = manifest[key];
  if (record?.file?.endsWith('.js')) initialJsAssets.add(record.file);
  for (const css of record?.css || []) initialCssAssets.add(css);
}

const initialJavaScript = [...initialJsAssets].reduce((total, asset) => total + assetBytes(asset), 0);
const initialCss = [...initialCssAssets].reduce((total, asset) => total + assetBytes(asset), 0);
const initialGzip = [...initialJsAssets].reduce((total, asset) => total + assetGzipBytes(asset), 0)
  + [...initialCssAssets].reduce((total, asset) => total + assetGzipBytes(asset), 0);

checkBudget('Initial JavaScript', initialJavaScript, budgets.initialJavaScript);
checkBudget('Initial CSS', initialCss, budgets.initialCss);
checkBudget('Initial JavaScript + CSS gzip', initialGzip, budgets.initialGzip);

const eagerScreens = screenSources.filter((source) => initialGraph.has(source));
if (eagerScreens.length) {
  fail(`Unexpected eager Lite screen imports: ${eagerScreens.join(', ')}.`);
}

const routeChunks = [];
for (const source of screenSources) {
  const record = manifest[source];
  if (!record?.file) {
    fail(`Missing route chunk manifest entry for ${source}.`);
    continue;
  }
  const bytes = assetBytes(record.file);
  routeChunks.push({ source, file: record.file, bytes });
  checkBudget(`${source} route chunk`, bytes, budgets.routeChunk);
}

const duplicateFiles = new Map();
for (const [key, record] of Object.entries(manifest)) {
  if (!record?.file?.endsWith('.js')) continue;
  const keys = duplicateFiles.get(record.file) || [];
  keys.push(key);
  duplicateFiles.set(record.file, keys);
}
const duplicateChunkRecords = [...duplicateFiles.entries()].filter(([, keys]) => keys.length > 1);
if (duplicateChunkRecords.length > 4) {
  fail(`The manifest maps ${duplicateChunkRecords.length} duplicated JavaScript chunk records; inspect Rollup output for accidental vendor duplication.`);
} else if (duplicateChunkRecords.length) {
  warn(`The manifest maps ${duplicateChunkRecords.length} shared JavaScript chunk record(s); verify they are intentional shared chunks.`);
}

routeChunks.sort((left, right) => right.bytes - left.bytes);
const largestRoute = routeChunks[0];
console.log('[bundle-budget] PASS summary');
console.log(`  initial-js=${formatBytes(initialJavaScript)}`);
console.log(`  initial-css=${formatBytes(initialCss)}`);
console.log(`  initial-gzip=${formatBytes(initialGzip)}`);
console.log(`  route-chunks=${routeChunks.length}`);
if (largestRoute) console.log(`  largest-route=${largestRoute.source} ${formatBytes(largestRoute.bytes)}`);
for (const route of routeChunks) {
  console.log(`  screen=${route.source} file=${route.file} size=${formatBytes(route.bytes)}`);
}
