import React from 'react';
import LiteApp from '../LiteApp.jsx';

export default function LiteStoryFrame() {
  return <LiteApp />;
}

export function storyParameters(screen, scenario, { viewport = 'mobile390', status = 'verified', notes = '' } = {}) {
  return {
    liteScreen: screen,
    liteScenario: scenario,
    viewport: { defaultViewport: viewport },
    pocketlab: {
      product: 'Pocket Lab Lite',
      screen,
      scenario,
      implementation_status: status,
      notes,
      architecture: 'UI → FastAPI /api/lite/* → NATS/worker/agent/supervisor → evidence → FastAPI → UI',
    },
    docs: {
      description: {
        story: `${scenario}. ${status === 'partial' ? 'This is a partial or fixture-only contract and does not claim backend execution.' : 'Uses the production Lite API helper and TanStack Query path with deterministic MSW responses.'} ${notes}`,
      },
    },
  };
}

export function createLiteStory(screen, scenario, options = {}) {
  return {
    render: () => <LiteStoryFrame />,
    parameters: storyParameters(screen, scenario, options),
  };
}
