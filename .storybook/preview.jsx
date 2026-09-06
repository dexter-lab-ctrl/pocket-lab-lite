import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import '../src/index.css';
import { startPocketLabMocks, worker } from '../src/mocks/browser.js';
import { deviceFactsScenarioHandlers } from '../src/mocks/deviceFactsScenarios.js';
import { clearOfflineSafeSnapshots } from '../src/lib/liteOfflineDb.js';
import { liteQueryClient } from '../src/lib/liteQueryClient.js';
import { useLiteUiStore } from '../src/stores/liteUiStore.js';

let mocksStarted = false;

const viewports = {
  mobile360: { name: 'Mobile 360', styles: { width: '360px', height: '800px' } },
  mobile390: { name: 'Mobile 390', styles: { width: '390px', height: '844px' } },
  tablet: { name: 'Tablet', styles: { width: '768px', height: '1024px' } },
  desktop: { name: 'Desktop', styles: { width: '1440px', height: '1000px' } },
};

export const parameters = {
  layout: 'fullscreen',
  viewport: { viewports, defaultViewport: 'mobile390' },
  a11y: { config: { rules: [{ id: 'color-contrast', enabled: false }] } },
  controls: { expanded: true },
  options: { storySort: { order: ['Pocket Lab Lite', ['Home', 'Devices', 'Apps', 'Recovery', 'Security', 'Identity', 'Rules']] } },
  backgrounds: { default: 'lite', values: [{ name: 'lite', value: '#f8fafc' }] },
};

export const globalTypes = {
  reducedMotion: {
    name: 'Reduced motion',
    defaultValue: true,
    toolbar: { icon: 'accessibility', items: [{ value: true, title: 'Reduced' }, { value: false, title: 'Normal' }] },
  },
};

export const loaders = [async (context) => {
  if (!mocksStarted) {
    await startPocketLabMocks();
    mocksStarted = true;
  }
  liteQueryClient.clear();
  await clearOfflineSafeSnapshots().catch(() => null);
  const scenario = context.parameters?.liteScenario || 'healthy';
  const screenId = context.parameters?.liteScreen || 'home';
  const liteTheme = context.parameters?.liteTheme || 'daylight';
  const textScale = Number(context.parameters?.liteTextScale || 1);
  localStorage.setItem('POCKETLAB_MOCK_SCENARIO', scenario);
  localStorage.setItem('POCKETLAB_LITE_THEME', liteTheme === 'dark' ? 'dark' : 'daylight');
  document.documentElement.dataset.pocketlabLiteTheme = liteTheme === 'dark' ? 'dark' : 'daylight';
  document.documentElement.classList.toggle('theme-pocket-lite-dark', liteTheme === 'dark');
  document.documentElement.classList.toggle('theme-pocket-lite-daylight', liteTheme !== 'dark');
  document.documentElement.style.fontSize = textScale >= 2 ? '200%' : '';
  worker.resetHandlers();
  const scenarioHandlers = deviceFactsScenarioHandlers(scenario);
  if (scenarioHandlers.length) worker.use(...scenarioHandlers);
  useLiteUiStore.getState().setActiveTab(screenId);
  document.documentElement.dataset.liteStorybook = 'true';
  document.documentElement.style.setProperty('scroll-behavior', 'auto');
  if (context.globals?.reducedMotion !== false) document.documentElement.classList.add('lite-reduced-motion');
  else document.documentElement.classList.remove('lite-reduced-motion');
  return { scenario, screenId, liteTheme, textScale };
}];

export const decorators = [
  (Story) => (
    <div data-pocketlab-lite-storybook="true" style={{ minHeight: '100vh' }}>
      <Story />
    </div>
  ),
];

export { expect, userEvent, within };
