import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default {
  title: 'Pocket Lab Lite/Recovery Parity',
  component: LiteStoryFrame,
  tags: ['autodocs'],
  parameters: {
    pocketlab: {
      generated_registry: 'src/test/fixtures/generated/parity/recovery-parity.js',
      authority: 'FastAPI payload fixture → selectRecoveryScreenView → React UI',
      warning: 'Fixtures are deterministic test evidence, not backend authority.',
    },
  },
};

const parityStory = (scenario, scenarioId, options = {}) => ({
  ...createLiteStory('recovery', scenario, options),
  parameters: {
    ...createLiteStory('recovery', scenario, options).parameters,
    pocketlab: {
      ...createLiteStory('recovery', scenario, options).parameters.pocketlab,
      parity_scenario_id: scenarioId,
      fixture: `src/test/fixtures/generated/parity/recovery/${scenarioId}.json`,
    },
  },
});

export const BackendUnavailable = parityStory('nats-down', 'recovery-backend-unavailable', { status: 'partial' });
export const BackupFailed = parityStory('worker-down', 'recovery-backup-failed', { status: 'partial' });
export const BackupRunning = parityStory('healthy', 'recovery-backup-running');
export const ConfirmationRequired = parityStory('healthy', 'recovery-confirmation-required');
export const Empty = parityStory('healthy', 'recovery-empty');
export const OfflineSnapshot = parityStory('nats-down', 'recovery-offline-snapshot');
export const PreviewReady = parityStory('healthy', 'recovery-preview-ready');
export const ProjectionStale = parityStory('recovery-projection-too-old', 'recovery-projection-stale');
export const RestoreCompleted = parityStory('healthy', 'recovery-restore-completed', { status: 'partial' });
export const RestoreFailed = parityStory('worker-down', 'recovery-restore-failed', { status: 'partial' });
export const RestoreRunning = parityStory('healthy', 'recovery-restore-running', { status: 'partial' });
export const RollbackCompleted = parityStory('healthy', 'recovery-rollback-completed', { status: 'partial' });
export const VerificationFailed = parityStory('worker-down', 'recovery-verification-failed');
export const VerificationRunning = parityStory('healthy', 'recovery-verification-running');
export const Verified = parityStory('healthy', 'recovery-verified');
