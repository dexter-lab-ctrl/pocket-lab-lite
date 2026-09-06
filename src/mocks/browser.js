import { setupWorker } from 'msw/browser';
import { handlers } from './handlers.js';
import { identityRulesP1Handlers } from './identityRulesP1Handlers.js';
import { identityRulesCompatibilityHandlers } from './identityRulesCompatibilityHandlers.js';
import { deviceFactsScenarioHandlers } from './deviceFactsScenarios.js';

const initialScenario = typeof window !== 'undefined'
  ? window.localStorage.getItem('POCKETLAB_MOCK_SCENARIO') || ''
  : '';

export const worker = setupWorker(
  ...deviceFactsScenarioHandlers(initialScenario),
  ...identityRulesP1Handlers,
  ...identityRulesCompatibilityHandlers,
  ...handlers,
);

export async function startPocketLabMocks() {
  if (typeof window === 'undefined') return;
  await worker.start({ onUnhandledRequest: 'bypass' });
  console.info('[Pocket Lab MSW] API mocks enabled');
}
