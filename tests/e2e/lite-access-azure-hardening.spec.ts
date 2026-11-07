// Azure Horizon Access P0–P7 — AUTHORED, NOT EXECUTED.
// No visual snapshot baselines are created or approved by this source change.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const widths = [320, 360, 390, 430, 768, 1024, 1440] as const;
const themes = ['light', 'dark', 'system'] as const;

async function openAccess(page: Page, scenario: string, theme: string, width: number) {
  await page.setViewportSize({ width, height: width <= 430 ? 844 : 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page, 'identity');
}

async function metrics(page: Page) {
  return page.evaluate(() => {
    const selectors = [
      '.lite-access-page', '.lite-page-header', '.lite-access-hero',
      '.lite-access-settings-card', '.lite-access-settings-row',
      '.lite-access-education-link', '.lite-identity-grid',
      '.lite-identity-card', '.lite-identity-form-field',
      '.lite-identity-form-field input',
    ];
    return Object.fromEntries(selectors.map((selector) => {
      const element = document.querySelector(selector);
      if (!element) return [selector, null];
      const css = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return [selector, {
        width: Math.round(box.width * 10) / 10,
        height: Math.round(box.height * 10) / 10,
        padding: css.padding,
        margin: css.margin,
        gap: css.gap,
        gridTemplateColumns: css.gridTemplateColumns,
        borderWidth: css.borderWidth,
        borderRadius: css.borderRadius,
        fontSize: css.fontSize,
        lineHeight: css.lineHeight,
      }];
    }));
  });
}

test.describe('Access P0–P7 mock qualification, source authored only', () => {
  for (const scenario of ['identity-summary', 'identity-premium-signed-out']) {
    for (const width of widths) {
      test(`light/dark geometry parity: ${scenario}, ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: width <= 430 ? 844 : 900 });
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await installScenario(page, scenario);
        await page.goto('/?screen=identity');
        await page.evaluate(() => localStorage.setItem('pocketlab:appearance', 'light'));
        await page.reload();
        await waitForLiteScreenToSettle(page, 'identity');
        await expect(page.locator('[data-lite-screen-id="identity"]')).toBeVisible();
        const light = await metrics(page);
        await page.evaluate(() => localStorage.setItem('pocketlab:appearance', 'dark'));
        await page.reload();
        await waitForLiteScreenToSettle(page, 'identity');
        const dark = await metrics(page);
        // Compare geometry, never colors or color-dependent shadows.
        expect(dark).toEqual(light);
        const bounds = await page.locator('[data-lite-screen-id="identity"]').evaluate((el) => ({
          scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
        }));
        expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.clientWidth + 2);
      });
    }
  }

  for (const theme of themes) {
    test(`education entry, disclosure and keyboard semantics: ${theme}`, async ({ page }) => {
      await openAccess(page, 'identity-premium-multiple', theme, 390);
      await page.getByRole('button', { name: /How Access works/i }).click();
      const explain = page.getByRole('dialog', { name: /Understand your access/i });
      await expect(explain.getByText('Make protected changes')).toBeVisible();
      await explain.getByRole('button', { name: /Close/i }).click();
      await page.getByRole('button', { name: 'Manage Access' }).click();
      const manage = page.getByRole('dialog', { name: /Manage access/i });
      await manage.getByRole('button', { name:'Passkeys', exact:true }).click();
      await manage.getByRole('button', { name:/Second passkey/i }).click();
      const detail = page.getByRole('dialog', { name: /Access Details/i });
      const nativeDisclosure = detail.locator('details.lite-ux-technical-facts');
      await expect(nativeDisclosure).not.toHaveAttribute('open');
      await nativeDisclosure.locator('summary').press('Enter');
      await expect(nativeDisclosure).toHaveAttribute('open');
      await expect(nativeDisclosure.locator('.lite-shared-disclosure-chevron')).toHaveCount(1);
      await page.keyboard.press('Escape');
      await expect(detail).toBeHidden();
    });
  }

  test('signed-out education is available without implied permission', async ({ page }) => {
    await openAccess(page, 'identity-premium-signed-out', 'dark', 390);
    await page.getByRole('button', { name:/How Access works/i }).click();
    const dialog = page.getByRole('dialog', { name:/How Access works/i });
    await expect(dialog).toContainText('Sign in to review your account');
    await expect(dialog).toContainText('server authorization');
  });

  test('mobile Manage shares Compact/Medium/Expanded, isolated from form interactions', async ({ page }) => {
    await openAccess(page, 'identity-premium-multiple', 'light', 390);
    await page.getByRole('button', { name:'Manage Access' }).click();
    const dialog = page.getByRole('dialog', { name:/Manage access/i });
    await dialog.getByRole('button', { name:'Compact', exact:true }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await dialog.getByRole('button', { name:'Expand', exact:true }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await dialog.getByRole('button', { name:'Expand', exact:true }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await dialog.getByRole('button', { name:'Recovery', exact:true }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await expect(dialog).toContainText('Recovery');
  });

  test('desktop Manage and nested Details retain separate draggable geometry and Close', async ({ page }) => {
    await openAccess(page, 'identity-premium-multiple', 'dark', 1024);
    await page.getByRole('button', { name:'Manage Access' }).click();
    const manage = page.getByRole('dialog', { name:/Manage access/i });
    await expect(manage).toHaveAttribute('data-lite-identity-manage-layout', 'desktop-movable');
    await manage.getByRole('button', { name:'Passkeys', exact:true }).click();
    await manage.getByRole('button', { name:/Second passkey/i }).click();
    const detail = page.getByRole('dialog', { name:/Access Details/i });
    await expect(detail.locator('.lite-access-detail-intro')).toBeVisible();
    await detail.getByRole('button', { name:/Close/i }).click();
    await expect(detail).toBeHidden();
    await expect(manage).toBeVisible();
  });

  test('restricted Enterprise and saved-state presentation remain truthful', async ({ page }) => {
    await openAccess(page, 'identity-enterprise-viewer', 'dark', 390);
    await page.getByRole('button', { name:/How Access works/i }).click();
    await expect(page.getByRole('dialog', { name:/Understand your access/i })).toContainText('Enterprise Mode');
  });

  test('signed-out and signed-in accessibility regressions have no serious or critical violations', async ({ page }) => {
    for (const scenario of ['identity-premium-signed-out', 'identity-summary']) {
      await openAccess(page, scenario, 'dark', 390);
      const violations = (await new AxeBuilder({ page }).include('[data-lite-screen-id="identity"]').analyze())
        .violations.filter((item) => ['serious','critical'].includes(item.impact || ''));
      expect(violations).toEqual([]);
    }
  });

  test('200% text zoom and reduced motion preserve horizontal containment', async ({ page }) => {
    await openAccess(page, 'identity-premium-long-text', 'light', 320);
    await page.addStyleTag({ content: 'html { font-size: 200%; }' });
    const overflow = await page.locator('[data-lite-screen-id="identity"]').evaluate((el) =>
      el.scrollWidth > el.clientWidth + 2);
    expect(overflow).toBe(false);
  });
});
