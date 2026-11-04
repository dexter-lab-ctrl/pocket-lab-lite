import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

export default { title: 'Pocket Lab Lite/Security', component: LiteStoryFrame, tags: ['autodocs'] };

async function expectSecurity(canvasElement) {
  const canvas = within(canvasElement);
  await expect(await canvas.findByRole('heading', { name: /Security|Safety Center/i, level: 1 })).toBeInTheDocument();
  return canvas;
}

async function openManageSection(canvasElement, label = 'Overview') {
  const canvas = await expectSecurity(canvasElement);
  const manage = await canvas.findByRole('button', { name: /Manage Security details/i });
  await userEvent.click(manage);
  const body = within(canvasElement.ownerDocument.body);
  const dialog = await body.findByRole('dialog', { name: /Manage Safety/i });
  await expect(dialog).toBeInTheDocument();
  if (label !== 'Overview') {
    const tab = within(dialog).getByRole('button', { name: new RegExp(`Open ${label} in Manage Safety`, 'i') });
    await userEvent.click(tab);
    await expect(tab).toHaveAttribute('aria-current', 'page');
  }
  await expect(within(dialog).getByRole('heading', { name: label === 'Checks' ? 'Run Checks' : label === 'Issues' ? 'Issues' : label, level: 2 })).toBeInTheDocument();
}

export const QuickCheckHealthy = {
  ...createLiteStory('security', 'security-quick-healthy'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/No urgent safety issues|Protected|Safety score/i);
  },
};
export const QuickCheckReviewRecommended = {
  ...createLiteStory('security', 'security-action-needed'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/attention|review|issue/i);
  },
};
export const FullCheckRunning = {
  ...createLiteStory('security', 'security-full-running'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/running|checking|progress/i);
  },
};
export const AppCheckHealthy = {
  ...createLiteStory('security', 'security-app-check-healthy'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/PhotoPrism|App Check/i);
  },
};
export const UrgentFinding = {
  ...createLiteStory('security', 'security-urgent'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/urgent|critical|attention/i);
  },
};
export const NoScanHistory = createLiteStory('security', 'security-first-run');
export const ProfileDataStale = createLiteStory('security', 'security-profile-stale');
export const ProgressStages = createLiteStory('security', 'security-progress');
export const ScannerUnavailable = {
  ...createLiteStory('security', 'security-scanner-unavailable'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/scanner|unavailable|attention/i);
  },
};
export const UnsupportedAppProfileRoute = createLiteStory('security', 'security-unsupported-app-route');
export const SavedOfflineSnapshot = {
  ...createLiteStory('security', 'offline-saved'),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|offline/i);
  },
};

