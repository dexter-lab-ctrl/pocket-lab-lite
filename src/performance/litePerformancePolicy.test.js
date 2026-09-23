import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

function read(path) {
  return readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');
}

describe('Pocket Lab Lite UI performance policy guards', () => {
  it('does not add a second animation framework', () => {
    const pkg = JSON.parse(read('package.json'));
    for (const forbidden of ['framer-motion', 'gsap', 'animejs', 'motion']) {
      expect(pkg.dependencies?.[forbidden]).toBeUndefined();
      expect(pkg.devDependencies?.[forbidden]).toBeUndefined();
    }
    expect(pkg.dependencies?.['@react-spring/web']).toBeTruthy();
    expect(pkg.dependencies?.['@use-gesture/react']).toBeTruthy();
  });

  it('keeps GPU promotion scoped to active compositor motion', () => {
    const css = read('src/index.css');
    expect(css).toContain("[data-lite-perf-motion-active='true']");
    expect(css).toContain('will-change: transform, opacity');
    expect(css).not.toMatch(/\*\s*\{[^}]*will-change\s*:/s);
  });

  it('keeps real-runtime performance qualification read-only', () => {
    const live = read('tests/e2e/lite-performance-live.spec.ts');
    const android = read('scripts/dev/lite/qualify-ui-performance-android-cdp.mjs');
    const forbiddenActions = [
      'Run Safety Check',
      'Full Local Check',
      'Backup Now',
      'Restore Latest',
      'Restart Agent',
      'Add Device',
      'Change Password',
      'Remove Old Device',
    ];
    for (const action of forbiddenActions) {
      expect(live).not.toContain(action);
      expect(android).not.toContain(action);
    }
    expect(live).not.toMatch(/request\.(post|put|patch|delete)\s*\(/i);
    expect(android).not.toMatch(/request\.(post|put|patch|delete)\s*\(/i);
  });

  it('does not turn performance evidence into telemetry', () => {
    const runtime = read('src/performance/LitePerformanceRuntime.jsx');
    const helper = read('tests/e2e/lite-performance-helpers.ts');
    expect(runtime).not.toContain('sendBeacon');
    expect(runtime).not.toContain('fetch(');
    expect(helper).not.toContain('hostname');
    expect(helper).not.toContain('device_name');
    expect(helper).not.toContain('tailscale');
  });
});
