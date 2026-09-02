import { expect, test, type Locator, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

type OverlayCase = {
  name: string;
  screen: string;
  scenario?: string;
  open: (page: Page) => Promise<void>;
  surface: (page: Page) => Locator;
};

const OVERLAYS: OverlayCase[] = [
  {
    name: 'home-manage',
    screen: 'home',
    open: async (page) => page.getByRole('button', { name: 'Workspace details' }).click(),
    surface: (page) => page.getByRole('dialog', { name: /Workspace details/i }),
  },
  {
    name: 'apps-manage',
    screen: 'catalog',
    scenario: 'catalog-ready',
    open: async (page) => page.getByRole('button', { name: /^Manage$/i }).first().click(),
    surface: (page) => page.getByRole('dialog', { name: /Manage PhotoPrism/i }),
  },
  {
    name: 'devices-manage',
    screen: 'devices',
    open: async (page) => page.getByRole('button', { name: /Manage Test-Phone-4/i }).click(),
    surface: (page) => page.locator('.lite-device-details-panel'),
  },
  {
    name: 'security-manage',
    screen: 'security',
    open: async (page) => page.getByRole('button', { name: /Manage Security details/i }).click(),
    surface: (page) => page.getByRole('dialog', { name: /Manage Security/i }),
  },
  {
    name: 'identity-manage',
    screen: 'identity',
    open: async (page) => page.getByRole('button', { name: /Manage Access/i }).click(),
    surface: (page) => page.getByRole('dialog', { name: /Manage access/i }),
  },
  {
    name: 'rules-manage',
    screen: 'rules',
    open: async (page) => page.getByRole('button', { name: /Manage Safety Rules/i }).click(),
    surface: (page) => page.getByRole('dialog', { name: /Manage Safety Rules/i }),
  },
  {
    name: 'recovery-manage',
    screen: 'recovery',
    open: async (page) => page.getByRole('button', { name: /Manage Recovery/i }).click(),
    surface: (page) => page.getByRole('dialog', { name: /Manage backups and recovery/i }),
  },
];

for (const item of OVERLAYS) {
  test(`${item.name} responsive Manage surface remains visually stable`, async ({ page }) => {
    await installScenario(page, item.scenario || 'healthy');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/?screen=${item.screen}`);
    await waitForLiteScreenToSettle(page, item.screen);

    await item.open(page);
    const surface = item.surface(page);
    await expect(surface).toBeVisible();

    await expect(surface).toHaveScreenshot(`${item.name}.png`, {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.02,
    });
  });
}
