import { mkdir, writeFile } from 'node:fs/promises';
import { resolveLiteBrowser } from '../../scripts/dev/lite/resolve-browser.mjs';

export default async function globalSetup() {
  const browser = resolveLiteBrowser();
  await mkdir('.pocketlab-dev/validation', { recursive: true });
  await writeFile(
    '.pocketlab-dev/validation/playwright-browser.json',
    `${JSON.stringify({ ...browser, recorded_at: new Date().toISOString() }, null, 2)}\n`,
    'utf8',
  );
}
