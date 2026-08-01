#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { spawnSync } from 'node:child_process';

const explicitNames = [
  'PLAYWRIGHT_EXECUTABLE_PATH',
  'POCKETLAB_PLAYWRIGHT_EXECUTABLE_PATH',
  'CHROME_PATH',
  'CHROMIUM_PATH',
  'EDGE_PATH',
];
const candidates = [
  ['/usr/bin/google-chrome', 'Google Chrome'],
  ['/usr/bin/google-chrome-stable', 'Google Chrome Stable'],
  ['/usr/bin/chromium', 'Chromium'],
  ['/usr/bin/chromium-browser', 'Chromium Browser'],
  ['/usr/bin/microsoft-edge', 'Microsoft Edge'],
  ['/usr/bin/microsoft-edge-stable', 'Microsoft Edge Stable'],
];

export function isWsl() {
  try {
    return readFileSync('/proc/version', 'utf8').toLowerCase().includes('microsoft');
  } catch {
    return false;
  }
}

function browserVersion(path) {
  const result = spawnSync(path, ['--version'], { encoding: 'utf8', timeout: 10_000 });
  return String(result.stdout || result.stderr || '').trim();
}

export function resolveLiteBrowser({ env = process.env } = {}) {
  for (const name of explicitNames) {
    const path = String(env[name] || '').trim();
    if (!path) continue;
    if (!existsSync(path)) {
      throw new Error(`${name} points to a missing executable: ${path}`);
    }
    return { name, browser: browserVersion(path).split(/\s+\d/)[0] || 'External browser', executable_path: path, version: browserVersion(path), launch_mode: 'external-explicit', wsl: isWsl() };
  }

  if (isWsl()) {
    const detected = candidates.find(([path]) => existsSync(path));
    if (!detected) {
      throw new Error('WSL2 requires an external Chrome/Chromium/Edge binary. Set PLAYWRIGHT_EXECUTABLE_PATH, CHROME_PATH, CHROMIUM_PATH, or EDGE_PATH.');
    }
    const [path, browser] = detected;
    return { name: 'auto-detected', browser, executable_path: path, version: browserVersion(path), launch_mode: 'external-wsl2', wsl: true };
  }

  if (env.CI) {
    return { name: 'playwright-managed', browser: 'Chromium', executable_path: null, version: 'managed by Playwright', launch_mode: 'managed-ci', wsl: false };
  }

  const detected = candidates.find(([path]) => existsSync(path));
  if (detected) {
    const [path, browser] = detected;
    return { name: 'auto-detected', browser, executable_path: path, version: browserVersion(path), launch_mode: 'external-local', wsl: false };
  }
  return { name: 'playwright-managed', browser: 'Chromium', executable_path: null, version: 'managed by Playwright', launch_mode: 'managed-local', wsl: false };
}

function parseArgs(argv) {
  const args = { json: false, evidence: '' };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === '--json') args.json = true;
    if (argv[index] === '--write-evidence') args.evidence = argv[index + 1] || '';
  }
  return args;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const args = parseArgs(process.argv.slice(2));
    const resolved = resolveLiteBrowser();
    if (args.evidence) {
      mkdirSync(dirname(args.evidence), { recursive: true });
      writeFileSync(args.evidence, `${JSON.stringify({ ...resolved, recorded_at: new Date().toISOString() }, null, 2)}\n`);
    }
    if (args.json || args.evidence) console.log(JSON.stringify(resolved, null, 2));
    else console.log(`${resolved.browser}: ${resolved.executable_path || 'Playwright managed'} (${resolved.version})`);
  } catch (error) {
    console.error(`Pocket Lab Lite browser preflight failed: ${error.message}`);
    process.exit(2);
  }
}
