import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Apps', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectApps(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Apps|App Catalog/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManage(canvasElement) {
  const canvas = await expectApps(canvasElement);
  const manage = (await canvas.findAllByRole('button', { name: /Manage/i }))[0];
  await expect(manage).toBeEnabled();
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  await expect(await body.findByRole('dialog')).toBeInTheDocument();
}

export const CatalogReady = createLiteStory('catalog', 'catalog-ready');

export const MultiAppCapabilityIsolation = {
  ...createLiteStory('catalog', 'catalog-multi-app', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText('Example App')).toBeInTheDocument();
    await expect(await canvas.findByText('PhotoPrism')).toBeInTheDocument();
    const manageButtons = await canvas.findAllByRole('button', { name: 'Manage' });
    await userEvent.click(manageButtons[0]);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: 'Manage Example App' });
    await expect(dialog).toBeInTheDocument();
    await expect(within(dialog).queryByText(/Connect photos|Import photos|Back up app|Check app|Repair/i)).not.toBeInTheDocument();
  },
};
export const AppInstalledRunning = {
  ...createLiteStory('catalog', 'healthy'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/PhotoPrism/i)).toBeInTheDocument();
    await expect(await canvas.findByRole('button', { name: /Open/i })).toBeEnabled();
  },
};
export const AppStopped = {
  ...createLiteStory('catalog', 'app-stopped'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/stopped|not running/i)).toBeInTheDocument();
  },
};
export const InstallAvailable = {
  ...createLiteStory('catalog', 'catalog-install-available'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/install/i)).toBeInTheDocument();
  },
};
export const ActionInProgress = {
  ...createLiteStory('catalog', 'catalog-installing'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/working|installing|progress/i)).toBeInTheDocument();
  },
};
export const ActionFailed = {
  ...createLiteStory('catalog', 'app-action-failed'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/attention|failed|problem/i)).toBeInTheDocument();
  },
};
export const MediaNotReady = {
  ...createLiteStory('catalog', 'app-media-not-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/photos|media/i)).toBeInTheDocument();
  },
};
export const RouteNotReady = {
  ...createLiteStory('catalog', 'app-route-not-ready'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/route|open|not ready/i)).toBeInTheDocument();
  },
};
export const PreparedProjectionStale = createLiteStory('catalog', 'app-projection-stale');
export const SavedOfflineSnapshot = {
  ...createLiteStory('catalog', 'offline-saved'),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    await expect(await canvas.findByText(/saved|offline/i)).toBeInTheDocument();
  },
};

export const InstalledManageOpen = {
  ...createLiteStory('catalog', 'healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const InstallAvailableManageOpen = {
  ...createLiteStory('catalog', 'catalog-install-available', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const ActionFailedManageOpen = {
  ...createLiteStory('catalog', 'app-action-failed', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManage(canvasElement),
};
export const Mobile320 = createLiteStory('catalog', 'healthy', { viewport: 'mobile360', notes: 'Narrow mobile density guard; exact 320px overflow is covered by Playwright.' });


async function expectManageAccessState(canvasElement, expected) {
  await openManage(canvasElement);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
  await expect(await within(dialog).findByText(expected)).toBeInTheDocument();
}

export const GovernedFullAccess = {
  ...createLiteStory('catalog', 'app-governance-full-access', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /You can manage this app/i),
};

export const GovernedReadOnly = {
  ...createLiteStory('catalog', 'app-governance-read-only', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /Read-only access/i),
};

export const GovernedApprovalRequired = {
  ...createLiteStory('catalog', 'app-governance-approval-required', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /needs approval/i),
};

export const GovernedTemporaryAccess = {
  ...createLiteStory('catalog', 'app-governance-temporary-allowed', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /Temporary access until/i),
};

export const GovernedBlockedByRules = {
  ...createLiteStory('catalog', 'app-governance-blocked', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /blocked by Rules/i),
};

export const GovernedMissingCredential = {
  ...createLiteStory('catalog', 'app-governance-missing-credential', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /credential is missing/i),
};

export const GovernedRecoveryBlocker = {
  ...createLiteStory('catalog', 'app-governance-recovery-blocker', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => expectManageAccessState(canvasElement, /storage device is unavailable/i),
};

export const GovernedUnsupportedCapability = {
  ...createLiteStory('catalog', 'catalog-multi-app', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectApps(canvasElement);
    const cards = canvas.getAllByText('Example App');
    await expect(cards.length).toBeGreaterThan(0);
    const manageButtons = await canvas.findAllByRole('button', { name: 'Manage' });
    await userEvent.click(manageButtons[0]);
    const body = within(canvasElement.ownerDocument.body);
    const dialog = await body.findByRole('dialog', { name: 'Manage Example App' });
    await expect(within(dialog).queryByText(/Back up app|Preview restore|Check app|Repair app/i)).not.toBeInTheDocument();
  },
};

/* Source-only premium Apps stories: not executed or baselined in this implementation PR. */
export const PremiumPhotosManage = {
  ...createLiteStory('catalog', 'catalog-ready', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
    const photos = within(manage).getByRole('tab', { name: 'Photos' });
    await userEvent.click(photos);
    await expect(await within(manage).findByRole('region', { name: 'Photo workflow' })).toBeInTheDocument();
    await expect(await within(manage).findByRole('region', { name: 'Photo backup' })).toBeInTheDocument();
  },
};

export const PremiumSharedImportDetails = {
  ...createLiteStory('catalog', 'catalog-ready', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
    await userEvent.click(within(manage).getByRole('tab', { name: 'Photos' }));
    const workflow = await within(manage).findByRole('region', { name: 'Photo workflow' });
    await userEvent.click(within(workflow).getByRole('button', { name: 'View details' }));
    const details = await body.findByRole('dialog', { name: /Import photos/i });
    await expect(within(details).getByText('What happened')).toBeInTheDocument();
    await expect(within(details).getByText('What changed')).toBeInTheDocument();
  },
};

export const PremiumPhotosNotReady = {
  ...createLiteStory('catalog', 'app-media-not-ready', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
    await userEvent.click(within(manage).getByRole('tab', { name: 'Photos' }));
    await expect(await within(manage).findByRole('region', { name: 'Photo workflow' })).toBeInTheDocument();
  },
};

export const PremiumBackupExplanation = {
  ...createLiteStory('catalog', 'catalog-ready', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog', { name: /Manage PhotoPrism/i });
    await userEvent.click(within(manage).getByRole('tab', { name: 'Photos' }));
    const backup = await within(manage).findByRole('region', { name: 'Photo backup' });
    await userEvent.click(within(backup).getByText('How photo backup works'));
    await expect(within(backup).getByText(/protected WebDAV destination/i)).toBeInTheDocument();
  },
};

/* Azure Horizon Apps — definitions only. Qualification and baselines deferred. */
export const AzureDaylightLibrary = createLiteStory('catalog','catalog-multi-app',{theme:'daylight',viewport:'desktop'});
export const AzureBlackLibrary = createLiteStory('catalog','catalog-multi-app',{theme:'dark',viewport:'desktop'});
export const AzureDaylightMobile = createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390'});
export const AzureBlackMobile = createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390'});
export const AzureSystem = createLiteStory('catalog','catalog-ready',{theme:'system',viewport:'desktop'});
export const AzureSavedBlack = createLiteStory('catalog','offline-saved',{theme:'dark',viewport:'mobile390'});
export const AzureStaleDaylight = createLiteStory('catalog','app-projection-stale',{theme:'daylight',viewport:'desktop'});
export const AzureRouteUnavailable = createLiteStory('catalog','app-route-not-ready',{theme:'dark',viewport:'desktop'});
export const AzureMediaNotReady = createLiteStory('catalog','app-media-not-ready',{theme:'daylight',viewport:'mobile390'});
export const AzureInstallInProgress = createLiteStory('catalog','catalog-installing',{theme:'dark',viewport:'desktop'});
export const AzureStopped = createLiteStory('catalog','app-stopped',{theme:'daylight',viewport:'mobile390'});
export const AzureFailedAction = createLiteStory('catalog','app-action-failed',{theme:'dark',viewport:'desktop'});
export const AzureNarrowText200 = createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile360',textScale:2});
export const AzureManageDesktop = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop'}),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog',{name:/Manage PhotoPrism/i});
    await expect(await within(manage).findByRole('button',{name:'Move app management panel'})).toBeVisible();
    await expect(within(manage).getByRole('button',{name:'Resize app management panel'})).toBeVisible();
    await expect(within(manage).getByRole('button',{name:'Reset app panel position and size'})).toBeVisible();
  },
};
export const AzureManageMobile = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390'}),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const manage = await body.findByRole('dialog',{name:/Manage PhotoPrism/i});
    await expect(within(manage).queryByRole('button',{name:'Resize app management panel'})).not.toBeInTheDocument();
  },
};
export const AzureManageBackupAndRecovery = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop'}),
  play: async ({ canvasElement }) => {
    await openManage(canvasElement);
    const manage = await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    const recovery = within(manage).queryByRole('tab',{name:/Recovery/i});
    if (recovery) await userEvent.click(recovery);
  },
};

/* Premium Azure Horizon P0/P1 states: AUTHORED — NOT EXECUTED — UNVALIDATED */
export const AzurePolishDaylightManage = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => openManage(canvasElement),
};
export const AzurePolishBlackManage = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => openManage(canvasElement),
};
export const AzurePolishMobileBlack = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await expect(within(dialog).queryByRole('button',{name:'Resize app management panel'})).not.toBeInTheDocument();
  },
};
export const AzurePolishPhotoBackupReady = {
  ...createLiteStory('catalog','photo-backup-completed',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => openManage(canvasElement),
};
export const AzurePolishPhotoBackupAttention = {
  ...createLiteStory('catalog','photo-backup-remote-unavailable',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => openManage(canvasElement),
};
export const AzurePolishPhotoBackupUnknown = {
  ...createLiteStory('catalog','photo-backup-malformed',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => openManage(canvasElement),
};
export const AzurePolishPhotoGuideExpanded = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await userEvent.click(within(dialog).getByRole('tab',{name:'Photos'}));
    const backup=await within(dialog).findByRole('region',{name:'Photo backup'});
    await userEvent.click(within(backup).getByText('How photo backup works'));
  },
};
export const AzurePolishStorageFactsExpanded = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await userEvent.click(within(dialog).getByText('Storage and device details'));
    await expect(within(dialog).getByText('Where this app runs')).toBeInTheDocument();
  },
};
export const AzurePolishActionNotices = {
  ...createLiteStory('catalog','app-media-not-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    const summary=within(dialog).queryByText('Other action notices');
    if(summary) await userEvent.click(summary);
  },
};
export const AzurePolishGenericApp = createLiteStory('catalog','catalog-multi-app',{theme:'daylight',viewport:'desktop',status:'unvalidated'});
export const AzurePolishZoom200 = createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile360',textScale:2,status:'unvalidated'});
export const AzurePolishSavedOffline = createLiteStory('catalog','offline-saved',{theme:'dark',viewport:'mobile390',status:'unvalidated'});

export const AzurePolishActionDetailsDaylight = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    await openManage(canvasElement);
    const body=within(canvasElement.ownerDocument.body);
    const manage=await body.findByRole('dialog',{name:/Manage PhotoPrism/i});
    await userEvent.click(within(manage).getByRole('tab',{name:'Photos'}));
    const flow=await within(manage).findByRole('region',{name:'Photo workflow'});
    await userEvent.click(within(flow).getByRole('button',{name:'View details'}));
    await expect(await body.findByRole('dialog',{name:/Import photos/i})).toBeInTheDocument();
  },
};
export const AzurePolishActionDetailsBlack = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: AzurePolishActionDetailsDaylight.play,
};


/* Final Azure Horizon Apps source-authored stories. No Storybook runs or
   screenshot promotions were performed in the authoring session. */
async function openFinalManage(canvasElement) {
  await openManage(canvasElement);
  return within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
}
export const AzureFinalDaylightCatalog = createLiteStory('catalog','catalog-multi-app',{theme:'daylight',viewport:'desktop',status:'unvalidated'});
export const AzureFinalBlackCatalog = createLiteStory('catalog','catalog-multi-app',{theme:'dark',viewport:'desktop',status:'unvalidated'});
export const AzureFinalSystemCatalog = createLiteStory('catalog','catalog-ready',{theme:'system',viewport:'mobile390',status:'unvalidated'});
export const AzureFinalGenericSecondApp = createLiteStory('catalog','catalog-multi-app',{theme:'dark',viewport:'desktop',status:'unvalidated'});
export const AzureFinalOfflineState = createLiteStory('catalog','offline-saved',{theme:'dark',viewport:'mobile390',status:'unvalidated'});
export const AzureFinalLongText = createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile360',textScale:2,status:'unvalidated'});
export const AzureFinalDesktopManageControls = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    const view=within(dialog);
    await expect(view.getByRole('button',{name:'Move app management panel'})).toBeVisible();
    await expect(view.getByRole('button',{name:'Reset app panel position and size'})).toBeVisible();
    await expect(view.getByRole('button',{name:'Resize app management panel'})).toBeVisible();
  },
};
export const AzureFinalMobileMedium = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','medium');
  },
};
export const AzureFinalMobileCompact = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    await userEvent.click(within(dialog).getByRole('button',{name:'Compact',exact:true}));
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','compact');
  },
};
export const AzureFinalMobileExpanded = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    await userEvent.click(within(dialog).getByRole('button',{name:'Expand',exact:true}));
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','expanded');
  },
};
export const AzureFinalStorageDisclosureExpanded = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    const disclosure=dialog.querySelector('.lite-catalog-premium-storage-details');
    if(disclosure) await userEvent.click(within(disclosure).getByText('Storage and device details'));
  },
};
export const AzureFinalNoticesDisclosureExpanded = {
  ...createLiteStory('catalog','app-media-not-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    const disclosure=dialog.querySelector('.lite-catalog-premium-action-notices');
    if(disclosure) await userEvent.click(within(disclosure).getByText('Other action notices'));
  },
};
export const AzureFinalPhotoGuideExpanded = {
  ...createLiteStory('catalog','photo-backup-completed',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    const guide=dialog.querySelector('.lite-catalog-premium-backup-actions details');
    if(guide) await userEvent.click(within(guide).getByText('How photo backup works'));
  },
};
export const AzureFinalPhotoBackupReady = {
  ...createLiteStory('catalog','photo-backup-completed',{theme:'dark',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => { await openFinalManage(canvasElement); },
};
export const AzureFinalPhotoBackupNotReady = {
  ...createLiteStory('catalog','photo-backup-remote-unavailable',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async ({canvasElement}) => { await openFinalManage(canvasElement); },
};
export const AzureFinalNestedActionDetails = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async ({canvasElement}) => {
    const dialog=await openFinalManage(canvasElement);
    const flow=within(dialog).getByRole('region',{name:'Photo workflow'});
    await userEvent.click(within(flow).getByRole('button',{name:'View details'}));
    const body=within(canvasElement.ownerDocument.body);
    await expect(await body.findByRole('dialog',{name:/Import photos|Photo/})).toBeInTheDocument();
  },
};

/* Balanced-density contract: paired scenarios, same DOM and geometry,
   theme resolved by the existing Azure Horizon provider. NOT RENDERED. */
export const BalancedDensityLightDesktop = createLiteStory('catalog','catalog-multi-app',{
  theme:'daylight',viewport:'desktop',status:'unvalidated',
  notes:'Balanced Apps geometry: compare directly with BalancedDensityDarkDesktop.',
});
export const BalancedDensityDarkDesktop = createLiteStory('catalog','catalog-multi-app',{
  theme:'dark',viewport:'desktop',status:'unvalidated',
  notes:'Same app cards, toolbar and controls as the Light variant; only semantic colors differ.',
});
export const BalancedDensityLightMobile = createLiteStory('catalog','catalog-ready',{
  theme:'daylight',viewport:'mobile390',status:'unvalidated',
});
export const BalancedDensityDarkMobile = createLiteStory('catalog','catalog-ready',{
  theme:'dark',viewport:'mobile390',status:'unvalidated',
});
export const BalancedDensitySystemMobile = createLiteStory('catalog','catalog-ready',{
  theme:'system',viewport:'mobile390',status:'unvalidated',
});
export const BalancedDensityManageLight = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: AzureFinalDesktopManageControls.play,
};
export const BalancedDensityManageDark = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: AzureFinalDesktopManageControls.play,
};
export const BalancedDensityDetailsLight = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: AzureFinalNestedActionDetails.play,
};
export const BalancedDensityDetailsDark = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: AzureFinalNestedActionDetails.play,
};
export const BalancedDensityLongTextMobile = createLiteStory('catalog','catalog-multi-app',{
  theme:'dark',viewport:'mobile360',textScale:2,status:'unvalidated',
  notes:'Review reflow and wrapped labels at 200% text scale; automated geometry uses exact 320px.',
});
export const BalancedDensityWrappedStatus = createLiteStory('catalog','app-media-not-ready',{
  theme:'daylight',viewport:'mobile390',status:'unvalidated',
  notes:'Review multi-line readiness, badges, and disabled-action guidance.',
});


