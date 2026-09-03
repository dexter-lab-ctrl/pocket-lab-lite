import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Recovery', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectRecovery(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Recovery|Backup/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageRecovery(canvasElement, section = 'Backup') {
  const canvas = await expectRecovery(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Recovery/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage backups and recovery/i });
  await expect(dialog).toBeInTheDocument();
  const tab = within(dialog).getByRole('tab', { name: section });
  await userEvent.click(tab);
  await expect(tab).toHaveAttribute('aria-selected', 'true');
}

export const RecoveryReady = {
  ...createLiteStory('recovery', 'recovery-ready'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/Recovery Ready|ready/i);
  },
};
export const ProjectionTooOld = {
  ...createLiteStory('recovery', 'recovery-projection-too-old'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|stale|projection/i);
  },
};
export const NoBackupsYet = createLiteStory('recovery', 'recovery-no-backups');
export const LatestBackupVerified = {
  ...createLiteStory('recovery', 'recovery-verified'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/verified/i);
  },
};
export const BackupRunning = {
  ...createLiteStory('recovery', 'recovery-backup-running'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/running|backup|working/i);
  },
};
export const BackupFailed = createLiteStory('recovery', 'recovery-backup-failed');
export const RestorePreviewReady = {
  ...createLiteStory('recovery', 'recovery-preview-ready'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/preview/i);
  },
};
export const RestoreBlocked = {
  ...createLiteStory('recovery', 'recovery-restore-blocked'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/blocked|not ready|attention/i);
  },
};
export const CheckpointReady = {
  ...createLiteStory('recovery', 'recovery-checkpoint-ready'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/checkpoint/i);
  },
};
export const NoStorageNodeConfigured = {
  ...createLiteStory('recovery', 'recovery-no-storage-node'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/storage/i);
  },
};
export const RepositoryUnavailable = {
  ...createLiteStory('recovery', 'recovery-repository-unavailable'),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/repository|unavailable/i);
  },
};
export const SavedOfflineSnapshot = createLiteStory('recovery', 'offline-saved');

export const ManageOverview = {
  ...createLiteStory('recovery', 'recovery-ready', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement, 'Backup'),
};
export const ManageBackups = {
  ...createLiteStory('recovery', 'recovery-verified', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement, 'Backup'),
};
export const ManageRestore = {
  ...createLiteStory('recovery', 'recovery-preview-ready', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement, 'Restore'),
};
export const ManageRestoreBlocked = {
  ...createLiteStory('recovery', 'recovery-restore-blocked', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRecovery(canvasElement, 'Restore'),
};
export const OfflineSavedManage = {
  ...createLiteStory('recovery', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await expectRecovery(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|offline/i);
  },
};
export const Mobile320 = createLiteStory('recovery', 'recovery-ready', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });
