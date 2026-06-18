#!/usr/bin/env node
import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import {
  existsSync,
  readFileSync,
  writeFileSync,
  mkdirSync,
  rmSync,
} from 'node:fs';
import { spawn } from 'node:child_process';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const STORYBOOK_DIR = join(ROOT, 'storybook-static');
const STORYBOOK_INDEX = join(STORYBOOK_DIR, 'index.json');
const UI_METADATA = join(ROOT, 'src/stories/tier9UiScreens.json');
const OUT_DIR = join(ROOT, 'docs/product/generated/ui-screenshots');
const MANIFEST_PATH = join(ROOT, 'docs/product/generated/ui-screenshot-manifest.json');

const HOST = '127.0.0.1';
const PORT = Number(process.env.POCKETLAB_STORYBOOK_SCREENSHOT_PORT || '6099');
const BASE_URL = `http://${HOST}:${PORT}`;
const VIEWPORT = { width: 1365, height: 900 };

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function kebab(value) {
  return String(value)
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .replace(/[^A-Za-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function startServer() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      'python3',
      ['-m', 'http.server', String(PORT), '--bind', HOST, '--directory', STORYBOOK_DIR],
      { stdio: ['ignore', 'pipe', 'pipe'] },
    );

    child.stdout.on('data', (chunk) => {
      process.stdout.write(`[storybook-static] ${chunk}`);
    });

    child.stderr.on('data', (chunk) => {
      process.stderr.write(`[storybook-static] ${chunk}`);
    });

    child.on('exit', (code) => {
      if (code !== null && code !== 0) {
        reject(
          new Error(
            `storybook-static server exited with ${code}. ` +
              `Port ${PORT} may already be in use. ` +
              `Run: lsof -ti :${PORT} | xargs -r kill`,
          ),
        );
      }
    });

    const startedAt = Date.now();

    const probe = async () => {
      try {
        const response = await fetch(`${BASE_URL}/index.html`, {
          cache: 'no-store',
        });
        if (response.ok) {
          resolve(child);
          return;
        }
      } catch {
        // retry
      }

      if (Date.now() - startedAt > 15000) {
        child.kill();
        reject(new Error(`Timed out starting Storybook static server on ${BASE_URL}`));
        return;
      }

      setTimeout(probe, 250);
    };

    probe();
  });
}

function getScreens(metadata) {
  if (Array.isArray(metadata)) return metadata;
  if (Array.isArray(metadata.screens)) return metadata.screens;
  throw new Error('src/stories/tier9UiScreens.json must contain a screens array.');
}

function storyNamesForScreen(screen) {
  if (Array.isArray(screen.stories)) return screen.stories;
  if (Array.isArray(screen.storyExports)) return screen.storyExports;
  if (Array.isArray(screen.story_exports)) return screen.story_exports;
  return [];
}

function buildStoryIndex(indexJson) {
  const entries = Object.values(indexJson.entries || indexJson.stories || {});
  return entries.filter((entry) => {
    const importPath = entry.importPath || '';
    const title = entry.title || '';
    return importPath.includes('PocketLabTabs.stories.jsx') || title.includes('UI Evidence Screens');
  });
}

function resolveStoryId(entries, storyName) {
  const suffix = `--${kebab(storyName)}`;

  const byIdSuffix = entries.find((entry) => String(entry.id || '').endsWith(suffix));
  if (byIdSuffix?.id) return byIdSuffix.id;

  const byName = entries.find((entry) => kebab(entry.name || '') === kebab(storyName));
  if (byName?.id) return byName.id;

  const byExport = entries.find((entry) => kebab(entry.exportName || '') === kebab(storyName));
  if (byExport?.id) return byExport.id;

  throw new Error(
    `Could not resolve Storybook story id for ${storyName}. ` +
      `Expected an index.json entry ending with ${suffix}.`,
  );
}

function resolveChromePath() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ].filter(Boolean);

  return candidates.find((candidate) => existsSync(candidate));
}

