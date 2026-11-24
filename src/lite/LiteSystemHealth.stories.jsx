import React from 'react';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

// Real registered screen, with deterministic mock API. Qualification not run.
export default { title: 'Pocket Lab Lite/Azure Horizon/System Health', component: LiteStoryFrame, tags: ['autodocs'] };
export const HealthyLightDesktop = createLiteStory('system-health', 'system-health-healthy', { theme: 'daylight', viewport: 'desktop' });
export const HealthyDarkDesktop = createLiteStory('system-health', 'system-health-healthy', { theme: 'dark', viewport: 'desktop' });
export const AttentionDarkDesktop = createLiteStory('system-health', 'system-health-attention', { theme: 'dark', viewport: 'desktop' });
export const AttentionLightMobile = createLiteStory('system-health', 'system-health-attention', { theme: 'daylight', viewport: 'mobile390' });
export const StaleDarkMobile = createLiteStory('system-health', 'system-health-stale', { theme: 'dark', viewport: 'mobile360' });
export const NoEvidenceLightMobile = createLiteStory('system-health', 'system-health-unknown', { theme: 'daylight', viewport: 'mobile390' });
export const ResolvedDesktop = createLiteStory('system-health', 'system-health-resolved', { theme: 'dark', viewport: 'desktop' });
export const TwoHundredPercentText = createLiteStory('system-health', 'system-health-attention', { theme: 'daylight', viewport: 'mobile360', textScale: 2 });

export const CriticalLightDesktop = createLiteStory('system-health', 'system-health-critical', { theme: 'daylight', viewport: 'desktop' });
export const CriticalDarkMobile = createLiteStory('system-health', 'system-health-critical', { theme: 'dark', viewport: 'mobile390' });
export const SavedOnlyDesktop = createLiteStory('system-health', 'system-health-saved-only', { theme: 'daylight', viewport: 'desktop' });
export const MixedCurrentSavedDesktop = createLiteStory('system-health', 'system-health-mixed', { theme: 'dark', viewport: 'desktop' });
export const MixedCurrentSavedMobile = createLiteStory('system-health', 'system-health-mixed', { theme: 'daylight', viewport: 'mobile360' });
export const OfflineSavedMobile = createLiteStory('system-health', 'system-health-offline', { theme: 'dark', viewport: 'mobile390' });
export const NoIncidentsDesktop = createLiteStory('system-health', 'system-health-healthy', { theme: 'daylight', viewport: 'desktop' });
export const ManyIncidentsDesktop = createLiteStory('system-health', 'system-health-many', { theme: 'dark', viewport: 'desktop' });
export const ManyIncidentsMobile = createLiteStory('system-health', 'system-health-many', { theme: 'daylight', viewport: 'mobile390' });
export const StaleUnresolvedDesktop = createLiteStory('system-health', 'system-health-saved-only', { theme: 'dark', viewport: 'desktop' });
export const ObservedRecoveryMobile = createLiteStory('system-health', 'system-health-observed-recovery', { theme: 'daylight', viewport: 'mobile390' });
export const VerifiedRepairDesktop = createLiteStory('system-health', 'system-health-verified-repair', { theme: 'dark', viewport: 'desktop' });
export const FailedRepairDesktop = createLiteStory('system-health', 'system-health-failed-repair', { theme: 'daylight', viewport: 'desktop' });
export const BlockedRepairMobile = createLiteStory('system-health', 'system-health-blocked-repair', { theme: 'dark', viewport: 'mobile360' });
export const LongTechnicalIdentifier = createLiteStory('system-health', 'system-health-long-identifier', { theme: 'dark', viewport: 'mobile360' });
export const MalformedTarget = createLiteStory('system-health', 'system-health-malformed-target', { theme: 'daylight', viewport: 'mobile390' });
export const ManageDesktop = createLiteStory('system-health', 'system-health-mixed', { theme: 'daylight', viewport: 'desktop', notes: 'Open Manage for responsive geometry qualification.' });
export const ManageMobile = createLiteStory('system-health', 'system-health-mixed', { theme: 'dark', viewport: 'mobile390', notes: 'Open Manage for mobile sheet qualification.' });
export const ManageLight = createLiteStory('system-health', 'system-health-attention', { theme: 'daylight', viewport: 'desktop' });
export const ManageDark = createLiteStory('system-health', 'system-health-attention', { theme: 'dark', viewport: 'desktop' });

/** P4 membership stories — ADDED, NOT RUN. */
export const EnrolledAndRemovedDesktop = createLiteStory('system-health', 'system-health-p4-membership', { theme: 'daylight', viewport: 'desktop' });
export const EnrolledAndRemovedMobile = createLiteStory('system-health', 'system-health-p4-membership', { theme: 'dark', viewport: 'mobile390' });
