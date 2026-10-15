import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function rules(page: Page, scenario = 'rules-enabled') {
  await installScenario(page, scenario);
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page, 'rules');
}
async function manage(page: Page, scenario = 'rules-enabled') {
  await rules(page, scenario);
  const trigger = page.getByRole('button', { name: 'Manage Safety Rules' }).first();
  await trigger.click();
  const sheet = page.getByRole('dialog', { name: 'Manage Safety Rules' });
  await expect(sheet).toBeVisible();
  return { sheet, trigger };
}
test.describe('Premium Rules Center — mocked source-backed UX', () => {
  test('renders exactly three primary regions with no duplicate dashboard', async ({ page }) => {
    await rules(page);
    await expect(page.locator('.lite-rules-premium-hero')).toHaveCount(1);
    await expect(page.locator('.lite-rules-premium-journey')).toHaveCount(1);
    await expect(page.getByLabel('Latest Decision')).toHaveCount(1);
    await expect(page.locator('.lite-rules-key-areas')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: /How Pocket Lab protects a change/i })).toBeVisible();
  });
  test('educational stages select via keyboard without auto-progress', async ({ page }) => {
    await rules(page);
    const stage = page.getByRole('button', { name: /Check Evaluate/i });
    await stage.focus();
    await page.keyboard.press('Enter');
    await expect(stage).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByText(/evaluates the applicable Rules/i)).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(stage).toHaveAttribute('aria-expanded', 'false');
  });
  test('opens and closes Manage with focus restoration', async ({ page }) => {
    const { sheet, trigger } = await manage(page);
    await sheet.getByRole('button', { name: 'Protections', exact: true }).click();
    await expect(sheet).toContainText(/Protected actions/i);
    await page.keyboard.press('Escape');
    await expect(sheet).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });
  test('shows an actual latest decision or a truthful empty state, not a placeholder approval', async ({ page }) => {
    await rules(page, 'rules-present');
    const latest = page.getByLabel('Latest Decision');
    await expect(latest).toBeVisible();
    const explain = latest.getByRole('button', { name: 'Explain this' });
    if (await explain.count()) {
      await explain.click();
      const detail = page.getByRole('dialog', { name: 'Decision Insight' });
      await expect(detail).toContainText(/Who requested it/i);
      await expect(detail).toContainText(/What would change/i);
      await expect(detail).toContainText(/Why this decision/i);
      await expect(detail).toContainText(/What can happen next/i);
      await expect(detail).toContainText(/not establish|execution/i);
      await page.keyboard.press('Escape');
      await expect(explain).toBeFocused();
    } else {
      await expect(latest).toContainText(/No recorded decisions/i);
    }
  });
  test('moves decision history and server policy summaries into Manage', async ({ page }) => {
    const { sheet } = await manage(page, 'rules-present');
    await sheet.getByRole('button', { name: 'Decisions', exact: true }).click();
    await expect(sheet).toContainText(/Decision History/i);
    await sheet.getByRole('button', { name: 'Policies', exact: true }).click();
    await expect(sheet).toContainText(/Policy summaries/i);
  });
  test('keeps Enterprise role sections inside the same Manage, not on the default screen', async ({ page }) => {
    const { sheet } = await manage(page, 'rules-enterprise-owner');
    await expect(page.getByRole('heading', { name: 'Rules governance' })).toHaveCount(0);
    await sheet.getByRole('button', { name: 'Test a Change' }).click();
    await expect(sheet).toContainText('This is a simulation. No real permission or system change is granted.');
    await sheet.getByRole('button', { name: 'Requests' }).click();
    await expect(sheet).toContainText(/request/i);
    await sheet.getByRole('button', { name: 'Revision & Recovery' }).click();
    await expect(sheet).toContainText(/Revision and recovery/i);
  });
  test('keeps read-only Enterprise members away from mutation controls', async ({ page }) => {
    const { sheet } = await manage(page, 'rules-enterprise-viewer');
    await sheet.getByRole('button', { name: 'Policies' }).click();
    await expect(sheet).toContainText(/not available to this role/i);
    await expect(sheet.getByRole('button', { name: 'Create Rules candidate' })).toHaveCount(0);
  });
  test('does not promote degraded protection into ready', async ({ page }) => {
    await rules(page, 'rules-validation-error');
    await expect(page.locator('[data-rules-protection-state]')).not.toHaveAttribute('data-rules-protection-state', 'ready');
  });
  test('respects reduced-motion and does not animate the educational stages', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await rules(page);
    const duration = await page.locator('.lite-rules-journey-track button').first().evaluate(el => getComputedStyle(el).transitionDuration);
    expect(duration.split(',').every(part => part.trim() === '0s')).toBeTruthy();
  });
  for (const width of [320,375,390,430,768,1024,1440]) {
    test('no horizontal clipping at ' + width + 'px and large text', async ({ page }) => {
      await page.setViewportSize({ width, height: 850 });
      await rules(page, 'rules-validation-error');
      await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      const sheet = await page.getByRole('button', { name: 'Manage Safety Rules' }).click().then(() => page.getByRole('dialog', { name: 'Manage Safety Rules' }));
      await expect(sheet).toBeVisible();
      expect(await sheet.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    });
  }
  test('Axe serious/critical in Rules hero, Manage and Decision Insight', async ({ page }) => {
    await rules(page, 'rules-present');
    const scan = async () => {
      const report = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
      expect(report.violations.filter(item => ['serious','critical'].includes(item.impact || ''))).toEqual([]);
    };
    await scan();
    await page.getByRole('button', { name: 'Manage Safety Rules' }).click();
    await scan();
    await page.keyboard.press('Escape');
    const explain = page.getByLabel('Latest Decision').getByRole('button', { name: 'Explain this' });
    if (await explain.count()) { await explain.click(); await scan(); }
  });
});
