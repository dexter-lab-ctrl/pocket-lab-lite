import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import { expectLitePerformanceBudget, installLiteFrameSampler, measureLiteInteraction, writeLitePerformanceEvidence } from './lite-performance-helpers';

// PR #588 infrastructure and threshold policy are retained without changes.
// SOURCE AUTHORED. NOT RUN. No Android or live-server evidence claimed.
test.beforeEach(async ({ page }) => { await installLiteFrameSampler(page); });
for (const [label, width] of [['mobile',390],['desktop',1280]] as const) {
  test('Access native first paint, Manage, nested details and return — ' + label, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 850 });
    await installScenario(page, 'identity-premium-multiple');
    const first = await measureLiteInteraction(page, info, 'access-first-paint-'+label, async () => {
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await expect(page.locator('[data-identity-horizon="account"]')).toBeVisible();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(first);
    await writeLitePerformanceEvidence(info, first);
    const open = await measureLiteInteraction(page, info, 'access-manage-open-'+label, async () => {
      await page.getByRole('button', { name: 'Manage Access' }).click();
      await expect(page.getByRole('dialog', { name: /Manage access/i })).toBeVisible();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(open);
    await writeLitePerformanceEvidence(info, open);
    const dialog = page.getByRole('dialog', { name: /Manage access/i });
    const section = await measureLiteInteraction(page, info, 'access-section-'+label, async () => {
      await dialog.getByRole('button', { name: 'Passkeys', exact: true }).click();
      await expect(dialog.locator('[data-identity-manage-section="passkeys"]')).toBeVisible();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(section);
    await writeLitePerformanceEvidence(info, section);
    const detail = await measureLiteInteraction(page, info, 'access-details-'+label, async () => {
      await dialog.getByRole('button', { name: /Second passkey/i }).click();
      await expect(page.getByRole('dialog', { name: /Access Details/i })).toBeVisible();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(detail);
    await writeLitePerformanceEvidence(info, detail);
  });
}
test('Access mobile snap cost — candidate only', async ({ page }, info) => {
  await page.setViewportSize({ width:390, height:844 });
  await installScenario(page, 'identity-summary');
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page,'identity');
  await page.getByRole('button',{name:'Manage Access'}).click();
  const panel=page.getByRole('dialog',{name:/Manage access/i});
  const snap=await measureLiteInteraction(page,info,'access-mobile-snap',async()=>{
    await panel.getByRole('button',{name:/Resize sheet, currently/}).focus();
    await page.keyboard.press('End');
    await expect(panel).toHaveAttribute('data-lite-sheet-snap','expanded');
  },{settleMs:900,mode:'mocked'});
  expectLitePerformanceBudget(snap);
  await writeLitePerformanceEvidence(info,snap);
});
