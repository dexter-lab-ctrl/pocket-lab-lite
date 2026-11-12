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
