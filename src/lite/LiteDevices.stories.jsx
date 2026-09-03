import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Devices', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectDevices(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: 'Devices', level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openHealthyDeviceManage(canvasElement) {
  const canvas = await expectDevices(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Test-Phone-4/i });
  await userEvent.click(manage);
  await expect(await canvas.findByText(/Test-Phone-4/i)).toBeInTheDocument();
}

export const ServerHostOnline = createLiteStory('devices', 'devices-server-online');
export const JoinedDeviceOnline = {
  ...createLiteStory('devices', 'devices-online'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Online/i)).toBeInTheDocument();
    await expect(await canvas.findByText(/Test-Phone-4/i)).toBeInTheDocument();
  },
};
export const JoinedDeviceOffline = {
  ...createLiteStory('devices', 'devices-offline'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Offline/i)).toBeInTheDocument();
  },
};
export const AgentStopped = {
  ...createLiteStory('devices', 'devices-agent-stopped'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Agent stopped/i)).toBeInTheDocument();
  },
};
export const Repairing = {
  ...createLiteStory('devices', 'devices-repairing'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Repairing/i)).toBeInTheDocument();
  },
};
export const RemoteAccessNotReady = {
  ...createLiteStory('devices', 'devices-remote-not-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Remote access not ready/i)).toBeInTheDocument();
  },
};
export const ProtectedServerHost = {
  ...createLiteStory('devices', 'devices-protected-host'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/Protected server host/i)).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: /Remove.*server/i })).not.toBeInTheDocument();
  },
};
export const CapabilityVerified = createLiteStory('devices', 'devices-capability-verified');
export const CapabilityPending = createLiteStory('devices', 'devices-capability-pending');
export const CapabilityNotAdvertised = createLiteStory('devices', 'devices-capability-missing');
export const InviteReady = {
  ...createLiteStory('devices', 'devices-invite-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/invite|connect command|ready/i)).toBeInTheDocument();
  },
};
export const InviteExpired = createLiteStory('devices', 'devices-invite-expired');
export const InviteIdentityMismatch = {
  ...createLiteStory('devices', 'devices-invite-mismatch'),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    await expect(await canvas.findByText(/mismatch|blocked|different device/i)).toBeInTheDocument();
  },
};
export const SavedOfflineSnapshot = createLiteStory('devices', 'offline-saved');

export const HealthyDeviceManageOpen = {
  ...createLiteStory('devices', 'devices-online', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openHealthyDeviceManage(canvasElement),
};
export const MobileVerticalConnection = createLiteStory('devices', 'devices-online', { viewport: 'mobile390', notes: 'Mobile connection topology guard.' });
export const DesktopHorizontalConnection = createLiteStory('devices', 'devices-online', { viewport: 'desktop', notes: 'Desktop connection topology guard.' });
export const RepairingManageOpen = {
  ...createLiteStory('devices', 'devices-repairing', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectDevices(canvasElement);
    const manageButtons = await canvas.findAllByRole('button', { name: /Manage/i });
    await userEvent.click(manageButtons[manageButtons.length - 1]);
    await expect(await canvas.findByText(/Repairing/i)).toBeInTheDocument();
  },
};
