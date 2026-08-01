import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';
export default { title: 'Pocket Lab Lite/Identity', component: LiteStoryFrame, tags: ['autodocs'] };
export const IdentitySummary = createLiteStory('identity', 'identity-summary', { status: 'partial', notes: 'Current repository summary only.' });
export const PasswordConfigured = createLiteStory('identity', 'identity-password-configured', { status: 'partial' });
export const PasswordChangeRequired = createLiteStory('identity', 'identity-password-change-required', { status: 'partial' });
export const IdentityLoading = createLiteStory('identity', 'slow-response', { status: 'partial' });
export const IdentityUnavailable = createLiteStory('identity', 'api-unavailable', { status: 'partial' });
export const FutureRoleAwareState = createLiteStory('identity', 'identity-role-aware-fixture', { status: 'partial', notes: 'Fixture-only future interface; no role-aware execution is claimed.' });
