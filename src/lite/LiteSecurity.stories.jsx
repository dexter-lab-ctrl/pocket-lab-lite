import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Security', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectSecurity(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Security|Safety Center/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManage(canvasElement) {
  const canvas = await expectSecurity(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Safety/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  await expect(await body.findByRole('dialog')).toBeInTheDocument();
}

export const QuickCheckHealthy = {
  ...createLiteStory('security', 'security-quick-healthy'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/No urgent safety issues|Protected|Safety score/i)).toBeInTheDocument();
  },
};
export const QuickCheckReviewRecommended = {
  ...createLiteStory('security', 'security-action-needed'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/attention|review|issue/i)).toBeInTheDocument();
  },
};
export const FullCheckRunning = {
  ...createLiteStory('security', 'security-full-running'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/running|checking|progress/i)).toBeInTheDocument();
  },
};
export const AppCheckHealthy = {
  ...createLiteStory('security', 'security-app-check-healthy'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/PhotoPrism|App Check/i)).toBeInTheDocument();
  },
};
export const UrgentFinding = {
  ...createLiteStory('security', 'security-urgent'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/urgent|critical|attention/i)).toBeInTheDocument();
  },
};
export const NoScanHistory = createLiteStory('security', 'security-first-run');
export const ProfileDataStale = createLiteStory('security', 'security-profile-stale');
export const ProgressStages = createLiteStory('security', 'security-progress');
export const ScannerUnavailable = {
  ...createLiteStory('security', 'security-scanner-unavailable'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/scanner|unavailable|attention/i)).toBeInTheDocument();
  },
};
export const UnsupportedAppProfileRoute = createLiteStory('security', 'security-unsupported-app-route');
export const SavedOfflineSnapshot = {
  ...createLiteStory('security', 'offline-saved'),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/saved|offline/i)).toBeInTheDocument();
  },
};

export const HealthyManageOverview = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const UrgentFindingManageOpen = {
  ...createLiteStory('security', 'security-urgent', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const ScannerUnavailableManageOpen = {
  ...createLiteStory('security', 'security-scanner-unavailable', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const OfflineSavedManageOpen = {
  ...createLiteStory('security', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(await canvas.findByText(/saved|offline/i)).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: /Run Quick Scan/i })).toBeDisabled();
  },
};
