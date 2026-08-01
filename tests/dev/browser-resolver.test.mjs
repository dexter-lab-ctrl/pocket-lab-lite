import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveLiteBrowser } from '../../scripts/dev/lite/resolve-browser.mjs';

test('explicit browser executable is honored', () => {
  const result = resolveLiteBrowser({ env: { PLAYWRIGHT_EXECUTABLE_PATH: '/bin/sh' } });
  assert.equal(result.executable_path, '/bin/sh');
  assert.equal(result.launch_mode, 'external-explicit');
});

test('missing explicit browser fails closed', () => {
  assert.throws(
    () => resolveLiteBrowser({ env: { PLAYWRIGHT_EXECUTABLE_PATH: '/definitely/missing/pocketlab-browser' } }),
    /missing executable/,
  );
});
