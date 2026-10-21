import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — no execution or approved visual baseline in this implementation-only session.
async function openIdentity(page: Page, scenario = 'identity-summary', theme: 'light' | 'dark' | 'system' = 'dark') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page, 'identity');
}
async function manage(page: Page, scenario = 'identity-summary', theme: 'light' | 'dark' | 'system' = 'dark') {
  await openIdentity(page, scenario, theme);
  await page.getByRole('button', { name: /^Manage Access$/i }).first().click();
  const dialog = page.getByRole('dialog', { name: /Manage access/i });
  await expect(dialog).toBeVisible();
  return dialog;
}
test.describe('Azure Horizon Identity source and access contracts', () => {
  for (const theme of ['light','dark','system'] as const) {
    test(`account-first personal composition — ${theme}`, async ({ page }) => {
      await openIdentity(page, 'identity-summary', theme);
      await expect(page.locator('[data-identity-horizon="account"]')).toBeVisible();
      await expect(page.getByRole('region', { name: 'Access profile' })).toContainText('Personal Mode');
      await expect(page.getByRole('heading', { name: 'Sign-in methods' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Active sessions' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Recent access activity' })).toBeVisible();
      await expect(page.locator('.lite-id-journey-steps li')).toHaveCount(4);
      const cards = page.locator('.lite-id-account-layout > *').filter({ has: page.getByRole('heading', { name: 'Sign-in methods' }) });
      await expect(cards.first()).toBeVisible();
    });
    test(`manage and protected dialogs inherit theme — ${theme}`, async ({ page }) => {
      const dialog = await manage(page, 'identity-summary', theme);
      await dialog.getByRole('button', { name: 'Recovery', exact: true }).click();
      await dialog.getByRole('button', { name: /Generate New Codes/i }).click();
      const confirmation = page.getByRole('dialog', { name: /Generate new recovery codes/i });
      await expect(confirmation).toBeVisible();
      await expect(page.locator('[data-private-ephemeral-result]')).toHaveCount(0);
      await page.keyboard.press('Escape');
      await expect(confirmation).toHaveCount(0);
      await expect(dialog).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
    });
    test(`WCAG AA automated screen and Manage scan — ${theme}`, async ({ page }) => {
      const dialog = await manage(page, 'identity-premium-multiple', theme);
      await expect(dialog).toBeVisible();
      const report = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      expect(report.violations.filter((issue) => issue.impact === 'serious' || issue.impact === 'critical'), JSON.stringify(report.violations)).toEqual([]);
    });
  }
  for (const width of [320,360,375,390,430,768,1024,1440]) {
    test(`responsive readable layout at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 850 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const dialog = await manage(page, 'identity-premium-long-text');
      expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
      const bounds = await dialog.boundingBox();
      expect(bounds).not.toBeNull();
      if (bounds) {
        expect(bounds.x).toBeGreaterThanOrEqual(-1);
        expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
      }
      await expect(dialog).toHaveAttribute('data-lite-identity-manage-layout', width >= 701 ? 'desktop-movable' : 'mobile-sheet');
    });
  }
  test('200% text scaling keeps access actions navigable', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    const dialog = await manage(page, 'identity-premium-long-text');
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await expect(dialog.getByRole('button', { name: /^Passkeys$/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  });
  test('desktop shared geometry moves, resizes, resets and keeps close reachable', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const dialog = await manage(page);
    const before = await dialog.boundingBox();
    const move = dialog.getByRole('button', { name: 'Move access panel' });
    await move.focus();
    await page.keyboard.press('ArrowLeft');
    const moved = await dialog.boundingBox();
    if (before && moved) expect(moved.x).toBeLessThan(before.x);
    const resize = dialog.getByRole('button', { name: 'Resize access panel' });
    await resize.focus();
    await page.keyboard.press('ArrowLeft');
    const resized = await dialog.boundingBox();
    if (moved && resized) expect(resized.width).toBeLessThanOrEqual(moved.width);
    await dialog.getByRole('button', { name: 'Reset access panel position and size' }).click();
    await expect(dialog.getByRole('button', { name: /Close app actions/i })).toBeVisible();
    await page.setViewportSize({ width: 800, height: 700 });
    const clamped = await dialog.boundingBox();
    if (clamped) expect(clamped.x + clamped.width).toBeLessThanOrEqual(801);
  });
  test('mobile never exposes desktop drag or resize', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const dialog = await manage(page);
    await expect(dialog).toHaveAttribute('data-lite-identity-manage-layout', 'mobile-sheet');
    await expect(dialog.getByRole('button', { name: 'Move access panel' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Resize access panel' })).toHaveCount(0);
  });
  for (const scenario of ['identity-premium-first-owner','identity-premium-signed-out','identity-premium-enrollment']) {
    test(`no authenticated dashboard for ${scenario}`, async ({ page }) => {
      await openIdentity(page,scenario);
      await expect(page.locator('[data-identity-horizon="account"]')).toHaveCount(0);
      await expect(page.getByRole('button', { name: /^Manage Access$/i })).toHaveCount(0);
    });
  }
  for (const role of ['owner','admin','operator','auditor','viewer']) {
    test(`Enterprise ${role} role remains server-reported`, async ({ page }) => {
      const dialog = await manage(page, `identity-enterprise-${role}`);
      await dialog.getByRole('button', { name: 'Roles & Access' }).click();
      await expect(dialog).toContainText(new RegExp(role,'i'));
      await expect(dialog).toContainText(/Effective capability matrix/i);
    });
  }
  test('saved Owner approvals never become actionable', async ({ page }) => {
    await openIdentity(page,'identity-owner-operation-offline');
    const approvals = page.getByRole('region',{name:'Pending approvals'}).first();
    await expect(approvals.getByRole('button',{name:'Approve'})).toBeDisabled();
    await expect(approvals.getByRole('button',{name:'Reject'})).toBeDisabled();
  });
  test('trusted clients remain separate from operation approvals', async ({ page }) => {
    const dialog=await manage(page,'identity-owner-client-pairing-pending');
    await dialog.getByRole('button',{name:'Trusted automation clients'}).click();
    await expect(dialog).toContainText(/Pending client registration/i);
    await expect(dialog).toContainText(/Pairing expires/i);
  });
  test('Enterprise Admin cannot gain Owner-only person actions through Details', async ({ page }) => {
    const dialog = await manage(page,'identity-enterprise-admin');
    await dialog.getByRole('button',{name:'People',exact:true}).click();
    await dialog.getByRole('button',{name:/Open Details/i}).first().click();
    await expect(page.getByRole('dialog',{name:/Access Details/i})).not.toContainText('Remove person');
  });
});

// Additional protected presentation paths use synthetic mocked state only.
test('owner setup keeps advanced manual fields behind disclosure',async({page})=>{
  await openIdentity(page,'identity-premium-first-owner');
  await expect(page.getByRole('button',{name:'Advanced Setup'})).toBeVisible();
  await expect(page.getByLabel('One-time setup token')).toHaveCount(0);
  await page.getByRole('button',{name:'Advanced Setup'}).click();
  await expect(page.getByLabel('One-time setup token')).toHaveAttribute('type','password');
});
test('signed-out supported password fallback stays optional',async({page})=>{
  await openIdentity(page,'identity-password-configured');
  await expect(page.getByRole('button',{name:/Advanced Sign-In/i})).toBeVisible();
  await page.getByRole('button',{name:/Advanced Sign-In/i}).click();
  await expect(page.getByLabel('Password',{exact:true})).toHaveAttribute('type','password');
});
test('session revocation is guarded by a nested consequence sheet',async({page})=>{
  const dialog=await manage(page,'identity-premium-multiple');
  await dialog.getByRole('button',{name:'Sessions',exact:true}).click();
  await dialog.getByRole('button',{name:/Other session/i}).first().click();
  const details=page.getByRole('dialog',{name:/Access Details/i});
  await expect(details).toBeVisible();
  await details.getByRole('button',{name:'Sign out session'}).click();
  await expect(page.getByRole('dialog',{name:/Sign out this session/i})).toBeVisible();
});
test('personal account does not render Enterprise People navigation',async({page})=>{
  const dialog=await manage(page,'identity-summary');
  await expect(dialog.getByRole('button',{name:'People',exact:true})).toHaveCount(0);
  await expect(dialog.getByRole('button',{name:'Roles & Access'})).toHaveCount(0);
});
