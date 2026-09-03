import { setupWorker } from 'msw/browser';
import { handlers } from './handlers.js';
import { identityRulesP1Handlers } from './identityRulesP1Handlers.js';
import { identityRulesCompatibilityHandlers } from './identityRulesCompatibilityHandlers.js';

export const worker = setupWorker(...identityRulesP1Handlers, ...identityRulesCompatibilityHandlers, ...handlers);

export async function startPocketLabMocks() {
  if (typeof window === 'undefined') return;
  await worker.start({ onUnhandledRequest: 'bypass' });
  console.info('[Pocket Lab MSW] API mocks enabled');
}
