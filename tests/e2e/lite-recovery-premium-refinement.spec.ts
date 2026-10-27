import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function recovery(page: Page, scenario = 'recovery-verified') {
  await installScenario(page, scenario);
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
}
test.describe('Premium Recovery Center — mocked UX, safety and accessibility', () => {
  test('has one hero, four-stage journey and bounded timeline', async ({ page }) => {
    await recovery(page);
    await expect(page.locator('.lite-recovery-premium-protection')).toHaveCount(1);
    await expect(page.locator('.lite-recovery-premium-journey')).toHaveCount(1);
    await expect(page.locator('.lite-recovery-premium-timeline')).toHaveCount(1);
    await expect(page.locator('.lite-recovery-premium-stage-grid button')).toHaveCount(4);
    await expect(page.locator('.lite-recovery-premium-timeline-list li')).not.toHaveCount(4);
  });
  test('Journey selection is purely educational and keyboard accessible', async ({ page }) => {
    await recovery(page);
    const btn = page.getByRole('button',{name:/Verify/}).filter({has:page.locator('svg')}).first();
    await btn.focus();
    await page.keyboard.press('Enter');
    await expect(btn).toHaveAttribute('aria-expanded','true');
    await expect(page.getByText(/Check the integrity of a saved backup/i)).toBeVisible();
  });
  test('opens shared Manage and preserves focus return', async ({ page }) => {
    await recovery(page);
    const trigger = page.getByRole('button',{name:'Manage Recovery'});
    await trigger.click();
    const dialog = page.getByRole('dialog',{name:/Manage backups and recovery/i});
    await expect(dialog).toBeVisible();
    await dialog.getByRole('tab',{name:'Restore'}).click();
    await expect(dialog.getByLabel('Restore impact preview')).toBeVisible();
    await expect(dialog).toContainText(/explicit confirmation/i);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });
  test('opens protected restore confirmation and cancels without dispatching restore', async ({ page }) => {
    await recovery(page, 'recovery-preview-ready');
    const restoreRequests: string[] = [];
    page.on('request', (request) => {
      if (request.method() !== 'GET' && /\/api\/lite\/recovery\/restore(?:$|\/)/.test(request.url())) {
        restoreRequests.push(request.url());
      }
    });
    const detailsResponse = page.waitForResponse((response) => response.url().endsWith('/api/lite/recovery/details') && response.status() === 200);
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const manage = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await manage.getByRole('tab', { name: 'Restore' }).click();
    const restoreRow = manage.locator('.lite-recovery-manage-action-row').filter({ hasText: 'Restore selected backup' });
    await detailsResponse;
    const restoreButton = restoreRow.getByRole('button', { name: 'Restore', exact: true });
    await expect(restoreButton).toBeEnabled();
    await restoreButton.click();

    const confirmation = page.getByRole('dialog', { name: 'Restore backup' });
    await expect(confirmation).toBeVisible();
    await expect(confirmation.locator('[data-recovery-native-confirm="true"]')).toContainText('backup-mock-001');
    await expect(confirmation).toContainText('Location status');
    await expect(confirmation).toContainText('Available');
    await confirmation.getByRole('button', { name: 'Cancel' }).click();
    await expect(confirmation).toHaveCount(0);
    expect(restoreRequests).toEqual([]);
  });
  test('saved or stale state never promotes restore readiness', async ({ page }) => {
    await recovery(page,'recovery-projection-too-old');
    await expect(page.locator('.lite-recovery-premium-protection')).toHaveAttribute('data-recovery-protection-state','unknown');
    await expect(page.getByRole('button',{name:'Back Up Now'})).toBeDisabled();
  });
  for (const width of [320,360,390,768,1024,1440]) {
    test('reflows without horizontal overflow at ' + width, async ({ page }) => {
      await page.setViewportSize({width,height:850});
      await recovery(page,'recovery-verified');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });
  }
  test('keeps final Recovery activity reachable above the fixed mobile navigation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 850 });
    await recovery(page, 'recovery-verified');
    const finalActivity = page.locator('.lite-recovery-premium-timeline-list li').last();
    await finalActivity.waitFor({ state: 'visible' });
    const metrics = await page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
      const nav = document.querySelector('.pocket-nav-dock');
      const activity = document.querySelector('.lite-recovery-premium-timeline-list li:last-child');
      const navRect = nav?.getBoundingClientRect();
      const activityRect = activity?.getBoundingClientRect();
      return {
        navTop: navRect?.top ?? null,
        activityBottom: activityRect?.bottom ?? null,
        maxScroll: document.documentElement.scrollHeight - window.innerHeight,
        scrollY: window.scrollY,
      };
    });
    expect(metrics.scrollY).toBeGreaterThanOrEqual(Math.max(0, metrics.maxScroll - 1));
    expect(metrics.activityBottom).not.toBeNull();
    expect(metrics.navTop).not.toBeNull();
    expect(metrics.activityBottom as number).toBeLessThanOrEqual(metrics.navTop as number);
  });
  test('large text and reduced motion preserve content and controls', async ({ page }) => {
    await page.setViewportSize({width:390,height:850});
    await page.emulateMedia({reducedMotion:'reduce'});
    await recovery(page,'recovery-verified');
    await page.evaluate(() => {document.documentElement.style.fontSize='200%';});
    await expect(page.getByRole('button',{name:'Manage Recovery'})).toBeVisible();
    const transition = await page.locator('.lite-recovery-premium-stage-grid button').first().evaluate(el=>getComputedStyle(el).transitionDuration);
    expect(transition.split(',').every(part=>part.trim()==='0s' || part.trim()==='1e-05s')).toBe(true);
  });
  test('Axe has no serious or critical violations in landing and Manage', async ({ page }) => {
    await recovery(page);
    let results = await new AxeBuilder({page}).analyze();
    expect(results.violations.filter(v=>['serious','critical'].includes(v.impact || ''))).toEqual([]);
    await page.getByRole('button',{name:'Manage Recovery'}).click();
    results = await new AxeBuilder({page}).analyze();
    expect(results.violations.filter(v=>['serious','critical'].includes(v.impact || ''))).toEqual([]);
  });
});
