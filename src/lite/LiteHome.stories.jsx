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

/*
 * Azure Home panel source states. Not approved visual baselines; these stories
 * use the existing Lite Story Frame, mocked FastAPI reads and portal primitive.
 */
async function openRecentActivity(canvasElement, section = 'Attention') {
  const canvas = await expectHome(canvasElement);
  await userEvent.click(await canvas.findByRole('button', { name: /View activity/i }));
  const documentBody = within(canvasElement.ownerDocument.body);
  const dialog = await documentBody.findByRole('dialog', { name: 'Recent activity' });
  await userEvent.click(within(dialog).getByRole('button', { name: section, exact: true }));
  return dialog;
}

function homePanelStory({ panel, theme, viewport = 'desktop', scenario = 'healthy', section = 'Attention', textScale = 1, notes = '' }) {
  return {
    ...createLiteStory('home', scenario, {
      theme, viewport, textScale, status: 'unvalidated',
      notes: notes || 'Source story only; no screenshot or accessibility qualification yet.',
    }),
    play: async ({ canvasElement }) => {
      if (panel === 'workspace') {
        await openWorkspaceDetails(canvasElement);
        if (section === 'Service health') {
          const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Workspace details' });
          await userEvent.click(within(dialog).getByRole('button', { name: 'Service health' }));
        }
      } else await openRecentActivity(canvasElement, section);
    },
  };
}

export const AzureWorkspaceDaylightDesktop = homePanelStory({ panel: 'workspace', theme: 'daylight' });
export const AzureWorkspaceBlackDesktop = homePanelStory({ panel: 'workspace', theme: 'dark' });
export const AzureWorkspaceDaylightMobile = homePanelStory({ panel: 'workspace', theme: 'daylight', viewport: 'mobile390' });
export const AzureWorkspaceBlackMobile = homePanelStory({ panel: 'workspace', theme: 'dark', viewport: 'mobile390' });
export const AzureActivityDaylightDesktop = homePanelStory({ panel: 'activity', theme: 'daylight' });
export const AzureActivityBlackDesktop = homePanelStory({ panel: 'activity', theme: 'dark' });
export const AzureActivityDaylightMobile = homePanelStory({ panel: 'activity', theme: 'daylight', viewport: 'mobile390' });
export const AzureActivityBlackMobile = homePanelStory({ panel: 'activity', theme: 'dark', viewport: 'mobile390' });
export const AzureActivityAttention = homePanelStory({ panel: 'activity', theme: 'dark', scenario: 'lifecycle-attention', section: 'Attention' });
export const AzureActivityRunning = homePanelStory({ panel: 'activity', theme: 'dark', section: 'Running' });
export const AzureActivityRecent = homePanelStory({ panel: 'activity', theme: 'daylight', section: 'Recent' });
export const AzureActivityHistory = homePanelStory({ panel: 'activity', theme: 'dark', section: 'History' });
export const AzureActivityEmpty = homePanelStory({ panel: 'activity', theme: 'daylight', section: 'Running' });
export const AzureActivitySaved = homePanelStory({ panel: 'activity', theme: 'daylight', scenario: 'offline-saved', section: 'History' });
export const AzureActivityUnavailable = homePanelStory({ panel: 'activity', theme: 'dark', scenario: 'api-unavailable' });
export const AzureActivityReviewUnavailable = homePanelStory({ panel: 'activity', theme: 'dark', scenario: 'api-unavailable', section: 'History' });
export const AzureWorkspaceEnlargedText = homePanelStory({ panel: 'workspace', theme: 'dark', viewport: 'mobile360', textScale: 2,
  notes: 'Long text / 200% type-scale overflow qualification pending.' });
export const AzureActivityReducedMotion = homePanelStory({ panel: 'activity', theme: 'daylight',
  notes: 'Storybook reducedMotion toolbar should be enabled during qualification.' });
export const AzureWorkspaceSystem = homePanelStory({ panel: 'workspace', theme: 'system' });
export const AzureActivitySystem = homePanelStory({ panel: 'activity', theme: 'system' });
export const AzureWorkspaceDesktopMovedResized = {
  ...createLiteStory('home', 'healthy', { viewport: 'desktop', theme: 'dark', status: 'unvalidated' }),
  play: async ({ canvasElement }) => {
    await openWorkspaceDetails(canvasElement);
    const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Workspace details' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move Workspace details panel' }));
    await userEvent.keyboard('{ArrowLeft}');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Resize Workspace details panel' }));
    await userEvent.keyboard('{ArrowLeft}');
  },
};
export const AzureActivityDesktopMovedResized = {
  ...createLiteStory('home', 'healthy', { viewport: 'desktop', theme: 'dark', status: 'unvalidated' }),
  play: async ({ canvasElement }) => {
    const dialog = await openRecentActivity(canvasElement);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Move Recent activity panel' }));
    await userEvent.keyboard('{ArrowLeft}');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Resize Recent activity panel' }));
    await userEvent.keyboard('{ArrowLeft}');
  },
};

/* P0/P1 workflow visual-source stories. All are AUTHORED / UNVALIDATED. */
export const FlowReadyDaylightDesktop = homePanelStory({ panel:'workspace', theme:'daylight', section:'Service health' });
export const FlowReadyBlackDesktop = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health' });
export const FlowReadyDaylightMobile = homePanelStory({ panel:'workspace', theme:'daylight', section:'Service health', viewport:'mobile390' });
export const FlowReadyBlackMobile = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', viewport:'mobile390' });
export const FlowReviewBlackMobile = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', scenario:'lifecycle-attention', viewport:'mobile390' });
export const FlowSavedBlackMobile = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', scenario:'offline-saved', viewport:'mobile390' });
export const FlowSystemDesktop = homePanelStory({ panel:'workspace', theme:'system', section:'Service health' });
export const FlowNarrowDesktop = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', viewport:'desktop',
  notes:'Use Move/Resize controls to qualify 380px actual panel width; source only.' });
export const FlowTextEnlargedMobile = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', viewport:'mobile360', textScale:2 });
export const FlowReducedMotion = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', viewport:'mobile390',
  notes:'Enable Storybook reduced-motion toolbar during later qualification.' });
export const FlowCheckingContract = homePanelStory({ panel:'workspace', theme:'dark', section:'Service health', viewport:'mobile390',
  notes:'Checking state requires an in-flight refresh fixture; this story is an entry point, not proof of checking.' });

export const FlowActivityLongHistory = homePanelStory({ panel:'activity', theme:'dark', section:'History',
  notes:'History uses bounded, backend-owned samples; enlarged/long fixture qualification pending.' });
export const FlowActivityMobile320 = homePanelStory({ panel:'activity', theme:'dark', viewport:'mobile360',
  notes:'Storybook 360px reference; exact 320px is covered by mocked browser tests.' });
export const FlowActivitySystem = homePanelStory({ panel:'activity', theme:'system', section:'Recent' });
