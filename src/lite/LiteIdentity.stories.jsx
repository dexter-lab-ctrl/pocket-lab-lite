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
  await expect(dialog).toHaveTextContent(/Passkeys/i);
  await expect(dialog).toHaveTextContent(/Sessions/i);
  await expect(dialog).toHaveTextContent(/Recovery/i);
}

async function expectEnterpriseRole(canvasElement, role) {
  const canvas = await expectIdentity(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Identity & Access governance/i })).toBeInTheDocument();
  await expect(canvasElement).toHaveTextContent(new RegExp(role, 'i'));
  await expect(canvasElement).toHaveTextContent(/People, roles and Safety Rules use the same server-owned authority model/i);
  return canvas;
}

export const IdentitySummary = {
  ...createLiteStory('identity', 'identity-summary', { notes: 'Personal Mode Owner summary using the unified Identity projection while preserving the established Lite storytelling pattern.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await expect(await canvas.findByLabelText('Access posture')).toBeInTheDocument();
    await expect(canvasElement).toHaveTextContent(/Passkeys/i);
    await expect(canvasElement).toHaveTextContent(/Sessions/i);
    await expect(canvasElement).toHaveTextContent(/Recovery/i);
    await expect(canvasElement).toHaveTextContent(/Personal Mode/i);
  },
};

export const OwnerReady = createLiteStory('identity', 'identity-summary', { notes: 'Personal Mode local Owner ready state.' });
export const PasswordConfigured = createLiteStory('identity', 'identity-password-configured', { notes: 'Password-configured compatibility state.' });
export const PasswordChangeRequired = {
  ...createLiteStory('identity', 'identity-password-change-required'),
  play: async ({ canvasElement }) => {
    await expectIdentity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/password|change|access/i);
  },
};
export const IdentityLoading = createLiteStory('identity', 'slow-response', { notes: 'Loading/deferred-read presentation only; no authentication ceremony is simulated.' });
export const IdentityUnavailable = createLiteStory('identity', 'api-unavailable', { notes: 'Unavailable/read-only presentation.' });

export const ManageAccessOpen = {
  ...createLiteStory('identity', 'identity-summary', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageAccess(canvasElement),
};

export const ContextHelpOpen = {
  ...createLiteStory('identity', 'identity-summary', { viewport: 'desktop', notes: 'Reusable contextual Help contract; the same registry/sheet primitive can be extended to other Lite tabs.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    const help = (await canvas.findAllByRole('button', { name: /Help:/i }))[0];
    await userEvent.click(help);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: /Your Identity & Access overview/i });
    await expect(dialog).toHaveTextContent(/Why it matters/i);
    await expect(dialog).toHaveTextContent(/What to do/i);
  },
};

export const EnterpriseOwner = {
  ...createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'desktop', notes: 'Enterprise Owner is root-equivalent for supported Pocket Lab administration while hard safety and step-up controls remain.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Owner');
    await expect(canvasElement).toHaveTextContent(/No peer approval/i);
    await expect(canvasElement).toHaveTextContent(/Owner is root-equivalent/i);
  },
};

export const EnterpriseAdmin = {
  ...createLiteStory('identity', 'identity-enterprise-admin', { viewport: 'desktop', notes: 'Admin delegated-management story with independent review for protected operations where Rules require it.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Admin');
    await expect(canvasElement).toHaveTextContent(/delegated administration|independent review/i);
  },
};

export const EnterpriseOperator = {
  ...createLiteStory('identity', 'identity-enterprise-operator', { viewport: 'desktop', notes: 'Operator day-to-day access story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Operator');
    await expect(canvasElement).toHaveTextContent(/day-to-day|review/i);
  },
};

export const EnterpriseAuditor = {
  ...createLiteStory('identity', 'identity-enterprise-auditor', { viewport: 'desktop', notes: 'Auditor read-only governance/evidence story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Auditor');
    await expect(canvasElement).toHaveTextContent(/Read-only governance|evidence/i);
  },
};

export const EnterpriseViewer = {
  ...createLiteStory('identity', 'identity-enterprise-viewer', { viewport: 'desktop', notes: 'Viewer read-only workspace evidence story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Viewer');
    await expect(canvasElement).toHaveTextContent(/Read-only workspace/i);
  },
};

export const EnterprisePeopleManagement = {
  ...createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'desktop', notes: 'Owner People management matrix with separate identities and role-aware lifecycle actions.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRole(canvasElement, 'Owner');
    await userEvent.click(await canvas.findByRole('button', { name: 'People' }));
    await expect(await canvas.findByRole('heading', { name: 'People', level: 3 })).toBeInTheDocument();
    await expect(canvasElement).toHaveTextContent(/Add person/i);
    await expect(canvasElement).toHaveTextContent(/New Person/i);
    await expect(canvasElement).toHaveTextContent(/Waiting to join/i);
  },
};

export const Mobile320 = createLiteStory('identity', 'identity-summary', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow remains covered by Playwright.' });
export const EnterpriseMobile = createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'mobile360', notes: 'Enterprise Identity governance narrow-mobile Storybook contract.' });

// Compatibility alias retained for generated documentation that referenced the
// older fixture name. The scenario now exercises a real deterministic Owner
// Enterprise projection rather than a future/partial placeholder.
export const EnterpriseRoleAwareFixture = EnterpriseOwner;
export const FutureRoleAwareState = EnterpriseOwner;
