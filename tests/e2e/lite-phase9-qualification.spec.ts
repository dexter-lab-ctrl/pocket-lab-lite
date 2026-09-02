import { expect, test } from '@playwright/test';
import {
  installScenario,
  LITE_TABS,
  openTab,
  waitForLiteScreenToSettle,
} from './lite-test-helpers';

async function assertNoPageOverflow(page) {
  await expect.poll(async () => page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))).toEqual(
    expect.objectContaining({
      scrollWidth: expect.any(Number),
      clientWidth: expect.any(Number),
    }),
  );

  expect(await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  )).toBe(true);
}

async function visibleButton(screen, name: RegExp) {
  const button = screen
    .getByRole('button', { name })
    .first();

  await expect(button).toBeVisible();
  return button;
}

test.describe('Pocket Lab Lite Phase 9 native/PWA qualification', () => {
  test.beforeEach(async ({ page }) => {
    await installScenario(page, 'healthy');
  });

  test('all Lite surfaces remain usable at 200 percent text size', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/?screen=home');

    await page.addStyleTag({
      content: `
        html {
          font-size: 200% !important;
        }
      `,
    });

    for (const [label, screenId] of LITE_TABS) {
      await openTab(page, label, screenId);
      await waitForLiteScreenToSettle(page, screenId);

      const screen = page.locator(
        `[data-lite-screen-id="${screenId}"]`,
      );

      await expect(screen).toBeVisible();
      await assertNoPageOverflow(page);

      const heading = screen.getByRole('heading', { level: 1 }).first();
      await expect(heading).toBeVisible();

      const visibleButtons = screen.locator('button:visible');
      if (await visibleButtons.count()) {
        const first = visibleButtons.first();
        await expect(first).toBeVisible();

        const box = await first.boundingBox();
        expect(box, `${screenId}: first visible button should remain reachable`).not.toBeNull();

        if (box) {
          expect(box.width).toBeGreaterThan(0);
          expect(box.height).toBeGreaterThan(0);
        }
      }
    }
  });

  test('Manage sheets preserve keyboard open, Escape close, and focus return', async ({ page }) => {
    const flows = [
      {
        screen: 'home',
        path: '/?screen=home',
        action: /Workspace details/i,
      },
      {
        screen: 'security',
        path: '/?screen=security',
        action: /Manage Safety/i,
      },
      {
        screen: 'recovery',
        path: '/?screen=recovery',
        action: /Manage Recovery/i,
      },
      {
        screen: 'identity',
        path: '/?screen=identity',
        action: /Manage Access/i,
      },
      {
        screen: 'rules',
        path: '/?screen=rules',
        action: /Manage Safety Rules/i,
      },
    ];

    for (const flow of flows) {
      await page.goto(flow.path);
      await waitForLiteScreenToSettle(page, flow.screen);

      const screen = page.locator(
        `[data-lite-screen-id="${flow.screen}"]`,
      );

      const opener = await visibleButton(screen, flow.action);

      await opener.focus();
      await expect(opener).toBeFocused();

      await page.keyboard.press('Enter');

      const dialog = page.locator('[role="dialog"]:visible').first();

      await expect(dialog).toBeVisible();

      await expect.poll(
        () => page.evaluate(() => {
          const active = document.activeElement;
          return Boolean(active?.closest?.('[role="dialog"]'));
        }),
        {
          message: `${flow.screen}: focus should enter the opened dialog`,
          timeout: 5_000,
        },
      ).toBe(true);

      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();

      await expect.poll(
        () => opener.evaluate((element) => document.activeElement === element),
        {
          message: `${flow.screen}: focus should return to the opener`,
          timeout: 5_000,
        },
      ).toBe(true);
    }
  });

  test('Devices Manage preserves keyboard and focus lifecycle', async ({ page }) => {
    await page.goto('/?screen=devices');
    await waitForLiteScreenToSettle(page, 'devices');

    const devices = page.locator('[data-lite-screen-id="devices"]');

    const healthyCard = devices
      .locator('.lite-device-card')
      .filter({ hasText: 'Test-Phone-4' });

    await expect(healthyCard).toBeVisible();

    const manage = healthyCard
      .getByRole('button', { name: /Manage Test-Phone-4/i })
      .first();

    await expect(manage).toBeVisible();
    await manage.focus();
    await expect(manage).toBeFocused();

    await page.keyboard.press('Enter');

    const detailPanel = devices.locator('.lite-device-details-panel');
    await expect(detailPanel).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(detailPanel).toBeHidden();
    await expect(manage).toBeFocused();
  });

  test('reduced motion suppresses animated connection packets without hiding state', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/?screen=devices');
    await waitForLiteScreenToSettle(page, 'devices');

    expect(
      await page.evaluate(
        () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      ),
    ).toBe(true);

    const devices = page.locator('[data-lite-screen-id="devices"]');

    const connected = devices
      .locator('[data-connection-state="connected"]')
      .first();

    await expect(connected).toBeVisible();
    await expect(connected).toHaveAttribute('aria-label', /connected/i);

    const signal = connected.locator('.lite-device-flow-signal');

    if (await signal.count()) {
      await expect(signal).toHaveCSS('animation-name', 'none');
    }

    const disconnected = devices
      .locator('[data-connection-state="disconnected"]')
      .first();

    if (await disconnected.count()) {
      await expect(disconnected).toBeVisible();
      await expect(disconnected).toHaveAttribute(
        'aria-label',
        /disconnected/i,
      );
    }
  });

  test('cross-tab navigation leaves no stale screen-local overlay', async ({ page }) => {
    await page.goto('/?screen=home');

    const sequence = [
      ['Home', 'home'],
      ['Devices', 'devices'],
      ['Security', 'security'],
      ['Recovery', 'recovery'],
      ['Identity & Access', 'identity'],
      ['Rules', 'rules'],
      ['Home', 'home'],
    ] as const;

    for (const [label, screenId] of sequence) {
      await openTab(page, label, screenId);
      await waitForLiteScreenToSettle(page, screenId);

      const current = page.locator(
        `[data-lite-screen-id="${screenId}"]`,
      );

      await expect(current).toBeVisible();

      for (const [, otherScreenId] of LITE_TABS) {
        if (otherScreenId === screenId) continue;

        const other = page.locator(
          `[data-lite-screen-id="${otherScreenId}"]`,
        );

        await expect(other).not.toBeVisible();
      }

      await expect(
        page.locator('[role="dialog"]:visible'),
      ).toHaveCount(0);

      await assertNoPageOverflow(page);
    }
  });

  test('closing a Manage sheet before tab navigation does not resurrect it', async ({ page }) => {
    await page.goto('/?screen=identity');
    await waitForLiteScreenToSettle(page, 'identity');

    const identity = page.locator('[data-lite-screen-id="identity"]');

    const manage = await visibleButton(identity, /Manage Access/i);
    await manage.click();

    const dialog = page.locator('[role="dialog"]:visible').first();

    await expect(dialog).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();

    await openTab(page, 'Rules', 'rules');
    await openTab(page, 'Identity & Access', 'identity');

    await expect(
      page.locator('[role="dialog"]:visible'),
    ).toHaveCount(0);

    await expect(identity).toBeVisible();
  });
});