async function waitForStoryContent(page, storyId) {
  await page.waitForSelector('#storybook-root', {
    state: 'attached',
    timeout: 30000,
  });

  await page.waitForFunction(() => {
    const root = document.querySelector('#storybook-root');
    if (!root) return false;

    const text = (root.textContent || '').trim();
    const hasRenderedElement = root.children.length > 0;
    const hasUsefulText =
      text.length > 20 &&
      !text.includes("Couldn't find story matching") &&
      !text.includes('The component failed to render properly');

    return hasRenderedElement && hasUsefulText;
  }, { timeout: 30000 });

  await page.evaluate(() =>
    document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve(),
  );

  await page.waitForTimeout(1000);

  const bodyClass = await page.locator('body').getAttribute('class').catch(() => '');
  const bodyText = await page.locator('body').innerText({ timeout: 3000 }).catch(() => '');

  if ((bodyClass || '').includes('sb-show-errordisplay') || bodyText.includes("Couldn't find story matching")) {
    throw new Error(
      `Storybook rendered an error page for ${storyId}. ` +
        `bodyClass=${bodyClass || '<none>'}. ` +
        `Page text: ${bodyText.slice(0, 1200)}`,
    );
  }

  if (bodyText.includes('Find components') && bodyText.includes('Storybook')) {
    throw new Error(
      `Capture target is Storybook manager shell, not iframe story content for ${storyId}.`,
    );
  }
}

async function capture() {
  if (!existsSync(STORYBOOK_INDEX)) {
    throw new Error('storybook-static/index.json not found. Run npm run build-storybook first.');
  }

  if (!existsSync(UI_METADATA)) {
    throw new Error('src/stories/tier9UiScreens.json not found.');
  }

  const metadata = readJson(UI_METADATA);
  const screens = getScreens(metadata);
  const indexJson = readJson(STORYBOOK_INDEX);
  const entries = buildStoryIndex(indexJson);

  if (!entries.length) {
    throw new Error('No Storybook UI documentation Storybook entries found in storybook-static/index.json.');
  }

  rmSync(OUT_DIR, { recursive: true, force: true });
  mkdirSync(OUT_DIR, { recursive: true });

  const server = await startServer();

  const browser = await chromium.launch({
    headless: true,
    executablePath: resolveChromePath(),
  });

  const captured = [];

  try {
    const context = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: 1,
      serviceWorkers: 'block',
    });

    await context.addInitScript(() => {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations?.().then((registrations) => {
          for (const registration of registrations) {
            registration.unregister();
          }
        });
      }
    });

    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error(`[storybook-console:error] ${msg.text()}`);
      }
    });

    for (const screen of screens) {
      const screenId = screen.id || kebab(screen.title || screen.name || screen.component || 'screen');
      const storyNames = storyNamesForScreen(screen);

      for (const storyName of storyNames) {
        const storyId = resolveStoryId(entries, storyName);
        const fileName = `${kebab(screenId)}__${kebab(storyName)}.png`;
        const absolutePath = join(OUT_DIR, fileName);
        const repositoryPath = relative(ROOT, absolutePath).replaceAll('\\', '/');
        const docsRelativePath = relative(join(ROOT, 'docs/product'), absolutePath).replaceAll('\\', '/');

        const url =
          `${BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}` +
          `&viewMode=story&globals=&args=&singleStory=true`;

        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
        await waitForStoryContent(page, storyId);

        const root = page.locator('#storybook-root');

        await root.screenshot({
          path: absolutePath,
          animations: 'disabled',
        });

        const hash = sha256File(absolutePath);

        captured.push({
          screen_id: screenId,
          screen_title: screen.title || screen.name || screenId,
          simple_label: screen.simpleLabel || screen.simple_label || '',
          component: screen.component || '',
          story_export: storyName,
          story_id: storyId,
          story_url: `iframe.html?id=${storyId}&viewMode=story`,
          screenshot: docsRelativePath,
          repository_path: repositoryPath,
          sha256: hash,
          viewport: VIEWPORT,
        });

        console.log(`Captured ${screenId}/${storyName} -> ${repositoryPath}`);
      }
    }
  } finally {
    await browser.close();
    server.kill();
  }

  const manifest = {
    tier: 'Storybook Screenshot Evidence for MkDocs',
    capture_mode: 'storybook-static iframe screenshot with deterministic FastAPI mocks',
    runtime_scope:
      'documentation-only Storybook iframe capture; deterministic mock FastAPI data; no direct NATS access; no frontend shell execution',
    generated_at_utc: new Date().toISOString(),
    storybook_index: 'storybook-static/index.json',
    screenshot_count: captured.length,
    screen_count: new Set(captured.map((item) => item.screen_id)).size,
    viewport: VIEWPORT,
    screenshots: captured,
  };

  writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  console.log(`Wrote ${relative(ROOT, MANIFEST_PATH)}`);
  console.log(
    `Captured ${manifest.screenshot_count} Storybook screenshot evidence Storybook screenshots across ${manifest.screen_count} screens.`,
  );
}

capture().catch((error) => {
  console.error(error);
  process.exit(1);
});
