import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import RecoveryBackupLocation from './RecoveryBackupLocation.jsx';

export default {
  title: 'Pocket Lab Lite/Recovery/Backup location',
  component: RecoveryBackupLocation,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    pocketlab: {
      product: 'Pocket Lab Lite',
      authority: 'Backend-owned location projection → Recovery presentation',
      warning: 'The Android system folder picker is not implemented; these stories cover truthful backend-discovered states.',
    },
  },
};

const location = (overrides = {}) => ({
  location_id: 'default-private',
  kind: 'private_default',
  display_name: 'Pocket Lab private backup folder',
  status: 'ready',
  available: true,
  writable: true,
  repository_present: true,
  is_default: true,
  is_selected: true,
  free_bytes: 18.4 * 1024 ** 3,
  ...overrides,
});

const locations = (selected, registered = [selected], candidates = []) => ({
  selected_location: selected,
  selected_location_id: selected.location_id,
  default_location_id: 'default-private',
  locations: registered,
  candidates,
  picker: { system_folder_picker: 'not_implemented', selection_mode: 'backend_discovered_candidates', raw_paths_accepted: false },
});

const custom = (overrides = {}) => location({
  location_id: 'loc-internal-pocketlab',
  kind: 'android_internal',
  display_name: 'Android internal storage › Pocket Lab Backups',
  is_default: false,
  is_selected: true,
  ...overrides,
});

async function openChoices(canvasElement) {
  const canvas = within(canvasElement);
  await userEvent.click(await canvas.findByRole('button', { name: 'Change backup location' }));
  await expect(await canvas.findByRole('group', { name: 'Backend-discovered backup locations' })).toBeInTheDocument();
}

export const DefaultPrivate = {
  render: () => <RecoveryBackupLocation locations={locations(location())} />,
};

export const CustomInternalReady = {
  render: () => <RecoveryBackupLocation locations={locations(custom())} />,
  play: async ({ canvasElement }) => {
    await expect(canvasElement).toHaveTextContent(/Android internal storage|Pocket Lab Backups/i);
  },
};

export const RemovableStorageReady = {
  render: () => {
    const selected = custom({ location_id: 'loc-sd-card', kind: 'android_removable', display_name: 'SD card › Pocket Lab Backups', is_removable: true, free_bytes: 42.7 * 1024 ** 3 });
    return <RecoveryBackupLocation locations={locations(selected)} onForget={() => {}} />;
  },
};

export const LowSpace = {
  render: () => <RecoveryBackupLocation locations={locations(custom({ status: 'low_space', available: false, writable: true, free_bytes: 12 * 1024 ** 2, reason_code: 'low_free_space' }))} />,
  play: async ({ canvasElement }) => {
    await openChoices(canvasElement);
    await expect(canvasElement).toHaveTextContent(/Low space/i);
  },
};

export const ReadOnly = {
  render: () => <RecoveryBackupLocation locations={locations(custom({ status: 'read_only', available: false, writable: false, reason_code: 'storage_not_writable' }))} />,
};

export const Disconnected = {
  render: () => <RecoveryBackupLocation locations={locations(custom({ status: 'missing', available: false, writable: false, repository_present: true, reason_code: 'storage_unavailable' }))} />,
};

export const RepositoryMissing = {
  render: () => <RecoveryBackupLocation locations={locations(custom({ status: 'available', available: true, repository_present: false, reason_code: 'repository_not_initialized' }))} />,
};

export const CandidateDiscovery = {
  render: () => <RecoveryBackupLocation
    locations={locations(location(), [location()], [{ candidate_id: 'loc-sd-card', kind: 'android_removable', display_name: 'SD card › Pocket Lab Backups', status: 'available', available: true, writable: true, is_removable: true }])}
    onDiscover={() => {}}
    onSelect={() => {}}
  />,
  play: async ({ canvasElement }) => {
    await openChoices(canvasElement);
    await expect(canvasElement).toHaveTextContent(/Available storage candidates|SD card/i);
  },
};

export const SavedOffline = {
  render: () => <RecoveryBackupLocation disabled locations={locations(custom({ status: 'missing', available: false, reason_code: 'saved_state_only' }))} />,
};

export const BackupRunning = {
  render: () => <RecoveryBackupLocation disabled busy="backup" locations={locations(location())} />,
};
