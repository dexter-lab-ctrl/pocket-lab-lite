import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Security', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectSecurity(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Security|Safety Center/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageSection(canvasElement, label = 'Overview') {
  const canvas = await expectSecurity(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Security details/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage Security/i });
  await expect(dialog).toBeInTheDocument();
  if (label !== 'Overview') {
    const tab = within(dialog).getByRole('tab', { name: new RegExp(`Open ${label} in Security Manage`, 'i') });
    await userEvent.click(tab);
    await expect(tab).toHaveAttribute('aria-selected', 'true');
  }
  await expect(within(dialog).getByRole('heading', { name: label, level: 3 })).toBeInTheDocument();
}

export const QuickCheckHealthy = {
  ...createLiteStory('security', 'security-quick-healthy'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/No urgent safety issues|Protected|Safety score/i);
  },
};
export const QuickCheckReviewRecommended = {
  ...createLiteStory('security', 'security-action-needed'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/attention|review|issue/i);
  },
};
export const FullCheckRunning = {
  ...createLiteStory('security', 'security-full-running'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/running|checking|progress/i);
  },
};
export const AppCheckHealthy = {
  ...createLiteStory('security', 'security-app-check-healthy'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/PhotoPrism|App Check/i);
  },
};
export const UrgentFinding = {
  ...createLiteStory('security', 'security-urgent'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/urgent|critical|attention/i);
  },
};
export const NoScanHistory = createLiteStory('security', 'security-first-run');
export const ProfileDataStale = createLiteStory('security', 'security-profile-stale');
export const ProgressStages = createLiteStory('security', 'security-progress');
export const ScannerUnavailable = {
  ...createLiteStory('security', 'security-scanner-unavailable'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/scanner|unavailable|attention/i);
  },
};
export const UnsupportedAppProfileRoute = createLiteStory('security', 'security-unsupported-app-route');
export const SavedOfflineSnapshot = {
  ...createLiteStory('security', 'offline-saved'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|offline/i);
  },
};

export const HealthyManageOverview = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Overview'),
};
export const ManageChanges = {
  ...createLiteStory('security', 'security-action-needed', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Changes'),
};
export const ManageIssues = {
  ...createLiteStory('security', 'security-urgent', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Issues'),
};
export const ManageCheckPath = {
  ...createLiteStory('security', 'security-full-running', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Check path'),
};
export const ManageEvidence = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Evidence'),
};
export const ManageHistory = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'History'),
};
export const ManageTechnicalDetails = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Technical details'),
};
export const UrgentFindingManageOpen = {
  ...createLiteStory('security', 'security-urgent', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Issues'),
};
export const ScannerUnavailableManageOpen = {
  ...createLiteStory('security', 'security-scanner-unavailable', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Overview'),
};
export const OfflineSavedManageOpen = {
  ...createLiteStory('security', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|offline/i);
    const quickScan = within(canvasElement).queryByRole('button', { name: /Run Quick Safety Check|Reconnect to run Quick Safety Check/i });
    if (quickScan) await expect(quickScan).toBeDisabled();
  },
};
