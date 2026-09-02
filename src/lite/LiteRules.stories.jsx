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
  await expect(within(dialog).getByText(/Protections/i)).toBeInTheDocument();
  await expect(within(dialog).getByText(/Recent protected decisions/i)).toBeInTheDocument();
  await expect(within(dialog).getByText(/Technical status/i)).toBeInTheDocument();
  await expect(within(dialog).queryByText(/Policy engine/i)).not.toBeInTheDocument();
}

export const NoRules = createLiteStory('rules', 'rules-empty', { notes: 'Verified Personal Mode empty-policy presentation.' });
export const RulesPresent = {
  ...createLiteStory('rules', 'rules-present', { notes: 'Verified current server-owned Rules presentation.' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectRules(canvasElement);
    await expect(await canvas.findByText(/Sensitive changes are checked first|Protected/i)).toBeInTheDocument();
    await expect(canvas.queryByText(/Open Policy Agent|Rego|package pocketlab/i)).not.toBeInTheDocument();
  },
};
export const ProtectionHealthy = createLiteStory('rules', 'rules-enabled', { notes: 'Verified enabled/protected Personal Mode presentation.' });
export const RuleEnabled = createLiteStory('rules', 'rules-enabled');
export const RuleDisabled = {
  ...createLiteStory('rules', 'rules-disabled'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRules(canvasElement);
    await expect(await canvas.findByText(/disabled|blocked|attention/i)).toBeInTheDocument();
  },
};
export const RuleValidationError = {
  ...createLiteStory('rules', 'rules-validation-error'),
  play: async ({ canvasElement }) => {
    const canvas = await expectRules(canvasElement);
    await expect(await canvas.findByText(/attention|blocked|validation/i)).toBeInTheDocument();
  },
};
export const RuleExecutionPending = createLiteStory('rules', 'rules-execution-pending', {
  status: 'partial',
  notes: 'Fixture-only pending presentation. It does not claim browser-owned execution or downstream action completion.',
});
export const RulesUnavailable = createLiteStory('rules', 'api-unavailable', { notes: 'Verified fail-closed unavailable presentation.' });

export const ManageRulesOpen = {
  ...createLiteStory('rules', 'rules-enabled', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRules(canvasElement),
};
export const ValidationErrorOpen = {
  ...createLiteStory('rules', 'rules-validation-error', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageRules(canvasElement),
};
export const Mobile320 = createLiteStory('rules', 'rules-enabled', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });

export const EnterpriseApprovalFixture = createLiteStory('rules', 'rules-approval-required', {
  status: 'partial',
  notes: 'Enterprise Rules approvals are implemented and remain permission-only, but this fixture does not by itself activate an Enterprise role/session.',
});
