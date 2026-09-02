import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Recovery', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectRecovery(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Recovery|Backup/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageRecovery(canvasElement) {
  const canvas = await expectRecovery(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Recovery/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  await expect(await body.findByRole('dialog', { name: /Manage Recovery/i })).toBeInTheDocument();
}

export const RecoveryReady = {
  ...createLiteStory('recovery', 'recovery-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/Recovery Ready|ready/i)).toBeInTheDocument();
  },
};
export const ProjectionTooOld = {
  ...createLiteStory('recovery', 'recovery-projection-too-old'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/saved|stale|projection/i)).toBeInTheDocument();
  },
};
export const NoBackupsYet = createLiteStory('recovery', 'recovery-no-backups');
export const LatestBackupVerified = {
  ...createLiteStory('recovery', 'recovery-verified'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/verified/i)).toBeInTheDocument();
  },
};
export const BackupRunning = {
  ...createLiteStory('recovery', 'recovery-backup-running'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/running|backup|working/i)).toBeInTheDocument();
  },
};
export const BackupFailed = createLiteStory('recovery', 'recovery-backup-failed');
export const RestorePreviewReady = {
  ...createLiteStory('recovery', 'recovery-preview-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/preview/i)).toBeInTheDocument();
  },
};
export const RestoreBlocked = {
  ...createLiteStory('recovery', 'recovery-restore-blocked'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/blocked|not ready|attention/i)).toBeInTheDocument();
  },
};
export const CheckpointReady = {
  ...createLiteStory('recovery', 'recovery-checkpoint-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/checkpoint/i)).toBeInTheDocument();
  },
};
export const NoStorageNodeConfigured = {
  ...createLiteStory('recovery', 'recovery-no-storage-node'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/storage/i)).toBeInTheDocument();
  },
};
export const RepositoryUnavailable = {
  ...createLiteStory('recovery', 'recovery-repository-unavailable'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/repository|unavailable/i)).toBeInTheDocument();
  },
};
export const SavedOfflineSnapshot = createLiteStory('recovery', 'offline-saved');

export const ManageOverview = {
  ...createLiteStory('recovery', 'recovery-ready', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement),
};
export const ManageRestoreBlocked = {
  ...createLiteStory('recovery', 'recovery-restore-blocked', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement),
};
export const OfflineSavedManage = {
  ...createLiteStory('recovery', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectRecovery(canvasElement);
    await expect(await canvas.findByText(/saved|offline/i)).toBeInTheDocument();
  },
};
export const Mobile320 = createLiteStory('recovery', 'recovery-ready', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });
