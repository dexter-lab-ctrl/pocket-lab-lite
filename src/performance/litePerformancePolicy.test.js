import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  LITE_PERFORMANCE_INTERACTIONS,
  LITE_PERFORMANCE_PRIMITIVES,
  LITE_PERFORMANCE_SCREENS,
} from './litePerformanceBudget.js';
import { LITE_UI_PERFORMANCE_MATRIX } from './litePerformanceMatrix.js';

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

  it('covers every Lite tab and shared UI primitive without blanket memoization', () => {
    expect(LITE_PERFORMANCE_SCREENS).toEqual([
      'home',
      'catalog',
      'devices',
      'security',
      'identity',
      'rules',
      'recovery',
    ]);

    const primitiveSources = [
      read('src/components/ui.jsx'),
      read('src/lite/LiteUi.jsx'),
      read('src/lite/LiteOverlay.jsx'),
      read('src/lite/LiteApp.jsx'),
      read('src/lite/LiteToastHost.jsx'),
      read('src/lite/LiteActionProgress.jsx'),
    ].join('\n');
    for (const primitive of LITE_PERFORMANCE_PRIMITIVES) {
      expect(primitiveSources).toContain(`data-lite-perf-primitive="${primitive}"`);
    }

    const registry = read('src/lite/liteScreenRegistry.js');
    expect(registry).toContain('memoLiteScreen');
    expect(registry).toContain('React.memo(Component)');
    expect(read('src/components/ui.jsx')).not.toContain('React.memo(');
    expect(read('src/lite/LiteUi.jsx')).not.toContain('React.memo(');
    expect(read('src/lite/LiteOverlay.jsx')).not.toContain('React.memo(');
  });

  it('keeps every declared performance interaction tied to a qualified scenario', () => {
    const contractSource = read('tests/e2e/lite-performance-contract.ts');
    const qualified = [...contractSource.matchAll(/^\s*'([^']+)',\s*$/gm)].map((match) => match[1]);
    expect(qualified).toEqual(LITE_PERFORMANCE_INTERACTIONS);

    const spec = read('tests/e2e/lite-performance.spec.ts');
    for (const interaction of LITE_PERFORMANCE_INTERACTIONS) {
      expect(spec).toContain(`interactionId('${interaction}'`);
    }
  });

  it('keeps the deep UI matrix on every Lite screen and inside the declared interaction registry', () => {
    expect(new Set(LITE_UI_PERFORMANCE_MATRIX.map((item) => item.screen))).toEqual(new Set(LITE_PERFORMANCE_SCREENS));
    expect(LITE_UI_PERFORMANCE_MATRIX.length).toBeGreaterThanOrEqual(LITE_PERFORMANCE_SCREENS.length);
    for (const item of LITE_UI_PERFORMANCE_MATRIX) {
      expect(item.nestedSurface).toBeTruthy();
      expect(item.authorityRequired).toBeTruthy();
      expect(item.safeExecutionMode).toBeTruthy();
      expect(item.evidenceId).toMatch(/^[a-z0-9.-]+$/);
      expect(LITE_PERFORMANCE_INTERACTIONS).toContain(item.interaction);
    }
  });

  it('keeps GPU promotion scoped to active compositor motion', () => {
    const css = read('src/index.css');
    expect(css).toContain("[data-lite-perf-motion-active='true']");
    expect(css).toContain('will-change: transform, opacity');
    expect(css).not.toMatch(/\*\s*\{[^}]*will-change\s*:/s);
  });

  it('keeps qualification-only screen motion out of the measured frame path', () => {
    const css = read('src/index.css');
    expect(css).toContain("html[data-lite-perf-mode='true'] .theme-pocket-lite-daylight .pocket-main");
    expect(css).toContain('animation: none !important;');
    expect(css).toContain('transition: none !important;');
    expect(css).toContain('normal product motion');
    expect(css).toContain('unchanged');
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