export const HealthyManageOverview = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Overview'),
};
export const ManageChanges = {
  ...createLiteStory('security', 'security-action-needed', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Changes'),
};
export const ManageIssues = {
  ...createLiteStory('security', 'security-urgent', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Issues'),
};
export const ManageCheckPath = {
  ...createLiteStory('security', 'security-full-running', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Check path'),
};
export const ManageEvidence = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Evidence'),
};
export const ManageHistory = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'History'),
};
export const ManageTechnicalDetails = {
  ...createLiteStory('security', 'security-quick-healthy', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Technical details'),
};
export const UrgentFindingManageOpen = {
  ...createLiteStory('security', 'security-urgent', { viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Issues'),
};
export const ScannerUnavailableManageOpen = {
  ...createLiteStory('security', 'security-scanner-unavailable', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Overview'),
};
export const OfflineSavedManageOpen = {
  ...createLiteStory('security', 'offline-saved', { viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await expectSecurity(canvasElement);
    await expect(canvasElement).toHaveTextContent(/saved|offline/i);
    const quickScan = within(canvasElement).queryByRole('button', { name: /Run Quick Safety Check|Reconnect to run Quick Safety Check/i });
    if (quickScan) await expect(quickScan).toBeDisabled();
  },
};

/* Azure Horizon P0–P3 deterministic story cases.
   DEFINED — CAPTURE AND APPROVAL DEFERRED. */
export const AzureBlackDesktop = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'desktop' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(canvas.getByRole('region', { name: 'Safety overview' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /Open Coverage & Checks/i })).toBeInTheDocument();
  },
};
export const AzureDaylightDesktop = createLiteStory('security', 'security-action-needed', { theme: 'daylight', viewport: 'desktop' });
export const AzureSystemMobile = createLiteStory('security', 'security-quick-healthy', { theme: 'system', viewport: 'mobile390' });
export const AzureBlackMobile320 = createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile320' });
export const AzureDaylightLargeText = createLiteStory('security', 'security-action-needed', { theme: 'daylight', viewport: 'mobile360', textScale: 2 });
export const AzureBlackPartialCoverage = createLiteStory('security', 'security-scanner-unavailable', { theme: 'dark', viewport: 'desktop' });
export const AzureSavedState = createLiteStory('security', 'security-profile-stale', { theme: 'dark', viewport: 'mobile390' });
export const AzureActiveFullCheck = createLiteStory('security', 'security-full-running', { theme: 'dark', viewport: 'desktop' });
export const AzureFirstRunNoScore = createLiteStory('security', 'security-first-run', { theme: 'daylight', viewport: 'mobile390' });
export const AzureManageChecks = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Checks'),
};
export const AzureManageCoverage = {
  ...createLiteStory('security', 'security-scanner-unavailable', { theme: 'dark', viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const AzureManageEvidenceMobile = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'daylight', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Evidence'),
};
export const AzureManageTechnicalMobile = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Technical details'),
};

/* Native P0–P7: authored state coverage; screenshot approval is deferred. */
export const NativeDarkMobileIndex = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    const canvas = await expectSecurity(canvasElement);
    await expect(canvas.getByRole('navigation', { name: 'Safety destinations' })).toBeInTheDocument();
    await userEvent.click(canvas.getByRole('button', { name: 'Manage Security details' }));
    const dialog = await within(canvasElement.ownerDocument.body).findByRole('dialog', { name: 'Manage Safety' });
    await expect(within(dialog).getByRole('navigation', { name: 'Manage Safety sections' })).toBeInTheDocument();
  },
};
export const NativeDarkMobileCoverage = {
  ...createLiteStory('security', 'security-scanner-unavailable', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const NativeSystemFirstRun = createLiteStory('security', 'security-first-run', { theme: 'system', viewport: 'mobile320' });
export const NativeDaylightOffline = createLiteStory('security', 'offline-saved', { theme: 'daylight', viewport: 'mobile390' });
export const NativeDarkFullRunning = createLiteStory('security', 'security-full-running', { theme: 'dark', viewport: 'desktop' });
export const NativeDaylightAttention = createLiteStory('security', 'security-action-needed', { theme: 'daylight', viewport: 'desktop' });
export const NativeAppCheck = createLiteStory('security', 'security-app-check-healthy', { theme: 'dark', viewport: 'desktop' });


/* R6 — authored visual-hardening stories. No snapshots or play runs were generated. */
export const RefinementDaylightCoverageMobile = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'daylight', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const RefinementDarkCoverage320 = {
  ...createLiteStory('security', 'security-scanner-unavailable', { theme: 'dark', viewport: 'mobile320' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const RefinementSystemLightCoverage = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'system', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const RefinementSystemDarkIndex = createLiteStory('security', 'security-quick-healthy', { theme: 'system', viewport: 'mobile320' });
export const RefinementPartialCoverage = {
  ...createLiteStory('security', 'security-scanner-unavailable', { theme: 'dark', viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Coverage'),
};
export const RefinementFindings = {
  ...createLiteStory('security', 'security-urgent', { theme: 'daylight', viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Issues'),
};
export const RefinementHistory = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'History'),
};
export const RefinementTechnical = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'daylight', viewport: 'desktop' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Technical details'),
};
export const RefinementRunChecks = {
  ...createLiteStory('security', 'security-full-running', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Checks'),
};
export const RefinementEvidence = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'daylight', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => openManageSection(canvasElement, 'Evidence'),
};
export const RefinementSavedOffline = createLiteStory('security', 'offline-saved', { theme: 'dark', viewport: 'mobile320' });
export const RefinementFirstRun = createLiteStory('security', 'security-first-run', { theme: 'daylight', viewport: 'mobile390' });
export const RefinementAttention = createLiteStory('security', 'security-action-needed', { theme: 'dark', viewport: 'desktop' });
export const RefinementExpandedDetail = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManageSection(canvasElement, 'Coverage');
    const body = within(canvasElement.ownerDocument.body);
    const dialog = body.getByRole('dialog', { name: 'Manage Safety' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Open Security coverage details' }));
    await expect(body.getByRole('dialog', { name: /Quick safety coverage/i })).toBeInTheDocument();
  },
};
export const RefinementCompactSheet = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManageSection(canvasElement, 'Coverage');
    const body = within(canvasElement.ownerDocument.body);
    const dialog = body.getByRole('dialog', { name: 'Manage Safety' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Compact' }));
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
  },
};
export const RefinementMediumSheet = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'daylight', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManageSection(canvasElement, 'Coverage');
    const dialog = within(canvasElement.ownerDocument.body).getByRole('dialog', { name: 'Manage Safety' });
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
  },
};
export const RefinementExpandedSheet = {
  ...createLiteStory('security', 'security-quick-healthy', { theme: 'dark', viewport: 'mobile390' }),
  play: async ({ canvasElement }) => {
    await openManageSection(canvasElement, 'Coverage');
    const dialog = within(canvasElement.ownerDocument.body).getByRole('dialog', { name: 'Manage Safety' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Expand' }));
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
  },
};
