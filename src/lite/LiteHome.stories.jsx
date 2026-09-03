import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Home', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectHome(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
  await expect(await canvas.findByRole('button', { name: 'Workspace details' })).toBeEnabled();
  return canvas;
}

async function openWorkspaceDetails(canvasElement) {
  const canvas = await expectHome(canvasElement);
  const opener = await canvas.findByRole('button', { name: 'Workspace details' });
  await userEvent.click(opener);
  const body = within(canvasElement.ownerDocument.body);
  await expect(await body.findByRole('dialog', { name: /Workspace details/i })).toBeInTheDocument();
}

export const Healthy = {
  ...createLiteStory('home', 'healthy'),
  play: async ({ canvasElement }) => {
    const canvas = await expectHome(canvasElement);
    await expect(canvas.queryByText(/Showing saved information/i)).not.toBeInTheDocument();
  },
};

export const ReviewRecommended = {
  ...createLiteStory('home', 'lifecycle-attention'),
  play: async ({ canvasElement }) => {
    const canvas = await expectHome(canvasElement);
    await expect(await canvas.findByText(/attention|review/i)).toBeInTheDocument();
  },
};

export const ReleaseUpToDate = createLiteStory('home', 'release-current');
export const ReleaseAvailable = {
  ...createLiteStory('home', 'release-available'),
  play: async ({ canvasElement }) => {
    const canvas = await expectHome(canvasElement);
    await expect(await canvas.findByText(/release|update/i)).toBeInTheDocument();
  },
};
export const ReleaseCheckFailed = createLiteStory('home', 'release-failed');

export const SavedOfflineSnapshot = {
  ...createLiteStory('home', 'offline-saved'),
  play: async ({ canvasElement }) => {
    const canvas = await expectHome(canvasElement);
    await expect(await canvas.findByText(/saved/i)).toBeInTheDocument();
  },
};

export const APIUnavailable = {
  ...createLiteStory('home', 'api-unavailable'),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(await canvas.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: /Refresh/i })).toBeInTheDocument();
  },
};

export const HealthyManageOpen = {
  ...createLiteStory('home', 'healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openWorkspaceDetails(canvasElement),
};

export const AttentionManageOpen = {
  ...createLiteStory('home', 'lifecycle-attention', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openWorkspaceDetails(canvasElement),
};

export const SavedOfflineManageOpen = {
  ...createLiteStory('home', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openWorkspaceDetails(canvasElement),
};

export const Narrow320 = createLiteStory('home', 'healthy', { viewport: 'mobile360', notes: 'Narrow mobile density guard; Playwright covers the exact 320px viewport.' });
export const Mobile = createLiteStory('home', 'healthy', { viewport: 'mobile360' });
export const Desktop = createLiteStory('home', 'healthy', { viewport: 'desktop' });
