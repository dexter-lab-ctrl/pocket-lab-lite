import { setupWorker } from 'msw/browser';
import { handlers } from './handlers.js';

export const worker = setupWorker(...handlers);

export async function startPocketLabMocks() {
  if (typeof window === 'undefined') return;
  await worker.start({ onUnhandledRequest: 'bypass' });
  console.info('[Pocket Lab MSW] API mocks enabled');
}
