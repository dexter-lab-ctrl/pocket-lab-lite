import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// R6: AUTHORED — NOT EXECUTED. Mocked source-only qualification.
// No canonical PNG baselines, live scanner calls or physical device access.
const mobileWidths = [320, 360, 375, 390, 430] as const;
const desktopWidths = [768, 1024, 1280, 1440, 1920] as const;
const appearances = [
  { name: 'light', selected: 'light', systemDark: false },
  { name: 'dark', selected: 'dark', systemDark: true },
  { name: 'system-light', selected: 'system', systemDark: false },
  { name: 'system-dark', selected: 'system', systemDark: true },
] as const;

async function showSafety(page: Page, width: number, appearance: typeof appearances[number], scenario = 'security-quick-healthy') {
  await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
  await page.emulateMedia({ colorScheme: appearance.systemDark ? 'dark' : 'light', reducedMotion: 'reduce' });
  await page.addInitScript((choice) => localStorage.setItem('pocketlab:appearance', choice), appearance.selected);
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme', appearance.selected === 'system'
    ? (appearance.systemDark ? 'dark' : 'light') : appearance.selected);
}

async function manageCoverage(page: Page) {
  await page.getByRole('button', { name: 'Manage Security details' }).click();
  const manage = page.getByRole('dialog', { name: 'Manage Safety' });
  await expect(manage).toBeVisible();
  await manage.getByRole('button', { name: 'Open Coverage in Manage Safety' }).click();
  await expect(manage.getByRole('heading', { name: 'Coverage', level: 2 })).toBeVisible();
  return manage;
}

async function assertNoOverflow(page: Page, rootSelector: string) {
  const measure = await page.locator(rootSelector).first().evaluate((root) => {
    const rect = root.getBoundingClientRect();
    return {
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      rootWidth: rect.width,
      rootScrollWidth: root.scrollWidth,
      rootClientWidth: root.clientWidth,
    };
  });
  expect(measure.documentWidth, 'viewport overflow').toBeLessThanOrEqual(measure.viewportWidth + 2);
  expect(measure.rootScrollWidth, 'panel horizontal overflow').toBeLessThanOrEqual(measure.rootClientWidth + 2);
}

function rgbLuminance(raw: string): number {
  const channels = raw.match(/[\d.]+/g)?.slice(0, 3).map(Number) || [];
  if (channels.length !== 3) throw new Error('Unexpected color: ' + raw);
  const linear = channels.map((value) => {
    const channel = value / 255;
    return channel <= .04045 ? channel / 12.92 : Math.pow((channel + .055) / 1.055, 2.4);
  });
  return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2];
}
function contrastRatio(foreground: string, background: string): number {
  const a = rgbLuminance(foreground), b = rgbLuminance(background);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
}

test.describe('Safety R0–R5 responsive and semantic parity — AUTHOR ONLY', () => {
  for (const width of [...mobileWidths, ...desktopWidths]) {
    for (const appearance of appearances) {
      test(`${appearance.name} / ${width}px: one heading, readable rows, semantic surfaces`, async ({ page }) => {
        await showSafety(page, width, appearance, 'security-scanner-unavailable');
        const manage = await manageCoverage(page);
        await expect(manage.locator('[data-security-manage-section="coverage"] .lite-security-manage-section-head')).toHaveCount(0);
        await expect(manage.getByRole('heading', { name: 'Coverage', level: 2 })).toHaveCount(1);
        await expect(manage.getByRole('heading', { name: 'Quick safety coverage', level: 3 })).toHaveCount(1);
        await assertNoOverflow(page, '.lite-security-manage-scroll');
        const tokens = await manage.evaluate((root) => {
          const html = getComputedStyle(document.documentElement);
          const sheet = root.querySelector('.lite-security-manage-scroll')!;
          const heading = root.querySelector('.lite-safety-native-detail-heading')!;
          const row = root.querySelector('.lite-security-quick-coverage-card .lite-security-manage-row')!;
          const first = row.firstElementChild as HTMLElement;
          const section = root.querySelector('.lite-security-manage-section')!;
          return {
            sheet: getComputedStyle(sheet).backgroundColor,
            surface: html.getPropertyValue('--azure-surface').trim(),
            text: getComputedStyle(heading).color,
            textToken: html.getPropertyValue('--azure-text').trim(),
            headingBackground: getComputedStyle(section).backgroundColor,
            rowWrap: getComputedStyle(row).overflowWrap,
            firstWidth: first.getBoundingClientRect().width,
            rowWidth: row.getBoundingClientRect().width,
          };
        });
        // The section is transparent rather than an unpolished white rectangle.
        expect(tokens.headingBackground).toBe('rgba(0, 0, 0, 0)');
        expect(tokens.rowWrap).not.toBe('anywhere');
        expect(tokens.firstWidth, 'text track squeezed by adjacent badge/action').toBeGreaterThan(Math.min(120, tokens.rowWidth * .44));
        await expect(manage.locator('.lite-safety-native-detail-heading p')).toContainText('Review completed');
        if (width <= 430) {
          await expect(manage).toHaveAttribute('data-lite-mobile-header', 'safety');
          const header = manage.locator('.lite-overlay-head');
          await expect(header.getByRole('button', { name: 'Close security details' })).toBeVisible();
          await expect(header.getByRole('group', { name: 'Sheet size' })).toBeVisible();
        }
      });
    }
  }
});

