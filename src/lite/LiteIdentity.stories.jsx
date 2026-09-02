import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Identity', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectIdentity(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: 'Identity & Access', level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageAccess(canvasElement) {
  const canvas = await expectIdentity(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Access/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage access/i });
  await expect(dialog).toBeInTheDocument();
  await expect(within(dialog).getByText(/Passkeys/i)).toBeInTheDocument();
  await expect(within(dialog).getByText(/Sessions/i)).toBeInTheDocument();
  await expect(within(dialog).getByText(/Recovery/i)).toBeInTheDocument();
}

export const IdentitySummary = {
  ...createLiteStory('identity', 'identity-summary', { notes: 'Current Personal Mode owner/access summary backed by the implemented Lite Identity API.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await expect(await canvas.findByLabelText('Access posture')).toBeInTheDocument();
    await expect(await canvas.findByText(/Passkeys/i)).toBeInTheDocument();
    await expect(await canvas.findByText(/Sessions/i)).toBeInTheDocument();
    await expect(await canvas.findByText(/Recovery/i)).toBeInTheDocument();
  },
};
export const OwnerReady = createLiteStory('identity', 'identity-summary', { notes: 'Verified Personal Mode owner-ready presentation.' });
export const PasswordConfigured = createLiteStory('identity', 'identity-password-configured', { notes: 'Verified current password-configured presentation.' });
export const PasswordChangeRequired = {
  ...createLiteStory('identity', 'identity-password-change-required', { notes: 'Verified current password-change-required presentation.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await expect(await canvas.findByText(/password|change/i)).toBeInTheDocument();
  },
};
export const IdentityLoading = createLiteStory('identity', 'slow-response', { notes: 'Verified loading/deferred-read presentation only; no authentication ceremony is simulated.' });
export const IdentityUnavailable = createLiteStory('identity', 'api-unavailable', { notes: 'Verified unavailable/read-only presentation.' });

export const ManageAccessOpen = {
  ...createLiteStory('identity', 'identity-summary', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageAccess(canvasElement),
};
export const Mobile320 = createLiteStory('identity', 'identity-summary', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });

export const EnterpriseRoleAwareFixture = createLiteStory('identity', 'identity-role-aware-fixture', {
  status: 'partial',
  notes: 'Enterprise Identity source is implemented, but this deterministic fixture does not by itself prove a role-aware Enterprise session is active.',
});
