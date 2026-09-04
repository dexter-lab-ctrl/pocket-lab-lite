import { expect, test } from '@playwright/test';
import { installScenario } from './lite-test-helpers';

async function installRulesActivationFetch(page, terminal: 'success' | 'not_completed') {
  await page.addInitScript(({ terminalState }) => {
    const originalFetch = window.fetch.bind(window);
    const phases = ['pending', 'validating', 'switching', 'restarting', 'verifying'];
    window.__rulesActivationPhase = -1;
    window.__rulesActivationTerminal = terminalState;

    window.fetch = async (input, init) => {
      const requestUrl = typeof input === 'string' ? input : input.url;
      const url = new URL(requestUrl, window.location.origin);
      const method = String(init?.method || (typeof input === 'string' ? 'GET' : input.method) || 'GET').toUpperCase();

      if (url.pathname === '/api/lite/enterprise/rules/source-sync' && method === 'POST') {
        window.__rulesActivationPhase = 0;
        return new Response(JSON.stringify({
          status: 'queued',
          accepted: true,
          activation_required: true,
          summary: 'Safety Rules update was accepted. The supervisor will stage, restart and verify it.',
          operation: {
            operation_id: 'plo-ui-progress',
            candidate_revision_id: 'plr-ui-candidate',
            state: 'pending',
          },
        }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/api/lite/enterprise/rules/source-sync/status' && method === 'GET') {
        const phase = window.__rulesActivationPhase;
        if (phase >= 0 && phase < phases.length) {
          const current = phases[phase];
          const shouldStop = terminalState === 'not_completed' && current === 'validating';
          window.__rulesActivationPhase = shouldStop ? 99 : phase + 1;
          return new Response(JSON.stringify({
            source: {
              durable: true,
              active_revision: 'plr-old',
              known_good_revision: 'plr-old',
              repository_revision: 'plr-ui-candidate',
              source_update_required: true,
              activation_in_progress: true,
              activation_operation: {
                operation_id: 'plo-ui-progress',
                candidate_revision_id: 'plr-ui-candidate',
                state: current,
                created_at: '2026-09-04T17:30:00Z',
                updated_at: '2026-09-04T17:30:03Z',
              },
            },
            sanitized: true,
            policy_source_exposed: false,
            runtime_command_exposed: false,
          }), { headers: { 'Content-Type': 'application/json' } });
        }
        const succeeded = terminalState === 'success';
        return new Response(JSON.stringify({
          source: {
            durable: true,
            active_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
            known_good_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
            repository_revision: 'plr-ui-candidate',
            source_update_required: !succeeded,
            activation_in_progress: false,
            activation_operation: null,
          },
          sanitized: true,
          policy_source_exposed: false,
          runtime_command_exposed: false,
        }), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/api/lite/policy' && method === 'GET') {
        const response = await originalFetch(input, init);
        const payload = await response.clone().json();
        const phase = window.__rulesActivationPhase;
        const started = phase >= 0;
        const terminalReached = phase >= phases.length || phase === 99;
        const succeeded = terminalReached && terminalState === 'success';
        payload.active_policy = {
          ...(payload.active_policy || {}),
          revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
          repository_revision: 'plr-ui-candidate',
          known_good_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
          source_update_required: !succeeded,
          source_update_available: !succeeded,
          activation_in_progress: started && !terminalReached,
        };
        payload.engine = {
          ...(payload.engine || {}),
          healthy: true,
          loopback_only: true,
          endpoint_exposed_to_browser: false,
        };
        payload.status = succeeded ? 'ready' : 'degraded';
        payload.degraded_reason = succeeded ? '' : started && !terminalReached ? 'policy_activation_pending' : 'policy_source_update_pending';
        payload.summary = succeeded
          ? 'Safety Rules are active and ready for protected changes.'
          : started && !terminalReached
            ? 'Safety Rules are being updated and verified. Protected changes remain fail-closed until verification finishes.'
            : 'A Safety Rules update is ready. The Owner must confirm it before protected changes can continue.';
        return new Response(JSON.stringify(payload), {
          status: response.status,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      return originalFetch(input, init);
    };
  }, { terminalState: terminal });
}

test.describe('Rules governed activation progress', () => {
  test.beforeEach(async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.setViewportSize({ width: 390, height: 844 });
  });

  test('shows server-reported supervisor phases and disables duplicate actions until proof succeeds', async ({ page }) => {
    await installRulesActivationFetch(page, 'success');
    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');

    const update = rules.getByRole('button', { name: 'Update Safety Rules' });
    await expect(update).toBeVisible();
    await update.click();

    await expect(rules.getByRole('button', { name: 'Rules update running' })).toBeDisabled();
    await expect(rules.getByRole('button', { name: 'Update in progress…' })).toBeDisabled();
    await expect(rules.getByRole('button', { name: /^Refresh$/ })).toHaveCount(0);

    const progress = rules.locator('.lite-rules-activation-card');
    await expect(progress).toBeVisible();
    await expect(progress).toContainText('Supervisor proof');
    await expect(progress).toContainText('Accepted');
    await expect(progress).toContainText('Validating');
    await expect(progress).toContainText('Switching');
    await expect(progress).toContainText('Restarting');
    await expect(progress).toContainText('Verifying');
    await expect(progress).toContainText('Succeeded');

    await expect(progress).toHaveAttribute('data-rules-activation-state', 'active', { timeout: 15_000 });
    await expect(progress).toContainText('proved the new Rules revision');
    await expect(rules.getByRole('button', { name: /^Refresh$/ })).toBeVisible();
    await expect(rules.getByRole('button', { name: 'Rules update running' })).toHaveCount(0);
    await expect(rules.getByRole('button', { name: 'Update in progress…' })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('keeps the last proved phase and re-enables retry after the server reports no completed update', async ({ page }) => {
    await installRulesActivationFetch(page, 'not_completed');
    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');

    await rules.getByRole('button', { name: 'Update Safety Rules' }).click();
    const progress = rules.locator('.lite-rules-activation-card');
    await expect(progress).toHaveAttribute('data-rules-activation-state', 'not_completed', { timeout: 10_000 });
    await expect(progress).toContainText('Update not completed');
    await expect(progress).toContainText('previous known-good protection remains authoritative');

    await expect(rules.getByRole('button', { name: 'Update Safety Rules' })).toBeEnabled();
    await expect(rules.getByRole('button', { name: /^Refresh$/ })).toBeVisible();
    await expect(rules).toContainText(/fail-closed|blocked/i);
  });
});
