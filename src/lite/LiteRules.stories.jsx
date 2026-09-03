import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Rules', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectRules(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: 'Safety Rules', level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageRules(canvasElement) {
  const canvas = await expectRules(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Safety Rules/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage Safety Rules/i });
  await expect(dialog).toBeInTheDocument();
  await expect(dialog).toHaveTextContent(/Protections/i);
  await expect(dialog).toHaveTextContent(/Recent protected decisions/i);
  await expect(dialog).toHaveTextContent(/Technical status/i);
  await expect(dialog).not.toHaveTextContent(/Policy engine/i);
}

async function expectEnterpriseRules(canvasElement, role) {
  const canvas = await expectRules(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Rules governance/i })).toBeInTheDocument();
  await expect(canvasElement).toHaveTextContent(new RegExp(role, 'i'));
  await expect(canvasElement).toHaveTextContent(/same server-resolved|same model as Identity/i);
  return canvas;
}

export const NoRules = createLiteStory('rules', 'rules-empty', { notes: 'Personal Mode empty-policy presentation.' });
export const RulesPresent = {
  ...createLiteStory('rules', 'rules-present', { notes: 'Personal Mode current server-owned Rules presentation.' }),
  play: async ({ canvasElement }) => {
    await expectRules(canvasElement);
    await expect(canvasElement).toHaveTextContent(/Protection|Protected/i);
    await expect(canvasElement).not.toHaveTextContent(/package pocketlab/i);
  },
};
export const ProtectionHealthy = createLiteStory('rules', 'rules-enabled', { notes: 'Personal Mode healthy fail-closed protection presentation.' });
export const RuleEnabled = createLiteStory('rules', 'rules-enabled');
export const RuleDisabled = {
  ...createLiteStory('rules', 'rules-disabled'),
  play: async ({ canvasElement }) => {
    await expectRules(canvasElement);
    await expect(canvasElement).toHaveTextContent(/disabled|blocked|attention/i);
  },
};
export const RuleValidationError = {
  ...createLiteStory('rules', 'rules-validation-error'),
  play: async ({ canvasElement }) => {
    await expectRules(canvasElement);
    await expect(canvasElement).toHaveTextContent(/attention|blocked|validation/i);
  },
};
export const RuleExecutionPending = createLiteStory('rules', 'rules-execution-pending', {
  status: 'partial',
  notes: 'Fixture-only pending presentation. It does not claim browser-owned execution or downstream action completion.',
});
export const RulesUnavailable = createLiteStory('rules', 'api-unavailable', { notes: 'Fail-closed unavailable presentation.' });

