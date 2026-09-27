import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const SCREENS = [
  ['home', 'Home'],
  ['catalog', 'Your Apps'],
  ['devices', 'Devices'],
  ['security', 'Safety Center'],
  ['identity', 'Identity & Access'],
  ['rules', 'Safety Rules'],
  ['recovery', 'Backup & Restore'],
] as const;

const FORBIDDEN_DEFAULT_UI = /(NATS|JetStream|FastAPI|\bbackend\b|control plane|durable consumer|projection stale|polling:)/i;

for (const [screenId, heading] of SCREENS) {
  test(`${screenId} default story is fresh, readable, and free of backend language`, async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);

    const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
    await expect(screen).toBeVisible();
    await expect(screen.getByRole('heading', { name: heading, exact: true }).first()).toBeVisible();
    await expect(screen.locator('.lite-ux-freshness')).toBeVisible();

    const visibleText = await screen.evaluate((element) => (element as HTMLElement).innerText);
    expect(visibleText).not.toMatch(FORBIDDEN_DEFAULT_UI);
  });
}

test('primary navigation uses the compact product vocabulary', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const nav = page.getByRole('navigation', { name: 'Pocket Lab sections' });
  for (const label of ['Home', 'Apps', 'Devices', 'Safety', 'Access', 'Rules', 'Recovery']) {
    await expect(nav.getByText(label, { exact: true })).toBeVisible();
  }
});

test('Home Workspace details provide real technical facts only on demand', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  await page.getByRole('button', { name: 'Workspace details' }).click();
  const dialog = page.getByRole('dialog').filter({ hasText: 'Workspace details' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Technical details', { exact: true })).toBeVisible();
});

test('saved/offline presentation stays usable and read-only', async ({ page }) => {
  await installScenario(page, 'offline-saved');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await expect(page.getByText('Showing saved information', { exact: false }).first()).toBeVisible();
});
