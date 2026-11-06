// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { HomeWorkspaceFlow, homeWorkflowPresentation, homeWorkflowNodeStates } from '../LiteHome.jsx';

afterEach(cleanup);
const cases = [
  { name: 'ready', props: { overallTone: 'ready', attentionCount: 0 }, badge: 'Live', text: 'Reported workspace checks are ready' },
  { name: 'attention', props: { overallTone: 'review', attentionCount: 2 }, badge: 'Review', text: 'Some workspace services need attention' },
  { name: 'saved', props: { overallTone: 'ready', savedStateOnly: true }, badge: 'Saved', text: 'Showing saved workspace state' },
  { name: 'checking', props: { overallTone: 'ready', checking: true }, badge: 'Checking', text: 'Checking your workspace flow' },
];
describe('Home Workspace Status Flow P0/P1 presentation', () => {
  for (const item of cases) {
    it(`renders ${item.name} without inventing node-level operational status`, () => {
      const view = homeWorkflowPresentation(item.props);
      expect(view.badge).toBe(item.badge);
      const { container } = render(<HomeWorkspaceFlow {...item.props} />);
      const flow = container.querySelector('.lite-home-workflow');
      expect(flow).toHaveAttribute('data-home-workflow-state', item.name);
      expect(within(flow).getByText(item.text)).toBeInTheDocument();
      expect(within(flow).getByText(item.badge)).toBeInTheDocument();
      const steps = within(flow).getAllByRole('listitem');
      expect(steps).toHaveLength(4);
      expect(steps.map((el) => el.getAttribute('aria-label'))).toEqual([
        'Device workspace flow step: Status not confirmed', 'Services workspace flow step: Status not confirmed',
        'Apps workspace flow step: Status not confirmed', 'Safety workspace flow step: Status not confirmed',
      ]);
      expect(flow.querySelectorAll('.lite-home-workflow-line[aria-hidden="true"]')).toHaveLength(3);
      expect(flow.querySelectorAll('.lite-home-workflow-node > svg[aria-hidden="true"]')).toHaveLength(4);
    });
  }
  it('does not turn unavailable/saved information into a live indicator', () => {
    const props = homeWorkflowPresentation({ overallTone: 'ready', savedStateOnly: true, checking: false });
    expect(props.state).toBe('saved');
    expect(props.activeNodes).toHaveLength(0);
    expect(props.doneNodes).toHaveLength(0);
  });
});

describe('P0–P6 node authority and saved-state contract', () => {
  const projected = [
    { key: 'device_fleet', tone: 'ready' },
    { key: 'app_catalog', tone: 'review' },
    { key: 'security', tone: 'danger' },
  ];
  it('uses only projected domain-specific statuses; connector and services remain unknown', () => {
    expect(homeWorkflowNodeStates(projected).map((item) => item.state)).toEqual([
      'ready', 'unknown', 'attention', 'critical',
    ]);
    const { container } = render(<HomeWorkspaceFlow overallTone="review" attentionCount={2} services={projected} />);
    expect(container.querySelectorAll('[data-home-node-state="ready"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-home-node-state="unknown"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-home-node-state="attention"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-home-node-state="critical"]')).toHaveLength(1);
    expect(screen.getByRole('listitem', { name: /Safety workspace flow step: Needs attention/ })).toBeInTheDocument();
  });
  it('does not show ready nodes when viewing saved information or checking', () => {
    for (const options of [{ savedStateOnly: true }, { checking: true }]) {
      expect(homeWorkflowNodeStates(projected, options).every((item) => item.state === 'unknown')).toBe(true);
    }
  });
});