export const ManageRulesOpen = {
  ...createLiteStory('rules', 'rules-enabled', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRules(canvasElement),
};
export const ValidationErrorOpen = {
  ...createLiteStory('rules', 'rules-validation-error', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRules(canvasElement),
};

export const ContextHelpOpen = {
  ...createLiteStory('rules', 'rules-enabled', { viewport: 'desktop', notes: 'Reusable contextual Help presentation for Safety Rules.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectRules(canvasElement);
    const help = (await canvas.findAllByRole('button', { name: /Help:/i }))[0];
    await userEvent.click(help);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: /Protection/i });
    await expect(dialog).toHaveTextContent(/Why it matters/i);
    await expect(dialog).toHaveTextContent(/What to do/i);
  },
};

export const EnterpriseOwnerProtection = {
  ...createLiteStory('rules', 'rules-enterprise-owner', { viewport: 'desktop', notes: 'Owner root-equivalent protection contract: no peer approval while hard safety guards and root-level passkey step-up remain.' }),
  play: async ({ canvasElement }) => {
    await expectEnterpriseRules(canvasElement, 'Owner');
    await expect(canvasElement).toHaveTextContent(/does not need another human approval|root-level/i);
    await expect(canvasElement).toHaveTextContent(/Direct/i);
  },
};

export const EnterpriseOwnerPolicies = {
  ...createLiteStory('rules', 'rules-enterprise-owner', { viewport: 'desktop', notes: 'Typed immutable candidate/activation lifecycle; no browser Rego editor or pointer mutation.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Owner');
    await userEvent.click(await canvas.findByRole('button', { name: 'Policies' }));
    await expect(await canvas.findByRole('heading', { name: 'Policy settings', level: 3 })).toBeInTheDocument();
    await expect(canvasElement).toHaveTextContent(/browser cannot submit Rego source/i);
    await expect(canvasElement).toHaveTextContent(/Rules revisions/i);
    await expect(canvasElement).toHaveTextContent(/Restore known-good Rules/i);
  },
};

export const EnterpriseAdminReview = {
  ...createLiteStory('rules', 'rules-enterprise-admin', { viewport: 'desktop', notes: 'Admin delegated authority matrix with independent review for device removal under default typed policy.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Admin');
    await expect(canvasElement).toHaveTextContent(/Admin/i);
    await expect(canvasElement).toHaveTextContent(/Review/i);
    await userEvent.click(await canvas.findByRole('button', { name: 'Requests' }));
    await expect(canvasElement).toHaveTextContent(/Review requests/i);
  },
};

export const EnterpriseOperatorReview = {
  ...createLiteStory('rules', 'rules-enterprise-operator', { viewport: 'desktop', notes: 'Operator day-to-day authority with review requirement for protected device removal.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Operator');
    await expect(canvasElement).toHaveTextContent(/Review/i);
    await userEvent.click(await canvas.findByRole('button', { name: 'Requests' }));
    await expect(canvasElement).toHaveTextContent(/Cancel request|independent review/i);
  },
};

export const EnterpriseAuditorReadOnly = {
  ...createLiteStory('rules', 'rules-enterprise-auditor', { viewport: 'desktop', notes: 'Auditor can review evidence and run non-executing bounded simulation, but cannot mutate Rules.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Auditor');
    await userEvent.click(await canvas.findByRole('button', { name: 'Test a change' }));
    await expect(canvasElement).toHaveTextContent(/This never executes the real action/i);
    await userEvent.click(await canvas.findByRole('button', { name: 'Policies' }));
    await expect(canvasElement).toHaveTextContent(/Policy editing is not available to this role/i);
  },
};

export const EnterpriseViewerReadOnly = {
  ...createLiteStory('rules', 'rules-enterprise-viewer', { viewport: 'desktop', notes: 'Viewer receives bounded recorded decision evidence but no mutation, simulation, requests, or exception authority.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Viewer');
    await userEvent.click(await canvas.findByRole('button', { name: 'Activity' }));
    await expect(canvasElement).toHaveTextContent(/Rules decision proves policy evaluation only/i);
    await userEvent.click(await canvas.findByRole('button', { name: 'Test a change' }));
    await expect(canvasElement).toHaveTextContent(/Simulation is not available to this role/i);
  },
};

export const EnterpriseRequests = {
  ...createLiteStory('rules', 'rules-approval-required', { viewport: 'desktop', notes: 'Delegated Operator request: exact target/revision, short-lived and permission-only.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectEnterpriseRules(canvasElement, 'Operator');
    await userEvent.click(await canvas.findByRole('button', { name: 'Requests' }));
    await expect(canvasElement).toHaveTextContent(/short-lived|one-time/i);
    await expect(canvasElement).toHaveTextContent(/Cancel request/i);
  },
};

export const Mobile320 = createLiteStory('rules', 'rules-enabled', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow remains covered by Playwright.' });
export const EnterpriseMobile = createLiteStory('rules', 'rules-enterprise-owner', { viewport: 'mobile360', notes: 'Enterprise Rules governance narrow-mobile Storybook contract.' });

// Compatibility aliases retained for generated documentation. These now point
// at deterministic, implemented Enterprise governance states rather than a
// future/partial capability placeholder.
export const EnterpriseApprovalFixture = EnterpriseRequests;
export const FutureApprovalRequired = EnterpriseRequests;
