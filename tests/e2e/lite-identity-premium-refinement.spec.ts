import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function identity(page: Page, scenario = 'identity-summary') {
  await installScenario(page, scenario);
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page, 'identity');
}
async function manage(page: Page, scenario = 'identity-summary') {
  await identity(page, scenario);
  await page.getByRole('button', { name: /^Manage Access$/i }).first().click();
  const dialog = page.getByRole('dialog', { name: /Manage access/i });
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe('Premium Identity & Access — source-backed interactions', () => {
  test('keeps one access story, a compact profile and four conceptual stages', async ({ page }) => {
    await identity(page);
    await expect(page.getByRole('region', { name: 'Access profile' })).toBeVisible();
    await expect(page.locator('.lite-id-journey-steps > li')).toHaveCount(4);
    await expect(page.getByRole('heading', { name: 'How your access fits together' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Recent access activity' })).toBeVisible();
  });
  test('does not query setup claims for an already authenticated Access Center', async ({ page }) => {
    const unnecessaryReads: string[] = [];
    page.on('request', (request) => {
      if (/\/api\/lite\/(?:identity\/owner-claim\/status|enterprise\/identity\/enrollment\/status)$/.test(new URL(request.url()).pathname)) {
        unnecessaryReads.push(new URL(request.url()).pathname);
      }
    });
    await identity(page);
    expect(unnecessaryReads).toEqual([]);
  });
  test('only mounts the selected Manage content section', async ({ page }) => {
    const dialog = await manage(page, 'identity-premium-multiple');
    await dialog.getByRole('button', { name: /^Passkeys$/ }).click();
    await expect(dialog.locator('[data-identity-manage-section]')).toHaveAttribute('data-identity-manage-section', 'passkeys');
    await expect(dialog.getByRole('button', { name: /Second passkey/i })).toBeVisible();
    await dialog.getByRole('button', { name: /^Sessions$/ }).click();
    await expect(dialog.locator('[data-identity-manage-section]')).toHaveAttribute('data-identity-manage-section', 'sessions');
    await expect(dialog.getByRole('button', { name: /^Other session/i })).toBeVisible();
    await expect(dialog.getByRole('button', { name: /Second passkey/i })).toHaveCount(0);
  });
  test('returns from Details to Manage without dismissing underlying overlay', async ({ page }) => {
    const dialog = await manage(page, 'identity-premium-multiple');
    await dialog.getByRole('button', { name: /^Passkeys$/ }).click();
    const row = dialog.getByRole('button', { name: /Second passkey/i });
    await row.click();
    const details = page.getByRole('dialog', { name: /Access Details/i });
    await expect(details).toBeVisible();
    await expect(details).not.toContainText('mock-second-passkey');
    await page.keyboard.press('Escape');
    await expect(details).toHaveCount(0);
    await expect(dialog).toBeVisible();
    await expect(row).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  });
  test('shows protected recovery consequence review without generating codes prematurely', async ({ page }) => {
    const dialog = await manage(page);
    await dialog.getByRole('button', { name: /^Recovery$/ }).click();
    await dialog.getByRole('button', { name: /^Generate New Codes$/ }).click();
    const confirm = page.getByRole('dialog', { name: /Generate new recovery codes/i });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText(/older recovery codes/i);
    await expect(page.locator('[data-private-ephemeral-result]')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeVisible();
  });
  test('activity filters use explicit event type and outcome with Details', async ({ page }) => {
    const dialog = await manage(page, 'identity-premium-multiple');
    await dialog.getByRole('button', { name: /^Activity$/ }).click();
    await dialog.getByRole('button', { name: /^Access changes$/ }).click();
    await expect(dialog).toContainText('Passkey registered');
    await dialog.getByRole('button', { name: /View activity details: Passkey registered/i }).click();
    await expect(page.getByRole('dialog', { name: /Access Details/i })).toContainText('Passkey registered');
  });
  test('shows Explain This with uncertainty and sanitized facts', async ({ page }) => {
    await identity(page);
    await page.getByRole('button', { name: /Explain This/i }).click();
    const panel = page.getByRole('dialog', { name: /Understand your access/i });
    await expect(panel).toContainText(/What this does not confirm/i);
    await expect(panel).toContainText(/Only the server|live permission/i);
  });
  test('keeps Enterprise People and Roles in one Manage navigation', async ({ page }) => {
    const dialog = await manage(page, 'identity-enterprise-owner');
    await dialog.getByRole('button', { name: 'People', exact: true }).click();
    await expect(dialog).toContainText('Add person');
    await expect(dialog.locator('.lite-governance-nav')).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Roles & Access' }).click();
    await expect(dialog).toContainText('Effective capability matrix');
    await dialog.getByRole('button', { name: /Role Details/i }).first().click();
    await expect(page.getByRole('dialog', { name: /Access Details/i })).toBeVisible();
  });
  test('keeps Admin unable to manage Owner and Personal Mode free of Enterprise controls', async ({ page }) => {
    const dialog = await manage(page, 'identity-enterprise-admin');
    await dialog.getByRole('button', { name: 'People', exact: true }).click();
    await dialog.getByRole('button', { name: /Open Details/i }).first().click();
    const details = page.getByRole('dialog', { name: /Access Details/i });
    await expect(details).not.toContainText('Remove person');
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    const personal = await manage(page, 'identity-summary');
    await expect(personal.getByRole('button', { name: 'People', exact: true })).toHaveCount(0);
  });
  test('retains signed-out and first-owner enrollment paths outside Access Center', async ({ page }) => {
    await identity(page, 'identity-premium-first-owner');
    await expect(page.getByRole('heading', { name: /Create the local Owner/i })).toBeVisible();
    await expect(page.locator('.lite-id-journey')).toHaveCount(0);
    await identity(page, 'identity-premium-signed-out');
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    await expect(page.locator('.lite-id-journey')).toHaveCount(0);
  });
  test('shows one exact pending bounded operation without changing Devices controls', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 860 });
    await identity(page, 'identity-owner-operation-pending');
    const approvals = page.getByRole('region', { name: 'Pending approvals' }).first();
    await expect(approvals).toBeVisible();
    await expect(approvals).toContainText('Secondary Phone');
    await expect(approvals).toContainText('PhotoPrism on this server');
    await expect(approvals).toContainText('one safe repeat');
    await approvals.getByText('What this approval includes').click();
    await expect(approvals).toContainText('One generated synthetic test photo may remain');
    await expect(approvals.getByRole('button', { name: 'Approve' })).toBeEnabled();
    await expect(approvals.getByRole('button', { name: 'Reject' })).toBeEnabled();
    await expect(page.locator('[data-lite-screen-id="devices"]')).toHaveCount(0);
  });
  test('renders multiple, expired, completed, and failed operations without replay controls', async ({ page }) => {
    await identity(page, 'identity-owner-operations-multiple');
    await expect(page.getByRole('region', { name: 'Pending approvals' }).first().locator('.lite-owner-operation-card')).toHaveCount(2);
    for (const scenario of ['identity-owner-operation-expired', 'identity-owner-operation-completed', 'identity-owner-operation-failed']) {
      await identity(page, scenario);
      const approvals = page.getByRole('region', { name: 'Pending approvals' }).first();
      await expect(approvals).toBeVisible();
      await expect(approvals.getByRole('button', { name: 'Approve' })).toHaveCount(0);
      await expect(approvals.getByRole('button', { name: 'Reject' })).toHaveCount(0);
    }
  });
  test('keeps approved execution read-only and disables saved approval state', async ({ page }) => {
    await identity(page, 'identity-owner-operation-executing');
    const executing = page.getByRole('region', { name: 'Pending approvals' }).first();
    await expect(executing).toContainText('Executing');
    await expect(executing.getByRole('button', { name: 'Approve' })).toHaveCount(0);
    await identity(page, 'identity-owner-operation-offline');
    const saved = page.getByRole('region', { name: 'Pending approvals' }).first();
    await expect(saved).toContainText('Live approval data unavailable');
    await expect(saved.getByRole('button', { name: 'Approve' })).toBeDisabled();
    await expect(saved.getByRole('button', { name: 'Reject' })).toBeDisabled();
  });
  for (const width of [320, 360, 375, 390, 768, 1024, 1440]) {
    test('keeps Journey and Manage readable at ' + width + 'px', async ({ page }) => {
      await page.setViewportSize({ width, height: 860 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const dialog = await manage(page, 'identity-premium-long-text');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      expect(overflow).toBe(false);
      const rect = await dialog.boundingBox();
      expect(rect).toBeTruthy();
      if (rect) { expect(rect.x).toBeGreaterThanOrEqual(-1); expect(rect.x + rect.width).toBeLessThanOrEqual(width + 1); }
    });
  }
  for (const percent of [200, 400]) {
    test('reflows important labels at ' + percent + '% text zoom', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 820 });
      const dialog = await manage(page, 'identity-premium-long-text');
      await page.addStyleTag({ content: 'html { font-size: ' + percent + '% !important; }' });
      await expect(dialog.getByRole('button', { name: /^Passkeys$/ })).toBeVisible();
      const rect = await dialog.boundingBox();
      if (rect) expect(rect.x + rect.width).toBeLessThanOrEqual(391);
    });
  }
  test('runs an axe AA contract including contrast on the Manage overlay', async ({ page }) => {
    const dialog = await manage(page);
    await expect(dialog).toBeVisible();
    const result = await new AxeBuilder({ page }).include('.lite-identity-manage-sheet').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    const blocking = result.violations.filter((violation) => ['serious', 'critical'].includes(violation.impact || ''));
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });
});
