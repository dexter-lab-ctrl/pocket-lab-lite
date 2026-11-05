// AUTHORED — NOT RUN · implementation-only session
import React from 'react';
import RecoveryJourney from './RecoveryJourney.jsx';
import RecoveryPremiumTimeline from './RecoveryPremiumTimeline.jsx';
import RecoveryRestoreAssistant from './RecoveryRestoreAssistant.jsx';
import RecoveryConfirmSheetLazy from './RecoveryConfirmSheetLazy.jsx';

export default {
  title: 'Pocket Lab Lite/Recovery/Azure Horizon Recovery Center',
  tags: ['autodocs'],
  parameters: { layout: 'padded', pocketlab: { qualification: 'NOT RUN — implementation-only session', authority: 'Projected FastAPI facts; interactions never create a restore' } },
};
const status = (backup, verify, preview, restore) => ({ backup, verify, preview, restore });
const activity = [{ id:'synthetic-backup-record', kind:'backup', title:'Latest backup record', summary:'The current backup record is marked verified.', time:'2026-10-10T10:42:00Z', state:'completed', origin:'snapshot' }];
const states = {
  HealthyVerified: status('completed','completed','needs_action','blocked'),
  NoBackup: status('not_started','blocked','blocked','blocked'),
  VerificationRequired: status('completed','needs_action','blocked','blocked'),
  PreviewRequired: status('completed','completed','needs_action','blocked'),
  PreviewReady: status('completed','completed','completed','available'),
  DestinationUnavailable: status('blocked','blocked','blocked','blocked'),
  BackupRunning: status('in_progress','unknown','unknown','unknown'),
  VerificationRunning: status('completed','in_progress','unknown','unknown'),
  RestoreRunning: status('completed','completed','completed','in_progress'),
  RestoreFailed: status('completed','completed','completed','failed'),
  RestoreCompleted: status('completed','completed','completed','completed'),
  PartialProtection: status('completed','needs_action','blocked','blocked'),
  DatabaseGuardActive: status('completed','completed','blocked','blocked'),
  ProjectionStale: status('unknown','unknown','unknown','unknown'),
  BackendUnavailable: status('unknown','unknown','unknown','unknown'),
  EmptyHistory: status('not_started','blocked','blocked','blocked'),
  PopulatedHistory: status('completed','completed','completed','available'),
  Unknown: status('unknown','unknown','unknown','unknown'),
};
const JourneyStory = ({ name, saved = false }) => <div style={{ maxWidth: 860 }}>
  <RecoveryJourney stages={states[name] || states.Unknown} saved={saved} />
  <RecoveryPremiumTimeline items={name === 'EmptyHistory' ? [] : activity} saved={saved} onViewActivity={() => {}} />
</div>;
export const HealthyVerified = { render: () => <JourneyStory name="HealthyVerified"/> };
export const NoBackup = { render: () => <JourneyStory name="NoBackup"/> };
export const VerificationRequired = { render: () => <JourneyStory name="VerificationRequired"/> };
export const PreviewRequired = { render: () => <JourneyStory name="PreviewRequired"/> };
export const PreviewReady = { render: () => <JourneyStory name="PreviewReady"/> };
export const DestinationUnavailable = { render: () => <JourneyStory name="DestinationUnavailable"/> };
export const BackupRunning = { render: () => <JourneyStory name="BackupRunning"/> };
export const VerificationRunning = { render: () => <JourneyStory name="VerificationRunning"/> };
export const RestoreRunning = { render: () => <JourneyStory name="RestoreRunning"/> };
export const RestoreFailed = { render: () => <JourneyStory name="RestoreFailed"/> };
export const RestoreCompleted = { render: () => <JourneyStory name="RestoreCompleted"/> };
export const PartialProtection = { render: () => <JourneyStory name="PartialProtection"/> };
export const DatabaseGuardActive = { render: () => <JourneyStory name="DatabaseGuardActive"/> };
export const ProjectionStale = { render: () => <JourneyStory name="ProjectionStale" saved/> };
export const BackendUnavailable = { render: () => <JourneyStory name="BackendUnavailable" saved/> };
export const OfflineSaved = { render: () => <JourneyStory name="HealthyVerified" saved/> };
export const HistoryEmpty = { render: () => <JourneyStory name="EmptyHistory"/> };
export const HistoryPopulated = { render: () => <JourneyStory name="PopulatedHistory"/> };
export const Unknown = { render: () => <JourneyStory name="Unknown"/> };
export const LongLocalizedText = { render: () => <div style={{ maxWidth:320, fontSize:'200%' }}><JourneyStory name="VerificationRequired"/></div> };
export const RestoreAssistantChoose = { render: () => <RecoveryRestoreAssistant step="choose" onStepChange={() => {}}>Select a safe restore point from the library.</RecoveryRestoreAssistant> };
export const RestoreAssistantReview = { render: () => <RecoveryRestoreAssistant step="safety" verified previewReady onStepChange={() => {}}>Live backend checks still determine the outcome.</RecoveryRestoreAssistant> };
export const RestoreAssistantBlocked = { render: () => <RecoveryRestoreAssistant step="confirm" verified={false} previewReady={false} writeBlocked onStepChange={() => {}}/> };
const backup = {backup_id:'synthetic-backup',verification_status:'verified',created_at:'2026-10-10T10:42:00Z'};
export const RestoreConfirmationGuarded = { render: () => <RecoveryConfirmSheetLazy backup={backup} preview={{preview_id:'synthetic-preview',backup_id:'other-backup',status:'ready'}} onCancel={() => {}} onConfirm={() => {}} /> };
export const RestoreConfirmationReady = { render: () => <RecoveryConfirmSheetLazy backup={backup} preview={{preview_id:'synthetic-preview',backup_id:backup.backup_id,status:'ready'}} onCancel={() => {}} onConfirm={() => {}} /> };
