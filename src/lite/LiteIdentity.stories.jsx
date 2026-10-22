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
  await expect(dialog.getByRole('button', { name: 'Recovery', exact: true })).toBeInTheDocument();
}

async function expectEnterpriseRole(canvasElement, role) {
  const canvas = await expectIdentity(canvasElement);
  const trigger = await canvas.findByRole('button', { name: /Manage Access/i });
  await userEvent.click(trigger);
  const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: /Manage access/i });
  await userEvent.click(within(dialog).getByRole('button', { name: 'Roles & Access' }));
  await expect(dialog).toHaveTextContent(new RegExp(role, 'i'));
  await expect(dialog).toHaveTextContent(/Effective capability matrix/i);
  return dialog;
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
    const dialog = within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i });
    await expect(dialog).toHaveTextContent(/Owner/i);
  },
};

export const EnterpriseAdmin = {
  ...createLiteStory('identity', 'identity-enterprise-admin', { viewport: 'desktop', notes: 'Admin delegated-management story with independent review for protected operations where Rules require it.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Admin');
    await expect(within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i })).toHaveTextContent(/Admin/i);
  },
};

export const EnterpriseOperator = {
  ...createLiteStory('identity', 'identity-enterprise-operator', { viewport: 'desktop', notes: 'Operator day-to-day access story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Operator');
    await expect(within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i })).toHaveTextContent(/Operator/i);
  },
};

export const EnterpriseAuditor = {
  ...createLiteStory('identity', 'identity-enterprise-auditor', { viewport: 'desktop', notes: 'Auditor read-only governance/evidence story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Auditor');
    await expect(within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i })).toHaveTextContent(/Auditor/i);
  },
};

export const EnterpriseViewer = {
  ...createLiteStory('identity', 'identity-enterprise-viewer', { viewport: 'desktop', notes: 'Viewer read-only workspace evidence story.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRole(canvasElement, 'Viewer');
    await expect(within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i })).toHaveTextContent(/Viewer/i);
  },
};

export const EnterprisePeopleManagement = {
  ...createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'desktop', notes: 'Owner People management matrix with separate identities and role-aware lifecycle actions.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRole(canvasElement, 'Owner');
    const dialog = within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'People', exact: true }));
    await expect(dialog).toHaveTextContent(/Add person/i);
    await expect(dialog).toHaveTextContent(/New Person/i);
    await expect(dialog).toHaveTextContent(/Waiting to join/i);
  },
};

export const Mobile320 = createLiteStory('identity', 'identity-summary', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow remains covered by Playwright.' });
export const EnterpriseMobile = createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'mobile360', notes: 'Enterprise Identity governance narrow-mobile Storybook contract.' });

// Compatibility alias retained for generated documentation that referenced the
// older fixture name. The scenario now exercises a real deterministic Owner
// Enterprise projection rather than a future/partial placeholder.
export const EnterpriseRoleAwareFixture = EnterpriseOwner;
export const FutureRoleAwareState = EnterpriseOwner;


