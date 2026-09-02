import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Apps', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectApps(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Apps|App Catalog/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManage(canvasElement) {
  const canvas = await expectApps(canvasElement);
  const manage = (await canvas.findAllByRole('button', { name: /Manage/i }))[0];
  await expect(manage).toBeEnabled();
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  await expect(await body.findByRole('dialog')).toBeInTheDocument();
}

export const CatalogReady = createLiteStory('catalog', 'catalog-ready');
export const AppInstalledRunning = {
  ...createLiteStory('catalog', 'healthy'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/PhotoPrism/i)).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: /Open/i })).toBeEnabled();
  },
};
export const AppStopped = {
  ...createLiteStory('catalog', 'app-stopped'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/stopped|not running/i)).toBeInTheDocument();
  },
};
export const InstallAvailable = {
  ...createLiteStory('catalog', 'catalog-install-available'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/install/i)).toBeInTheDocument();
  },
};
export const ActionInProgress = {
  ...createLiteStory('catalog', 'catalog-installing'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/working|installing|progress/i)).toBeInTheDocument();
  },
};
export const ActionFailed = {
  ...createLiteStory('catalog', 'app-action-failed'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/attention|failed|problem/i)).toBeInTheDocument();
  },
};
export const MediaNotReady = {
  ...createLiteStory('catalog', 'app-media-not-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/photos|media/i)).toBeInTheDocument();
  },
};
export const RouteNotReady = {
  ...createLiteStory('catalog', 'app-route-not-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/route|open|not ready/i)).toBeInTheDocument();
  },
};
export const PreparedProjectionStale = createLiteStory('catalog', 'app-projection-stale');
export const SavedOfflineSnapshot = {
  ...createLiteStory('catalog', 'offline-saved'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/saved|offline/i)).toBeInTheDocument();
  },
};

export const InstalledManageOpen = {
  ...createLiteStory('catalog', 'healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const InstallAvailableManageOpen = {
  ...createLiteStory('catalog', 'catalog-install-available', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const ActionFailedManageOpen = {
  ...createLiteStory('catalog', 'app-action-failed', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const Mobile320 = createLiteStory('catalog', 'healthy', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });
