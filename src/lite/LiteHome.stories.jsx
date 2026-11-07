import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';
import { HomeWorkspaceFlow, HomeHealthHero } from './LiteHome.jsx';
import { LiteThemeProvider } from './theme/LiteThemeProvider.jsx';

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
    await openWorkspaceDetails(canvasElement);
    const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Workspace details' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Updates' }));
    await expect(within(dialog).getByRole('heading', { name: 'Updates' })).toBeInTheDocument();
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
  await userEvent.click(await canvas.findByRole('button', { name: /View all activity/i }));
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
export const FlowCheckingContract = {
  ...createLiteStory('home', 'healthy', { theme:'dark', viewport:'mobile390', status:'partial',
    notes:'Presentational Checking fixture only; does not start an API refresh or claim backend work.' }),
  render: () => <LiteThemeProvider><div className="lite-home-panel-layer" style={{ padding:'1rem' }}>
    <p>Simulated Checking presentation; no backend request is started.</p>
    <div className="lite-home-details-panel" style={{ container:'home-panel / inline-size', maxWidth:440 }}>
      <HomeWorkspaceFlow overallTone="ready" attentionCount={0} checking />
    </div>
  </div></LiteThemeProvider>,
  play: async ({ canvasElement }) => {
    await expect(canvasElement.ownerDocument.documentElement).toHaveAttribute('data-lite-theme', 'dark');
    await expect(within(canvasElement).getByText('Checking', { exact: true })).toBeVisible();
    await expect(within(canvasElement).getAllByRole('listitem')).toHaveLength(4);
  },
};

export const FlowActivityLongHistory = homePanelStory({ panel:'activity', theme:'dark', section:'History',
  notes:'History uses bounded, backend-owned samples; enlarged/long fixture qualification pending.' });
export const FlowActivityMobile320 = homePanelStory({ panel:'activity', theme:'dark', viewport:'mobile360',
  notes:'Storybook 360px reference; exact 320px is covered by mocked browser tests.' });
export const FlowActivitySystem = homePanelStory({ panel:'activity', theme:'system', section:'Recent' });


/* Azure Horizon Command Home P0–P3 source fixtures. AUTHORED — NOT RUN; no visual approval. */
const commandOpts = { status: 'unvalidated', notes: 'Implementation fixture only. Browser, a11y and visual review deferred.' };
export const CommandDaylightHealthyDesktop = createLiteStory('home','healthy',{ theme:'daylight',viewport:'desktop',...commandOpts });
export const CommandDarkHealthyDesktop = createLiteStory('home','healthy',{ theme:'dark',viewport:'desktop',...commandOpts });
export const CommandDaylightHealthyMobile = createLiteStory('home','healthy',{ theme:'daylight',viewport:'mobile390',...commandOpts });
export const CommandDarkHealthyMobile = createLiteStory('home','healthy',{ theme:'dark',viewport:'mobile390',...commandOpts });
export const CommandAttentionDesktop = createLiteStory('home','lifecycle-attention',{theme:'daylight',viewport:'desktop',...commandOpts});
export const CommandAttentionMobile = createLiteStory('home','lifecycle-attention',{theme:'dark',viewport:'mobile390',...commandOpts});
export const CommandSavedOffline = createLiteStory('home','offline-saved',{theme:'daylight',viewport:'mobile390',...commandOpts});
export const CommandApiUnavailable = createLiteStory('home','api-unavailable',{theme:'dark',viewport:'mobile360',...commandOpts});
export const CommandLongText = createLiteStory('home','lifecycle-attention',{theme:'daylight',viewport:'mobile360',textScale:2,...commandOpts});
export const CommandEnlargedText = createLiteStory('home','healthy',{theme:'dark',viewport:'mobile390',textScale:2,...commandOpts});
export const CommandNarrow = createLiteStory('home','healthy',{theme:'daylight',viewport:'mobile360',...commandOpts});
export const CommandReducedMotion = createLiteStory('home','healthy',{theme:'dark',viewport:'mobile390',...commandOpts,
  notes:'Enable the Storybook reduced-motion toolbar during deferred visual review.'});
export const CommandSystem = createLiteStory('home','healthy',{theme:'system',viewport:'desktop',...commandOpts});

function commandIndexStory(panel, theme, viewport) {
  return { ...createLiteStory('home','healthy',{theme,viewport,...commandOpts}),
    play: async ({canvasElement}) => {
      const canvas = await expectHome(canvasElement);
      const name = panel === 'workspace' ? 'Workspace details' : 'Recent activity';
      await userEvent.click(await canvas.findByRole('button',{name: panel === 'workspace' ? name : /View all activity/i}));
      const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog',{name});
      await expect(dialog).toBeInTheDocument();
      await expect(within(dialog).getByRole('navigation', {name: (panel === 'workspace' ? 'Workspace details' : 'Activity') + ' sections'})).toBeInTheDocument();
    },
  };
}
export const CommandWorkspaceMobileIndex = commandIndexStory('workspace','daylight','mobile390');
export const CommandWorkspaceMobileNested = homePanelStory({panel:'workspace',theme:'dark',viewport:'mobile390',section:'Service health'});
export const CommandWorkspaceDesktopColumn = commandIndexStory('workspace','dark','desktop');
export const CommandActivityMobileIndex = commandIndexStory('activity','daylight','mobile390');
export const CommandActivityMobileNested = homePanelStory({panel:'activity',theme:'dark',viewport:'mobile390',section:'History'});
export const CommandActivityDesktopColumn = commandIndexStory('activity','dark','desktop');
export const CommandWorkspaceNarrowPanel = homePanelStory({panel:'workspace',theme:'dark',viewport:'desktop',
  notes:'Manually resize panel to 380px; actual container-query fallback qualification deferred.'});