// P3 deterministic premium states. These are source/fixture definitions only until qualification.
export const PremiumAccessJourney = {
  ...createLiteStory('identity', 'identity-summary', { viewport: 'desktop', notes: 'Conceptual four-stage Journey, not an authentication progress engine.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await expect(await canvas.findByRole('heading', { name: 'How your access fits together' })).toBeInTheDocument();
    await userEvent.click(canvas.getByRole('button', { name: 'View Recovery details' }));
    await expect(await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: /Access Details/i })).toHaveTextContent(/Recovery/i);
  },
};
export const PremiumPasskeysMultiple = createLiteStory('identity', 'identity-premium-multiple');
export const PremiumSessionsMultiple = createLiteStory('identity', 'identity-premium-multiple');
export const PremiumRecoveryMissing = createLiteStory('identity', 'identity-premium-recovery-missing');
export const PremiumPasskeysMissing = createLiteStory('identity', 'identity-premium-no-passkeys');
export const PremiumFactsUnavailable = createLiteStory('identity', 'identity-premium-unavailable-facts');
export const PremiumSignedOut = createLiteStory('identity', 'identity-premium-signed-out');
export const PremiumFirstOwner = createLiteStory('identity', 'identity-premium-first-owner');
export const PremiumPersonEnrollment = createLiteStory('identity', 'identity-premium-enrollment');
export const PremiumLongText = createLiteStory('identity', 'identity-premium-long-text', { viewport: 'mobile360', textScale: 2 });
export const PremiumReducedMotion = createLiteStory('identity', 'identity-premium-multiple', { viewport: 'mobile360', notes: 'Reduced-motion assertion belongs to focused mocked Playwright.' });
export const PremiumActivityOutcomes = createLiteStory('identity', 'identity-premium-multiple');
export const PremiumActivityEmpty = createLiteStory('identity', 'identity-summary');
export const OwnerOperationPending = {
  ...createLiteStory('identity', 'identity-owner-operation-pending', { viewport: 'desktop', notes: 'One server-owned bounded Photo Backup operation awaiting real Owner approval.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await expect(canvas).toHaveTextContent(/Pending approvals/i);
    await expect(canvas).toHaveTextContent(/Secondary Phone/i);
    await expect(canvas).toHaveTextContent(/one safe repeat/i);
  },
};
export const OwnerOperationsMultiple = createLiteStory('identity', 'identity-owner-operations-multiple', { viewport: 'desktop', notes: 'Multiple immutable pending operations remain separately reviewable.' });
export const OwnerOperationExpired = createLiteStory('identity', 'identity-owner-operation-expired', { notes: 'Expired operation is visible as terminal evidence without approval controls.' });
export const OwnerOperationApprovedExecuting = createLiteStory('identity', 'identity-owner-operation-executing', { viewport: 'desktop', notes: 'Server-owned execution progress after approval; no second Owner action is implied.' });
export const OwnerOperationCompleted = createLiteStory('identity', 'identity-owner-operation-completed', { viewport: 'desktop', notes: 'Completed bounded operation with indexing truth kept explicit.' });
export const OwnerOperationFailed = createLiteStory('identity', 'identity-owner-operation-failed', { notes: 'Safe terminal failure with no replayable approval action.' });
export const OwnerOperationOfflineSaved = createLiteStory('identity', 'identity-owner-operation-offline', { viewport: 'mobile360', notes: 'Saved operation state is review-only; backend freshness prevents approval.' });
export const TrustedAutomationClientPending = {
  ...createLiteStory('identity', 'identity-owner-client-pairing-pending', { viewport: 'desktop', notes: 'Pending requester pairing is visibly distinct from Photo Backup operation approval and remains passkey-protected.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectIdentity(canvasElement);
    await userEvent.click(await canvas.findByRole('button', { name: /Manage Access/i }));
    const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: /Manage access/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Trusted automation clients' }));
    await expect(dialog).toHaveTextContent(/Pending client registration/i);
    await expect(dialog).toHaveTextContent(/photo_backup\.bounded_acceptance\.v1/i);
    await expect(dialog).toHaveTextContent(/Public-key fingerprint/i);
  },
};
export const TrustedAutomationClientRegistered = createLiteStory('identity', 'identity-owner-client-registered', { viewport: 'desktop', notes: 'Owner-managed registered requester with fixed capability and revocation control.' });
export const TrustedAutomationClientsMultiple = createLiteStory('identity', 'identity-owner-client-multiple', { viewport: 'desktop', notes: 'Pending and registered requester states remain separate and reviewable.' });
export const TrustedAutomationClientExpired = createLiteStory('identity', 'identity-owner-client-expired', { notes: 'Expired pairing remains visible as terminal evidence without registration controls.' });
export const TrustedAutomationClientOfflineSaved = createLiteStory('identity', 'identity-owner-client-offline', { viewport: 'mobile360', notes: 'Saved pairing state is review-only; backend freshness prevents registration.' });
export const PremiumProtectedConfirmation = {
  ...createLiteStory('identity', 'identity-summary', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    await openManageAccess(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = body.getByRole('dialog', { name: /Manage access/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Recovery', exact: true }));
    await userEvent.click(within(dialog).getByRole('button', { name: /Generate New Codes/i }));
    await expect(await body.findByRole('dialog', { name: /Generate new recovery codes/i })).toHaveTextContent(/older/i);
  },
};
export const PremiumPeopleDetails = {
  ...createLiteStory('identity', 'identity-enterprise-owner', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    await openManageAccess(canvasElement);
    const dialog = within(canvasElement.ownerDocument.body).getByRole('dialog', { name: /Manage access/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'People', exact: true }));
    await userEvent.click(within(dialog).getAllByRole('button', { name: /Open Details/i })[0]);
    await expect(await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: /Access Details/i })).toHaveTextContent(/Owner/i);
  },
};

// Azure Horizon Black/Daylight reference states. IMPLEMENTED FIXTURES — UNVALIDATED.
export const AzurePersonalBlack = createLiteStory('identity','identity-summary',{viewport:'desktop',theme:'dark',status:'unvalidated'});
export const AzurePersonalDaylight = createLiteStory('identity','identity-summary',{viewport:'desktop',theme:'daylight',status:'unvalidated'});
export const AzurePersonalSystem = createLiteStory('identity','identity-summary',{viewport:'mobile390',theme:'system',status:'unvalidated'});
export const AzureMobileBlack = createLiteStory('identity','identity-summary',{viewport:'mobile360',theme:'dark',status:'unvalidated'});
export const AzureMobileDaylight = createLiteStory('identity','identity-summary',{viewport:'mobile360',theme:'daylight',status:'unvalidated'});
export const AzureLargeTextBlack = createLiteStory('identity','identity-premium-long-text',{viewport:'mobile360',theme:'dark',textScale:2,status:'unvalidated'});
export const AzureUnavailableBlack = createLiteStory('identity','api-unavailable',{viewport:'mobile360',theme:'dark',status:'unvalidated'});
export const AzureOwnerSetupBlack = createLiteStory('identity','identity-premium-first-owner',{viewport:'mobile360',theme:'dark',status:'unvalidated'});
export const AzureSignedOutDaylight = createLiteStory('identity','identity-premium-signed-out',{viewport:'desktop',theme:'daylight',status:'unvalidated'});
export const AzureOwnerGovernanceBlack = createLiteStory('identity','identity-enterprise-owner',{viewport:'desktop',theme:'dark',status:'unvalidated'});
export const AzureAdminGovernanceDaylight = createLiteStory('identity','identity-enterprise-admin',{viewport:'mobile360',theme:'daylight',status:'unvalidated'});
export const AzureOwnerPendingBlack = createLiteStory('identity','identity-owner-operation-pending',{viewport:'desktop',theme:'dark',status:'unvalidated'});
export const AzureTrustedClientDaylight = createLiteStory('identity','identity-owner-client-pairing-pending',{viewport:'desktop',theme:'daylight',status:'unvalidated'});
export const AzureSavedApprovalBlack = createLiteStory('identity','identity-owner-operation-offline',{viewport:'mobile360',theme:'dark',status:'unvalidated'});
