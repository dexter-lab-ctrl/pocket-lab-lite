import React from 'react';
import { expect, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Home', component: LiteStoryFrame, tags: ['autodocs'] };
export const Healthy = { ...createLiteStory('home', 'healthy'), play: async ({ canvasElement }) => { await expect(within(canvasElement).getByText(/Pocket Lab Lite/i)).toBeInTheDocument(); } };
export const ReviewRecommended = createLiteStory('home', 'lifecycle-attention');
export const ReleaseUpToDate = createLiteStory('home', 'release-current');
export const ReleaseAvailable = createLiteStory('home', 'release-available');
export const ReleaseCheckFailed = createLiteStory('home', 'release-failed');
export const SavedOfflineSnapshot = createLiteStory('home', 'offline-saved');
export const APIUnavailable = createLiteStory('home', 'api-unavailable');
export const Mobile = createLiteStory('home', 'healthy', { viewport: 'mobile360' });
export const Desktop = createLiteStory('home', 'healthy', { viewport: 'desktop' });
