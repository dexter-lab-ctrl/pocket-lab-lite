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
export const NativeLibraryDaylightTablet = createLiteStory('devices', 'devices-online', { theme:'daylight', viewport:'desktop', notes:'Tablet-sized deferred qualification uses responsive preview viewport controls.' });
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


/* P7 Native Manage qualification: AUTHORED, NOT EXECUTED.
 * Shared production Devices page, Azure semantic themes and mocked API only.
 * Screenshot baseline approval and hardware haptic checks remain pending. */
function nativeManageStory({ theme = 'dark', viewport = 'desktop', scenario = 'devices-online', section = '', details = false } = {}) {
  return {
    ...createLiteStory('devices', scenario, { theme, viewport }),
    play: async ({ canvasElement }) => {
      const canvas = within(canvasElement);
      await userEvent.click((await canvas.findAllByRole('button', { name: /^Manage / }))[0]);
      const dialog = await within(document.body).findByRole('dialog', { name: /^Manage / });
      if (viewport.startsWith('mobile')) {
        await expect(dialog.querySelector('[data-manage-view="index"]')).toBeInTheDocument();
      }
      if (section) {
        await userEvent.click(await within(dialog).findByRole('button', { name: section, exact: true }));
        await expect(dialog.querySelector('[data-active-device-section="' + section.toLowerCase() + '"]')).toBeInTheDocument();
      }
      if (details && viewport.startsWith('mobile')) {
        await userEvent.click(await within(dialog).findByRole('button', { name: 'Back to all device settings' }));
        await expect(dialog.querySelector('[data-manage-view="index"]')).toBeInTheDocument();
      }
    },
  };
}
export const NativeManageDesktopOverviewDark = nativeManageStory({ theme: 'dark' });
export const NativeManageDesktopHealthDaylight = nativeManageStory({ theme: 'daylight', section: 'Health' });
export const NativeManageDesktopConnectionDark = nativeManageStory({ section: 'Connection' });
export const NativeManageDesktopServicesDaylight = nativeManageStory({ theme: 'daylight', section: 'Services' });
export const NativeManageDesktopHistoryDark = nativeManageStory({ section: 'History' });
export const NativeManageDesktopTechnicalDaylight = nativeManageStory({ theme: 'daylight', section: 'Technical' });
export const NativeManageDesktopSystemTheme = nativeManageStory({ theme: 'system', section: 'Overview' });
export const NativeManageMobileIndexDark = nativeManageStory({ viewport: 'mobile390' });
export const NativeManageMobileIndexDaylight = nativeManageStory({ theme: 'daylight', viewport: 'mobile360' });
export const NativeManageMobileDetailHealth = nativeManageStory({ viewport: 'mobile390', section: 'Health' });
export const NativeManageMobileBackToIndex = nativeManageStory({ viewport: 'mobile390', section: 'Connection', details: true });
export const NativeManageMobileOfflineSaved = nativeManageStory({ viewport: 'mobile390', scenario: 'offline-saved' });
export const NativeManageMobileRepairing = nativeManageStory({ viewport: 'mobile390', scenario: 'devices-repairing', section: 'Health' });
export const NativeManageServerProtected = nativeManageStory({ scenario: 'devices-protected-host' });
export const NativeManageRemoteNotReady = nativeManageStory({ scenario: 'devices-remote-not-ready', section: 'Connection' });
export const NativeManagePartialResources = nativeManageStory({ scenario: 'devices-resource-partial', section: 'Health' });
export const NativeManageStaleServices = nativeManageStory({ scenario: 'devices-services-stale', section: 'Services' });
export const NativeManageLongNames320 = createLiteStory('devices', 'devices-long-name', {
  theme: 'daylight', viewport: 'mobile360', textScale: 2,
});