/* Azure Horizon Native App Library P0–P2: source-authored Storybook candidates.
   Not executed or visually approved in this implementation session. */
export const NativeLibrarySingleDaylight = createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390',status:'unvalidated'});
export const NativeLibrarySingleDark = createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'});
export const NativeLibraryMultiDesktop = createLiteStory('catalog','catalog-multi-app',{theme:'daylight',viewport:'desktop',status:'unvalidated'});
export const NativeLibraryMultiDark = createLiteStory('catalog','catalog-multi-app',{theme:'dark',viewport:'desktop',status:'unvalidated'});
export const NativeLibrarySystem = createLiteStory('catalog','catalog-ready',{theme:'system',viewport:'desktop',status:'unvalidated'});
export const NativeLibraryEmpty = createLiteStory('catalog','catalog-empty',{theme:'daylight',viewport:'mobile390',status:'unvalidated'});
export const NativeLibraryOffline = createLiteStory('catalog','offline-saved',{theme:'dark',viewport:'mobile390',status:'unvalidated'});
export const NativeLibraryNeedsAttention = createLiteStory('catalog','app-route-not-ready',{theme:'dark',viewport:'mobile390',status:'unvalidated'});
export const NativeLibraryLongText = createLiteStory('catalog','catalog-multi-app',{theme:'dark',viewport:'mobile360',textScale:2,status:'unvalidated'});
export const NativeManageOverview = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'desktop',status:'unvalidated'}),
  play: async({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await expect(within(dialog).getByRole('region',{name:'App overview'})).toBeVisible();
  }
};
export const NativeManageActivity = {
  ...createLiteStory('catalog','catalog-ready',{theme:'dark',viewport:'desktop',status:'unvalidated'}),
  play: async({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await userEvent.click(within(dialog).getByRole('tab',{name:'Activity'}));
    await expect(within(dialog).getByRole('region',{name:'Recent app activity'})).toBeVisible();
  }
};
export const NativeManagePhotosWorkflow = {
  ...createLiteStory('catalog','catalog-ready',{theme:'daylight',viewport:'mobile390',status:'unvalidated'}),
  play: async({canvasElement}) => {
    await openManage(canvasElement);
    const dialog=await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Manage PhotoPrism/i});
    await userEvent.click(within(dialog).getByRole('tab',{name:'Photos'}));
    await expect(within(dialog).getByRole('region',{name:'Photo workflow'})).toBeVisible();
  }
};
