import React from 'react';
import {
  LiteActionOutcome,
  LiteConsequenceSummary,
  LiteEmptyState,
  LiteFreshness,
  LiteHistoryTimeline,
  LiteSectionHeader,
  LiteTechnicalFacts,
} from './LiteUx.jsx';
import { LiteOperationalStory as LiteOperationalStoryPrimitive, LiteRefreshButton } from './LiteUi.jsx';

export default {
  title: 'Pocket Lab Lite/UX Maturity Contract',
  tags: ['autodocs'],
  parameters: {
    pocketlab: {
      product: 'Pocket Lab Lite',
      screen: 'ux-maturity-contract',
      scenario: 'shared-story-language',
      implementation_status: 'source-complete',
      notes: 'Reference stories for the summary → action → Manage → focused details product language. Presentation only; no backend execution.',
    },
  },
};

const shell = (children) => (
  <main className="theme-pocket-lite-daylight" style={{ minHeight: '100vh', padding: 24, background: 'var(--lite-bg, #f8fafc)' }}>
    <div style={{ maxWidth: 760, margin: '0 auto', display: 'grid', gap: 16 }}>{children}</div>
  </main>
);

export const FreshAndSavedInformation = {
  render: () => shell(
    <>
      <LiteSectionHeader eyebrow="Freshness" title="Information state" description="Users see whether information is current without seeing cache or refresh implementation." />
      <LiteFreshness lastUpdatedLabel="just now" />
      <LiteFreshness saved backendReachable={false} lastUpdatedLabel="12 minutes ago" />
    </>,
  ),
};

export const MeaningfulTechnicalDetails = {
  render: () => shell(
    <LiteTechnicalFacts
      facts={[
        { label: 'Checked', value: 'Today, 3:08 AM' },
        { label: 'Device', value: 'Server Phone' },
        { label: 'Current state', value: 'Connected' },
        { label: 'Duration', value: '18 seconds' },
        { label: 'Change made', value: 'None' },
        { label: 'Protected data', value: 'Hidden' },
        { label: 'Troubleshooting reference', value: 'PL-7F31' },
      ]}
    />,
  ),
};

export const ActivityTimeline = {
  render: () => shell(
    <LiteHistoryTimeline
      items={[
        { id: '1', title: 'Safety check completed', summary: 'No urgent issues were found.', time: '3:08 AM', state: 'completed' },
        { id: '2', title: 'PhotoPrism repaired', summary: 'App access was restored.', time: 'Yesterday', state: 'completed' },
        { id: '3', title: 'Backup verified', summary: 'Recovery is ready.', time: 'Sunday', state: 'completed' },
      ]}
    />,
  ),
};

export const ConsequenceBeforeChange = {
  render: () => shell(
    <LiteConsequenceSummary
      value={{
        title: 'Remove Living Room Phone?',
        summary: 'Review what changes before continuing.',
        will: ['Remove this device relationship from Pocket Lab.', 'Stop new Pocket Lab actions from being sent to it.'],
        willNot: ['Erase data from the phone.', 'Uninstall Pocket Lab from the phone.'],
        reversible: 'The phone can join again later through Add Device.',
        availability: 'Apps or backups that depend on the device may become unavailable.',
      }}
    />,
  ),
};

export const ActionResultStory = {
  render: () => shell(
    <LiteActionOutcome
      result={{
        title: 'PhotoPrism checked',
        summary: 'PhotoPrism is healthy.',
        what_changed: 'Nothing changed.',
        what_did_not_happen: 'No photos were scanned or modified.',
        protected_summary: 'Photos and private values stayed protected.',
        next_action: 'No action is needed right now.',
      }}
    />,
  ),
};

export const EmptyStateWithNextStep = {
  render: () => shell(
    <LiteEmptyState
      title="No safety checks yet"
      description="Run your first Safety Check to create a baseline."
      action={{ label: 'Run Safety Check', onClick: () => {} }}
    />,
  ),
};

function RefreshInControlStory() {
  const [refreshing, setRefreshing] = React.useState(false);

  const refresh = () => {
    setRefreshing(true);
    return new Promise((resolve) => {
      window.setTimeout(() => {
        setRefreshing(false);
        resolve();
      }, 900);
    });
  };

  return shell(
    <>
      <LiteSectionHeader eyebrow="Freshness" title="Refresh acknowledgement" description="The current view stays visible while the control provides immediate, accessible progress feedback." />
      <LiteRefreshButton scope="storybook-refresh" refresh={refresh} refreshing={refreshing} />
    </>,
  );
}

export const RefreshInControl = {
  render: () => <RefreshInControlStory />,
};

function OperationalStoryRefreshStory() {
  const [refreshing, setRefreshing] = React.useState(false);

  const refresh = () => {
    setRefreshing(true);
    return new Promise((resolve) => {
      window.setTimeout(() => {
        setRefreshing(false);
        resolve();
      }, 900);
    });
  };

  return shell(
    <LiteOperationalStoryPrimitive
      story={{
        state: 'ready',
        tone: 'ready',
        headline: 'Safety information is current',
        summary: 'Refresh keeps the current story visible while the latest result is checked.',
      }}
      primaryAction={{ label: 'Refresh Safety Center', onClick: refresh, refreshing }}
    />,
  );
}

export const OperationalStoryRefresh = {
  render: () => <OperationalStoryRefreshStory />,
};

export const MobileContract = {
  ...ConsequenceBeforeChange,
  parameters: { viewport: { defaultViewport: 'mobile390' } },
};
