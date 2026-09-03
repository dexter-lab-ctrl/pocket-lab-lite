import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import {
  LiteActionRow,
  LiteFlowStatusPanel,
  LiteOperationalStory,
  LiteOutcomeNotice,
} from './LiteUi.jsx';
import { LiteDetailsPanel, LiteSheet } from './LiteOverlay.jsx';

export default {
  title: 'Pocket Lab Lite/Shared Primitives',
  tags: ['autodocs'],
  parameters: {
    pocketlab: {
      product: 'Pocket Lab Lite',
      screen: 'shared-primitives',
      scenario: 'fixtureless-presentation',
      implementation_status: 'verified',
      notes: 'Direct Storybook coverage for repository-owned Lite UI primitives. No backend execution is simulated.',
    },
  },
};

const shell = (children) => (
  <main className="theme-pocket-lite-daylight" style={{ minHeight: '100vh', padding: '24px', background: 'var(--lite-bg, #f8fafc)' }}>
    <div style={{ maxWidth: 760, margin: '0 auto', display: 'grid', gap: 16 }}>{children}</div>
  </main>
);

export const OperationalReady = {
  render: () => shell(
    <LiteOperationalStory story={{ state: 'ready', tone: 'ready', headline: 'Everything looks good', summary: 'Pocket Lab is showing current server-owned state.', freshness: { label: 'Fresh just now', state: 'live' } }} manageAction={{ label: 'Manage', onClick: () => {} }} />,
  ),
};

export const OperationalAttention = {
  render: () => shell(
    <LiteOperationalStory story={{ state: 'attention', tone: 'attention', headline: 'Something changed', summary: 'Review the current state before continuing.', attention: 'One area needs attention.' }} primaryAction={{ label: 'Review', onClick: () => {} }} />,
  ),
};

export const OperationalSaved = {
  render: () => shell(
    <LiteOperationalStory story={{ state: 'saved', tone: 'saved', headline: 'Showing saved state', summary: 'Reconnect to refresh current information.', freshness: { label: 'Saved 12 minutes ago', state: 'saved' } }} />,
  ),
};

export const LongCopy = {
  render: () => shell(
    <LiteOperationalStory story={{ state: 'attention', tone: 'attention', headline: 'A deliberately long workspace status heading remains readable without forcing horizontal scrolling on narrow screens', summary: 'This intentionally long summary exercises wrapping for worst-plausible explanatory copy while keeping the next action reachable and the state meaning intact.', consequence: 'No backend capability is invented by this presentation-only stress story.' }} primaryAction={{ label: 'Review the current state', onClick: () => {} }} />,
  ),
  parameters: { viewport: { defaultViewport: 'mobile360' } },
};

export const ActionRowReady = {
  render: () => shell(
    <LiteActionRow label="Restart Agent" value="Ready" summary="Pocket Lab can send this request through the control plane." action={{ label: 'Restart Agent', onClick: () => {} }} />,
  ),
};

export const ActionRowBlocked = {
  render: () => shell(
    <LiteActionRow label="Remove old device" value="Blocked" summary="The protected server host cannot be removed." disabledReason="Protected server host" attention action={{ label: 'Remove', disabled: true, onClick: () => {} }} />,
  ),
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('button', { name: 'Remove' })).toBeDisabled();
  },
};

export const OutcomeFailed = {
  render: () => shell(
    <LiteOutcomeNotice outcome={{ tone: 'failed', headline: 'Action needs attention', summary: 'Pocket Lab did not report success.', nextAction: 'Review the current state before trying again.' }} />,
  ),
};

export const FlowWorking = {
  render: () => shell(
    <LiteFlowStatusPanel title="Restart Agent" label="Repairing" tone="info" note="Progress remains backend-owned." steps={[{ id: 'accepted', label: 'Request accepted', state: 'complete' }, { id: 'restart', label: 'Agent restarting', state: 'active' }, { id: 'heartbeat', label: 'Waiting for fresh heartbeat', state: 'waiting' }]} />,
  ),
};

export const FlowFailed = {
  render: () => shell(
    <LiteFlowStatusPanel title="Restart Agent" label="Needs attention" tone="danger" note="No false completion is shown." steps={[{ id: 'accepted', label: 'Request accepted', state: 'complete' }, { id: 'restart', label: 'Agent restart failed', state: 'failed' }, { id: 'heartbeat', label: 'Fresh heartbeat', state: 'waiting' }]} />,
  ),
};

function SheetHarness({ details = false }) {
  const [open, setOpen] = React.useState(false);
  return shell(
    <>
      <button type="button" onClick={() => setOpen(true)}>Open Manage</button>
      {details ? (
        <LiteDetailsPanel open={open} onClose={() => setOpen(false)} title="Action details" description="Focused details stay contained.">
          <LiteActionRow label="Outcome" value="Saved" summary="Sanitized presentation only." />
        </LiteDetailsPanel>
      ) : (
        <LiteSheet open={open} onClose={() => setOpen(false)} title="Manage details" description="Responsive side panel or bottom sheet.">
          <LiteActionRow label="Status" value="Ready" summary="Shared overlay primitive coverage." />
        </LiteSheet>
      )}
    </>,
  );
}

export const ManageSheetOpen = {
  render: () => <SheetHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const opener = canvas.getByRole('button', { name: 'Open Manage' });
    await userEvent.click(opener);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: 'Manage details' });
    await expect(dialog).toBeInTheDocument();
    await expect(within(dialog).getByRole('button', { name: /Close app actions/i })).toBeInTheDocument();
  },
};

export const ManageSheetMobile = {
  ...ManageSheetOpen,
  parameters: { viewport: { defaultViewport: 'mobile390' } },
};

export const DetailsPanelOpen = {
  render: () => <SheetHarness details />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: 'Open Manage' }));
    const body = within(canvasElement.ownerDocument.body);
    await expect(await body.findByRole('dialog', { name: 'Action details' })).toBeInTheDocument();
  },
};
