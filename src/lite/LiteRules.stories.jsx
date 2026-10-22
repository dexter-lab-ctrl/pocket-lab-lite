import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Rules', component: LiteStoryFrame, tags: ['autodocs'] };
const rules = (scenario, options = {}) => createLiteStory('rules', scenario, options);
async function openManage(canvasElement, section = 'Overview') {
  const canvas = within(canvasElement);
  await userEvent.click(await canvas.findByRole('button', { name: 'Manage Safety Rules' }));
  const sheet = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Manage Safety Rules' });
  await userEvent.click(within(sheet).getByRole('button', { name: section, exact: true }));
  return sheet;
}
export const NoRules = rules('rules-empty');
export const RulesPresent = rules('rules-present');
export const ProtectionHealthy = rules('rules-enabled', { notes: 'Authoritative Personal protection; one hero and latest server-backed decision.' });
export const RuleEnabled = ProtectionHealthy;
export const PersonalReady = ProtectionHealthy;
export const RuleDisabled = rules('rules-disabled', { notes: 'Degraded source, no manufactured Ready state.' });
export const PersonalNeedsAttention = RuleDisabled;
export const RuleValidationError = rules('rules-validation-error');
export const RuleExecutionPending = rules('rules-execution-pending', { status: 'partial', notes: 'Illustrative fixture; no backend operation inferred.' });
export const RulesUnavailable = rules('api-unavailable', { notes: 'Unconfirmed protection; no optimistic access.' });
export const SavedOffline = rules('api-unavailable', { notes: 'Saved-read fallback where available, never live authority.' });
export const Mobile320 = rules('rules-enabled', { viewport: 'mobile360', notes: '320px contract separately authored for Playwright.' });
export const EnterpriseMobile = rules('rules-enterprise-owner', { viewport: 'mobile360' });
export const EnterpriseOwnerProtection = rules('rules-enterprise-owner');
export const EnterpriseAdminReview = rules('rules-enterprise-admin');
export const EnterpriseOperatorReview = rules('rules-enterprise-operator');
export const EnterpriseAuditorReadOnly = rules('rules-enterprise-auditor');
export const EnterpriseViewerReadOnly = rules('rules-enterprise-viewer');
export const EnterpriseRequests = rules('rules-approval-required');
export const EnterpriseApprovalFixture = EnterpriseRequests;
export const FutureApprovalRequired = EnterpriseRequests;
export const EmptyDecisions = rules('rules-empty');
export const MultipleDecisions = rules('rules-present');
export const AllowedDecision = rules('rules-enabled');
export const BlockedDecision = rules('rules-disabled');
export const StepUpRequired = rules('rules-premium-step-up', { notes: 'Step-up surfaces are shown only when backend reports the requirement.' });
export const PendingApproval = rules('rules-premium-approval');
export const ActivationRunning = rules('rules-execution-pending', { notes: 'Server-reported activation only; no inferred success.' });
export const ActivationFailed = rules('rules-validation-error');
export const Rollback = rules('rules-validation-error', { notes: 'Recovery outcome must be returned by server; this story does not invent a rollback event.' });
export const MissingRevision = rules('rules-empty');
export const ReducedMotion = rules('rules-enabled', { notes: 'Playwright emulates prefers-reduced-motion; CSS disables new transitions.' });
export const LongText = rules('rules-premium-long', { textScale: 2, notes: 'Long text and 200% text scale layout scenario.' });
export const NarrowMobile = rules('rules-enabled', { viewport: 'mobile360' });
export const ManageRulesOpen = {
  ...rules('rules-enabled', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement, 'Protections');
    await expect(sheet).toHaveTextContent(/Protected actions/i);
  },
};
export const EnterpriseOwnerPolicies = {
  ...rules('rules-enterprise-owner', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement, 'Policies');
    await expect(sheet).toHaveTextContent(/Policy settings/i);
  },
};
export const DecisionHistoryOpen = {
  ...rules('rules-enabled', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement, 'Decisions');
    await expect(sheet).toHaveTextContent(/Decision History/i);
  },
};
export const ProtectionJourneyExpanded = {
  ...rules('rules-enabled'),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByRole('button', { name: /Check Evaluate/i }));
    await expect(canvasElement).toHaveTextContent(/evaluates the applicable Rules/i);
  },
};
export const DecisionInsightOpen = {
  ...rules('rules-present', { viewport: 'desktop', notes: 'Opens only when the server fixture provides a protected decision.' }),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const buttons = canvas.queryAllByRole('button', { name: 'Explain this' });
    if (buttons.length) {
      await userEvent.click(buttons[0]);
      await expect(await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Decision Insight' })).toBeInTheDocument();
    }
  },
};
export const ContextHelpOpen = {
  ...rules('rules-enabled'),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const help = (await canvas.findAllByRole('button', { name: /Help:/i }))[0];
    await userEvent.click(help);
  },
};

// Azure Horizon Rules fixtures — DEFINED, NOT EXECUTED in this implementation session.
export const AzureRulesBlack = rules('rules-present', { viewport: 'desktop', notes: 'Use global Black appearance toolbar.' });
export const AzureRulesDaylight = rules('rules-enabled', { viewport: 'desktop', notes: 'Use global Daylight appearance toolbar.' });
export const AzureRulesSystem = rules('rules-enabled', { notes: 'Use existing System appearance preference.' });
export const AzureRulesVerticalJourney = rules('rules-premium-long', { viewport: 'mobile360', textScale: 2 });
export const AzureRulesEnterprisePolicies = EnterpriseOwnerPolicies;
export const AzureRulesDecisionInsight = DecisionInsightOpen;
export const AzureRulesManageDesktop = ManageRulesOpen;
export const AzureRulesManageMobile = rules('rules-enabled', { viewport: 'mobile360' });
export const AzureRulesSimulation = {
  ...rules('rules-enterprise-owner', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement,'Test a Change');
    await expect(sheet).toHaveTextContent(/Simulation only/i);
  },
};
export const AzureRulesTemporaryAccess = {
  ...rules('rules-enterprise-owner', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement,'Temporary Access');
    await expect(sheet).toHaveTextContent(/Exact scope only/i);
  },
};
export const AzureRulesReviewRequests = {
  ...rules('rules-approval-required', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const sheet = await openManage(canvasElement,'Requests');
    await expect(sheet).toHaveTextContent(/Review requests/i);
  },
};