export const CommandActivityResizedPanel = homePanelStory({panel:'activity',theme:'daylight',viewport:'desktop',
  notes:'Manually resize to 380px and verify grouped navigation. Deferred.'});

async function openActivityRoot(canvasElement) {
  const canvas = await expectHome(canvasElement);
  await userEvent.click(await canvas.findByRole('button', { name: /View all activity/i }));
  return within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Recent activity' });
}

async function openSnapState(canvasElement, panel, snap) {
  const dialog = panel === 'workspace'
    ? await (async () => { await openWorkspaceDetails(canvasElement); return within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Workspace details' }); })()
    : await openActivityRoot(canvasElement);
  if (snap === 'compact') await userEvent.click(within(dialog).getByRole('button', { name: 'Compact', exact: true }));
  if (snap === 'expanded') {
    await userEvent.click(within(dialog).getByRole('button', { name: 'Expand', exact: true }));
  }
  await expect(dialog).toHaveAttribute('data-lite-sheet-snap', snap);
}

function commandSnapStory(panel, snap) {
  return {
    ...createLiteStory('home', 'healthy', {
      theme: 'dark', viewport: 'mobile390', status: 'validated',
      notes: `PR #634 shared mobile snap reference: ${panel} ${snap}.`,
    }),
    play: async ({ canvasElement }) => openSnapState(canvasElement, panel, snap),
  };
}

export const CommandWorkspaceMobileCompact = commandSnapStory('workspace', 'compact');
export const CommandWorkspaceMobileMedium = commandSnapStory('workspace', 'medium');
export const CommandWorkspaceMobileExpanded = commandSnapStory('workspace', 'expanded');
export const CommandActivityMobileCompact = commandSnapStory('activity', 'compact');
export const CommandActivityMobileMedium = commandSnapStory('activity', 'medium');
export const CommandActivityMobileExpanded = commandSnapStory('activity', 'expanded');

function isolatedHeroStory(props, theme='daylight') {
  return { ...createLiteStory('home','healthy',{theme,viewport:'mobile390',...commandOpts}),
    render: () => <LiteThemeProvider><div data-lite-theme-preview="command" className="lite-home-refined"
      style={{padding:'1rem'}}><HomeHealthHero overview={{overallTone:'ready',services:[{key:'security',tone:'ready'}]}}
      lastUpdatedLabel="" onDetails={() => {}} {...props}/></div></LiteThemeProvider>,
  };
}
export const CommandRunningOperation = isolatedHeroStory({running:true},'dark');
export const CommandChecking = isolatedHeroStory({refreshing:true},'daylight');
export const CommandInitialLoading = isolatedHeroStory({loading:true,overview:{overallTone:'unknown',services:[]}},'dark');
export const CommandPartialProjection = isolatedHeroStory({partial:true},'daylight');
export const CommandUnknown = isolatedHeroStory({error:true},'dark');


/*
 * Premium P0–P6 source fixtures — AUTHORED, NOT EXECUTED.
 * Existing PR #638 layout and mock authority remain unchanged. No visual
 * baselines or Storybook qualifications are approved in this session.
 */
const premiumOpts = { status: 'unvalidated',
  notes: 'P0–P6 Home source-only visual reference; later visual/a11y qualification required.' };
export const PremiumReadyDaylight390 = createLiteStory('home', 'healthy',
  { theme: 'daylight', viewport: 'mobile390', ...premiumOpts });
export const PremiumReadyDarkDesktop = createLiteStory('home', 'healthy',
  { theme: 'dark', viewport: 'desktop', ...premiumOpts });
export const PremiumAttentionDark390 = createLiteStory('home', 'lifecycle-attention',
  { theme: 'dark', viewport: 'mobile390', ...premiumOpts });
export const PremiumOfflineSavedSystem = createLiteStory('home', 'offline-saved',
  { theme: 'system', viewport: 'mobile390', ...premiumOpts });
export const PremiumUnavailableDaylight = createLiteStory('home', 'api-unavailable',
  { theme: 'daylight', viewport: 'mobile360', ...premiumOpts });
export const PremiumLongTextDark = createLiteStory('home', 'lifecycle-attention',
  { theme: 'dark', viewport: 'mobile360', textScale: 2, ...premiumOpts });
export const PremiumCriticalHero = isolatedHeroStory({
  overview: { overallTone: 'danger', services: [{ key: 'security', tone: 'danger' }] },
}, 'dark');
export const PremiumPartialHero = isolatedHeroStory({ partial: true }, 'daylight');
export const PremiumLoadingHero = isolatedHeroStory({
  loading: true, overview: { overallTone: 'unknown', services: [] },
}, 'daylight');
export const PremiumRunningHero = isolatedHeroStory({ running: true }, 'dark');
export const PremiumUnknownHero = isolatedHeroStory({ error: true }, 'dark');
export const PremiumWorkspaceDetailDark = homePanelStory({
  panel: 'workspace', theme: 'dark', viewport: 'mobile390', section: 'Service health',
  notes: 'Native grouped detail, haptic/delegation and semantic node statuses; unqualified.',
});
export const PremiumActivityHistoryDaylight = homePanelStory({
  panel: 'activity', theme: 'daylight', viewport: 'mobile390', section: 'History',
  notes: 'Backend-derived activity and review cursor, visible only after navigation; unqualified.',
});
