import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from '../stories/LiteStoryFrame.jsx';

// Existing production Devices page; no separate mock component tree.
export default { title: 'Pocket Lab Lite/Azure Horizon/Devices', component: LiteStoryFrame, tags: ['autodocs'] };
export const ConnectedBlackDesktop = createLiteStory('devices', 'devices-online', { theme:'dark', viewport:'desktop' });
export const ConnectedDaylightDesktop = createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'desktop' });
export const ConnectedBlackMobile = createLiteStory('devices', 'devices-online', { theme:'dark', viewport:'mobile390' });
export const ConnectedDaylightMobile = createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'mobile390' });
export const SystemAppearance = createLiteStory('devices', 'devices-online', { theme:'system', viewport:'desktop' });
export const AgentStopped = createLiteStory('devices', 'devices-agent-stopped', { theme:'dark', viewport:'mobile360' });
export const Repairing = createLiteStory('devices', 'devices-repairing', { theme:'dark', viewport:'desktop' });
export const RemoteAccessNotReady = createLiteStory('devices', 'devices-remote-not-ready', { theme:'daylight', viewport:'mobile390' });
export const ProtectedHost = createLiteStory('devices', 'devices-protected-host', { theme:'dark', viewport:'desktop' });
export const InviteReady = createLiteStory('devices', 'devices-invite-ready', { theme:'dark', viewport:'mobile390' });
export const IdentityMismatch = createLiteStory('devices', 'devices-invite-mismatch', { theme:'daylight', viewport:'desktop' });
export const OfflineSaved = createLiteStory('devices', 'offline-saved', { theme:'dark', viewport:'mobile390' });
export const TwoHundredPercentText = createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'mobile360', textScale:2 });

export const OfflineDaylight = createLiteStory('devices', 'devices-offline', { theme: 'daylight', viewport: 'mobile360' });
export const HealthPartialBlack = createLiteStory('devices', 'devices-resource-partial', { theme: 'dark', viewport: 'desktop' });
export const HealthStaleDaylight = createLiteStory('devices', 'devices-resource-stale', { theme: 'daylight', viewport: 'mobile390' });
export const NoReportedResources = createLiteStory('devices', 'devices-resource-missing', { theme: 'dark', viewport: 'mobile360' });
export const SupervisorStale = createLiteStory('devices', 'devices-services-stale', { theme: 'dark', viewport: 'desktop' });
export const MixedServicesDaylight = createLiteStory('devices', 'devices-services-mixed', { theme: 'daylight', viewport: 'desktop' });
export const MultipleResponsibilities = createLiteStory('devices', 'devices-online', { theme: 'daylight', viewport: 'desktop' });
export const LongNameBlackMobile = createLiteStory('devices', 'devices-long-name', { theme: 'dark', viewport: 'mobile360' });
export const BackupSourceUnavailable = createLiteStory('devices', 'photo-backup-source-offline', { theme: 'dark', viewport: 'mobile390' });
export const Resource200PercentBlack = createLiteStory('devices', 'devices-resource-complete', { theme: 'dark', viewport: 'mobile360', textScale: 2 });

/* P7 stories: AUTHORED — NOT EXECUTED — UNVALIDATED.
   Existing production Devices screen and mocked FastAPI projections are reused. */
export const NativeLibraryDaylightTablet = createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'tablet' });
export const NativeLibraryDarkLongNames = createLiteStory('devices', 'devices-long-name', { theme:'dark', viewport:'mobile360', textScale:2 });
export const NativeLibrarySavedUnconfirmed = createLiteStory('devices', 'offline-saved', { theme:'daylight', viewport:'mobile390' });
export const NativeLibraryConnectionAttention = createLiteStory('devices', 'devices-services-stale', { theme:'dark', viewport:'desktop' });
export const NativeLibraryIdentityBlocked = createLiteStory('devices', 'devices-invite-mismatch', { theme:'daylight', viewport:'mobile390' });
export const NativeLibraryManageConnection = {
  ...createLiteStory('devices', 'devices-online', { theme:'dark', viewport:'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole('button', { name:/Manage Test-Phone-4/i }));
    const dialog = await within(document.body).findByRole('dialog', { name:/Manage Test-Phone-4/i });
    await userEvent.click(await within(dialog).findByRole('button', { name:'Connection', exact:true }));
    await expect(await within(dialog).findByText(/Latest activity|Connection now/i)).toBeInTheDocument();
  },
};
export const NativeLibraryTopologyExpanded = {
  ...createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'mobile390' }),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByText('Connections & Topology'));
    await expect(await canvas.findByRole('region', { name:'Pocket Lab device connections' })).toBeInTheDocument();
  },
};