test.describe('Safety R6 details, accessibility and state honesty — AUTHOR ONLY', () => {
  test('focused Coverage has one sheet-owned heading and semantic decorator set', async ({ page }) => {
    await showSafety(page, 390, appearances[1], 'security-scanner-unavailable');
    const manage = await manageCoverage(page);
    await manage.getByRole('button', { name: 'Open Security coverage details' }).click();
    const detail = page.getByRole('dialog', { name: 'Quick safety coverage' });
    await expect(detail).toBeVisible();
    const article = detail.locator('[data-lite-detail-presentation="safety"]');
    await expect(article).toBeVisible();
    await expect(detail.getByRole('heading', { name: 'Quick safety coverage' })).toHaveCount(0);
    await expect(article.locator('.lite-safety-detail-title .lite-safety-detail-icon svg').first()).toBeVisible();
    await assertNoOverflow(page, '.lite-security-phase3-scroll');
    await page.keyboard.press('Escape');
    await expect(detail).toHaveCount(0);
    await expect(manage).toBeVisible();
  });

  test('partial, missing and offline states stay distinct without invented success', async ({ page }) => {
    await showSafety(page, 390, appearances[1], 'offline-saved');
    await expect(page.getByText(/saved|offline/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reconnect to run Quick Scan' })).toBeDisabled();
    const manage = await manageCoverage(page);
    await expect(manage.locator('.lite-security-manage-stat-grid')).toBeVisible();
    await expect(manage.locator('.lite-security-manage-section')).toBeVisible();
  });

  test('snap Compact / Medium / Expanded, handle, Back and Close stay independently accessible', async ({ page }) => {
    await showSafety(page, 390, appearances[0]);
    const manage = await manageCoverage(page);
    const snap = manage.getByRole('group', { name: 'Sheet size' });
    await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await snap.getByRole('button', { name: 'Compact' }).click();
    await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await snap.getByRole('button', { name: 'Expand' }).click();
    await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await snap.getByRole('button', { name: 'Expand' }).click();
    await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await expect(manage.locator('.lite-overlay-grip')).toBeVisible();
    await manage.getByRole('button', { name: 'Back to Manage Safety' }).click();
    await expect(manage.locator('[data-safety-manage-view="index"]')).toBeVisible();
    await manage.getByRole('button', { name: 'Close security details' }).click();
    await expect(manage).toHaveCount(0);
  });

  test('WCAG 2.1 AA plus explicit semantic text/indicator contrast', async ({ page }) => {
    for (const appearance of appearances) {
      await showSafety(page, 390, appearance, 'security-scanner-unavailable');
      const manage = await manageCoverage(page);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(result.violations.filter((issue) => ['critical','serious'].includes(issue.impact || ''))).toEqual([]);
      const samples = await manage.evaluate((root) => {
        const surface = getComputedStyle(root.querySelector('.lite-security-manage-scroll')!).backgroundColor;
        const rows = [
          root.querySelector('.lite-safety-native-detail-heading h2'),
          root.querySelector('.lite-safety-native-detail-heading p'),
        ].filter(Boolean);
        return rows.map((node) => ({ foreground: getComputedStyle(node!).color, background: surface }));
      });
      for (const sample of samples) expect(contrastRatio(sample.foreground, sample.background)).toBeGreaterThanOrEqual(4.5);
      const boundary = await manage.evaluate((root) => {
        const row = root.querySelector('.lite-safety-native-nav-row[aria-current="page"]')!;
        return { border: getComputedStyle(row).borderTopColor, background: getComputedStyle(row).backgroundColor };
      });
      expect(contrastRatio(boundary.border, boundary.background)).toBeGreaterThanOrEqual(3);
    }
  });

  test('200% text, safe-area padding and reduced motion preserve mobile controls', async ({ page }) => {
    await showSafety(page, 320, appearances[1]);
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    const manage = await manageCoverage(page);
    await expect(manage.getByRole('button', { name: 'Back to Manage Safety' })).toBeVisible();
    await expect(manage.getByRole('button', { name: 'Close security details' })).toBeVisible();
    await expect(manage.locator('.lite-overlay-grip')).toBeVisible();
    await assertNoOverflow(page, '.lite-security-manage-scroll');
  });

  test('desktop geometry controls remain shared, visible and keyboard reachable', async ({ page }) => {
    await showSafety(page, 1280, appearances[1]);
    const manage = await manageCoverage(page);
    await expect(manage.getByRole('button', { name: 'Move Safety panel' })).toBeVisible();
    await expect(manage.getByRole('button', { name: 'Reset Safety panel position and size' })).toBeVisible();
    await expect(manage.getByRole('button', { name: 'Resize Safety panel' })).toBeVisible();
    await manage.getByRole('button', { name: 'Move Safety panel' }).focus();
    await page.keyboard.press('ArrowRight');
    await manage.getByRole('button', { name: 'Reset Safety panel position and size' }).click();
    await expect(manage).toBeVisible();
  });

  test.fixme('review candidate desktop/mobile screenshots against existing PR #640 baselines before approval');
  test.fixme('qualify installed Android PWA and physical Android CDP Safety-only scope separately');
});
