// P6 mocked-only browser qualification assets. They use synthetic read-only
// fixtures and are kept separate from physical Android evidence.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const viewportMatrix = [320, 360, 375, 390, 430, 768, 1280, 1440] as const;
const themes = ['light', 'dark', 'system'] as const;
type Theme = (typeof themes)[number];

async function openSafety(page: Page, scenario = 'security-quick-healthy', theme: Theme = 'dark', width = 390) {
  await page.setViewportSize({ width, height: width <= 430 ? 844 : 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
}

async function manageSection(page: Page, section = 'Checks') {
  await page.getByRole('button', { name: 'Manage Security details' }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
  await dialog.getByRole('button', { name: `Open ${section} in Manage Safety` }).click();
  return dialog;
}

test.describe('Safety Azure Horizon global overlay — mocked qualification', () => {
  for (const theme of themes) for (const width of viewportMatrix) {
    test(`token-backed overlay, viewport containment and theme geometry: ${theme}, ${width}px`, async ({ page }) => {
      await openSafety(page, 'security-quick-healthy', theme, width);
      const dialog = await manageSection(page, 'Checks');
      await expect(dialog).toBeVisible();
      const evidence = await dialog.evaluate((element) => {
        const cs = getComputedStyle(element);
        const root = getComputedStyle(document.documentElement);
        const rect = element.getBoundingClientRect();
        const surface = root.getPropertyValue('--azure-surface').trim();
        const scratch = document.createElement('span');
        scratch.style.backgroundColor = surface;
        document.body.appendChild(scratch);
        const resolved = getComputedStyle(scratch).backgroundColor;
        scratch.remove();
        return {
          actualSurface: cs.backgroundColor, expectedSurface: resolved,
          left: rect.left, right: rect.right, width: window.innerWidth,
          color: cs.color, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
        };
      });
      expect(evidence.actualSurface).toBe(evidence.expectedSurface);
      expect(evidence.left).toBeGreaterThanOrEqual(-2);
      expect(evidence.right).toBeLessThanOrEqual(evidence.width + 2);
      expect(evidence.scrollWidth).toBeLessThanOrEqual(evidence.clientWidth + 2);
      await expect(dialog.getByText('Sensitive values and private paths are hidden from this view.')).toBeVisible();
    });
  }

  test('pending scanner outcomes never imply a completed clean scan', async ({ page }) => {
    await openSafety(page, 'security-full-running', 'dark', 390);
    const dialog = await manageSection(page, 'Checks');
    await expect(dialog.locator('[data-safety-status-hierarchy="true"]')).toBeVisible();
    await expect(dialog.getByText('No critical findings reported')).toHaveCount(0);
  });

  test('Compact and Expand are explicit shared mode controls with retained content', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'dark', 390);
    const dialog = await manageSection(page, 'Checks');
    await dialog.getByRole('button', { name: 'Compact' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await expect(dialog.getByRole('button', { name: 'Compact', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await dialog.getByRole('button', { name: 'Expand' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await expect(dialog.getByRole('button', { name: 'Expand', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(dialog).not.toContainText('DRAG HANDLE TO RESIZE');
  });

  test('desktop keyboard move, resize, Escape and focus return stay accessible', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'light', 1280);
    const manage = page.getByRole('button', { name: 'Manage Security details' });
    await manage.click();
    const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
    await dialog.getByRole('button', { name: 'Move Safety panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    await dialog.getByRole('button', { name: 'Resize Safety panel' }).focus();
    await page.keyboard.press('ArrowDown');
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(manage).toBeFocused();
  });

  test('history retains persisted text status and readable timestamps', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'dark', 430);
    const dialog = await manageSection(page, 'History');
    await dialog.getByRole('button', { name: 'Open Security history details' }).click();
    const detail = page.getByRole('dialog', { name: /Safety history/i }).last();
    await expect(detail).toBeVisible();
    const toggle = detail.getByRole('button', { name: /Recent safety checks/i });
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(detail.locator('[data-security-history-cursor-v2="true"]')).toBeVisible();
  });

  test('Quick coverage exclusions have one group disclosure, not repeated subtitles', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'light', 320);
    const dialog = await manageSection(page, 'Coverage');
    await dialog.getByRole('button', { name: 'Open Security coverage details' }).click();
    const details = page.getByRole('dialog', { name: /coverage/i }).last();
    const disclosure = details.getByRole('button', { name: /Skipped by Quick Safety Check/ });
    await disclosure.click();
    await expect(disclosure).toHaveAttribute('aria-expanded', 'true');
    await expect(details.locator('[data-lite-safety-coverage-list="true"]')).toBeVisible();
    await expect(details.getByText('skipped by quick profile')).toHaveCount(0);
  });

  test('technical details keep sensitive paths and raw logs out of rendered metadata', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'dark', 390);
    const dialog = await manageSection(page, 'Technical details');
    await dialog.getByRole('button', { name: 'Open safe Security technical details' }).click();
    const details = page.getByRole('dialog', { name: /Safe technical details/i }).last();
    const toggle = details.getByRole('button', { name: 'Technical details' });
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(details).not.toContainText('/data/data/com.termux');
    await expect(details).not.toContainText('raw scanner log');
  });
});

// These visual states are reviewed mocked baselines, separate from physical
// Android appearance evidence.
test.describe('Safety unification screenshots — reviewed mocked baselines', () => {
  for (const theme of themes) for (const width of [320, 390, 768, 1280] as const) {
    test(`shared Safety Manage state: ${theme}, ${width}px`, async ({ page }) => {
      await openSafety(page, 'security-quick-healthy', theme, width);
      const dialog = await manageSection(page, 'Checks');
      await expect(dialog).toHaveScreenshot(`safety-unified-${theme}-checks-${width}.png`, { animations: 'disabled' });
    });
  }
});


test.describe('Safety accessibility and nested visual evidence — qualification', () => {
  for (const theme of ['light', 'dark'] as const) {
    test(`WCAG AA candidate: ${theme} 390px Manage and nested Technical details`, async ({ page }) => {
      await openSafety(page, 'security-quick-healthy', theme, 390);
      const dialog = await manageSection(page, 'Technical details');
      await expect(dialog).toBeVisible();
      const candidate = await new AxeBuilder({ page }).include('[data-lite-overlay-portal="true"]').analyze();
      const blocking = candidate.violations.filter(item => ['serious', 'critical'].includes(item.impact || ''));
      expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
      const controls = dialog.locator('.lite-overlay-close, .lite-sheet-mobile-snap-actions button');
      const count = await controls.count();
      for (let i = 0; i < count; i += 1) {
        const box = await controls.nth(i).boundingBox();
        expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
      }
    });
  }

  test('System mode re-resolves surface tokens while a portalled Safety sheet remains open', async ({ page }) => {
    await openSafety(page, 'security-quick-healthy', 'system', 390);
    const dialog = await manageSection(page, 'Checks');
    await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
    const dark = await dialog.evaluate(element => getComputedStyle(element).backgroundColor);
    await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
    await expect.poll(async () => dialog.evaluate(element => getComputedStyle(element).backgroundColor)).not.toBe(dark);
  });

  for (const theme of themes) for (const width of [320, 390, 1280] as const) {
    for (const section of ['History', 'Coverage', 'Technical details'] as const) {
      test(`nested ${section} visual state: ${theme} ${width}px`, async ({ page }) => {
        await openSafety(page, 'security-quick-healthy', theme, width);
        const manage = await manageSection(page, section);
        const actionName = section === 'History' ? 'Open Security history details'
          : section === 'Coverage' ? 'Open Security coverage details'
            : 'Open safe Security technical details';
        await manage.getByRole('button', { name: actionName }).click();
        const detail = page.getByRole('dialog').last();
        await expect(detail).toBeVisible();
        await expect(detail.locator('[data-security-phase2-progressive-details="true"]')).toBeVisible();
        await expect(detail).toHaveScreenshot(`safety-unified-${theme}-${section.toLowerCase().replace(' ', '-')}-${width}.png`, { animations: 'disabled' });
      });
    }
  }
});
