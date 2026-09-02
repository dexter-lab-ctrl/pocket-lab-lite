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

export const NoRules = createLiteStory('rules', 'rules-empty', { notes: 'Verified Personal Mode empty-policy presentation.' });
export const RulesPresent = {
  ...createLiteStory('rules', 'rules-present', { notes: 'Verified current server-owned Rules presentation.' }),
  play: async ({ canvasElement }) => {
    await expectRules(canvasElement);
    await expect(canvasElement).toHaveTextContent(/Sensitive changes are checked first|Protected/i);
    await expect(canvasElement).not.toHaveTextContent(/Open Policy Agent|Rego|package pocketlab/i);
  },
};
export const ProtectionHealthy = createLiteStory('rules', 'rules-enabled', { notes: 'Verified enabled/protected Personal Mode presentation.' });
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

// Compatibility alias retained because generated UI-state documentation on the
// current base names this fixture. The implementation is no longer described as
// future; the fixture remains partial because it does not activate Enterprise Mode.
export const FutureApprovalRequired = EnterpriseApprovalFixture;
