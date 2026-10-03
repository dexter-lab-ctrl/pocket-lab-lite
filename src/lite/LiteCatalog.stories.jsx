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

export const MultiAppCapabilityIsolation = {
  ...createLiteStory('catalog', 'catalog-multi-app', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText('Example App')).toBeInTheDocument();
    await expect(await canvas.findByText('PhotoPrism')).toBeInTheDocument();
    const manageButtons = await canvas.findAllByRole('button', { name: 'Manage' });
    await userEvent.click(manageButtons[0]);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: 'Manage Example App' });
    await expect(dialog).toBeInTheDocument();
    await expect(within(dialog).queryByText(/Connect photos|Import photos|Back up app|Check app|Repair/i)).not.toBeInTheDocument();
  },
};
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


async function expectManageAccessState(canvasElement, expected) {
  await openManage(canvasElement);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
  await expect(await within(dialog).findByText(expected)).toBeInTheDocument();
}

export const GovernedFullAccess = {
  ...createLiteStory('catalog', 'app-governance-full-access', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /You can manage this app/i),
};

export const GovernedReadOnly = {
  ...createLiteStory('catalog', 'app-governance-read-only', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /Read-only access/i),
};

export const GovernedApprovalRequired = {
  ...createLiteStory('catalog', 'app-governance-approval-required', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /needs approval/i),
};

export const GovernedTemporaryAccess = {
  ...createLiteStory('catalog', 'app-governance-temporary-allowed', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /Temporary access until/i),
};

export const GovernedBlockedByRules = {
  ...createLiteStory('catalog', 'app-governance-blocked', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /blocked by Rules/i),
};

export const GovernedMissingCredential = {
  ...createLiteStory('catalog', 'app-governance-missing-credential', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /credential is missing/i),
};

export const GovernedRecoveryBlocker = {
  ...createLiteStory('catalog', 'app-governance-recovery-blocker', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /storage device is unavailable/i),
};

export const GovernedUnsupportedCapability = {
  ...createLiteStory('catalog', 'catalog-multi-app', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    const cards = canvas.getAllByText('Example App');
    await expect(cards.length).toBeGreaterThan(0);
    const manageButtons = await canvas.findAllByRole('button', { name: 'Manage' });
    await userEvent.click(manageButtons[0]);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: 'Manage Example App' });
    await expect(within(dialog).queryByText(/Back up app|Preview restore|Check app|Repair app/i)).not.toBeInTheDocument();
  },
};
