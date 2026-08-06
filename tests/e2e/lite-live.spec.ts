import { expect, test } from '@playwright/test';
import {
  LITE_TABS,
  openTab,
  waitForLiteScreenToSettle,
  watchApiFailures,
} from './lite-test-helpers';

test.describe('Pocket Lab Lite live read-only smoke', () => {
  test.skip(
    process.env.LITE_E2E_LIVE !== '1',
    'Set LITE_E2E_LIVE=1 after starting Caddy, FastAPI, SQLite, NATS/JetStream, worker, and PWA.'
  );

  test(
    'Caddy and FastAPI render every current Lite tab without write actions',
    async ({ page }) => {
      const failed = watchApiFailures(page);

      const statusResponse = page.waitForResponse(
        (response) =>
          response.url().includes('/api/lite/status')
      );

      await page.goto('/?screen=home');

      const response = await statusResponse;
      expect(response.ok()).toBeTruthy();

      const payload = await response.json();
      expect(payload).toHaveProperty('overall');

      for (const [label, screenId] of LITE_TABS) {
        await openTab(page, label, screenId);
      }

      expect(
        failed,
        `unexpected live Lite API failures: ${failed.join(', ')}`
      ).toEqual([]);
    }
  );

  test(
    'live Recovery projection meaning reaches the rendered UI',
    async ({ page }) => {
      const summaryResponse =
        page.waitForResponse(
          (response) =>
            response.url().includes(
              '/api/lite/recovery/summary'
            ) &&
            response.request().method() === 'GET' &&
            response.ok()
        );

      await page.goto('/?screen=recovery');

      const recovery = page.locator(
        '[data-lite-screen-id="recovery"]'
      );

      await expect(recovery).toBeVisible();

      const response = await summaryResponse;
      const payload = await response.json();

      await waitForLiteScreenToSettle(
        page,
        'recovery',
        {
          timeoutMs: 20_000,
          stableSamples: 4,
          intervalMs: 250,
        }
      );

      await expect(
        page.getByTestId(
          'parity-recovery-status'
        )
      ).toBeVisible();

      await expect(
        page.getByTestId(
          'parity-recovery-summary'
        )
      ).toBeVisible();

      const latestBackup =
        payload.latest_backup ||
        payload.last_backup ||
        {};

      if (latestBackup.backup_id) {
        await expect(
          page.getByTestId(
            'parity-latest-backup-id'
          )
        ).toHaveAttribute(
          'data-backup-id',
          latestBackup.backup_id
        );
      }

      const projectionStale =
        payload.read_degraded === true ||
        payload.degraded_reason ===
          'projection_too_old';

      const staleMessage = page.getByText(
        'Recovery information is old',
        { exact: true }
      );

      const backupButton = page.getByRole(
        'button',
        {
          name:
            /Back Up Now|Refresh to continue/i,
        }
      );

      if (projectionStale) {
        await expect(
          staleMessage
        ).toBeVisible();

        await expect(
          backupButton
        ).toBeDisabled();
      } else {
        await expect(
          staleMessage
        ).toHaveCount(0);
      }
    }
  );
});
