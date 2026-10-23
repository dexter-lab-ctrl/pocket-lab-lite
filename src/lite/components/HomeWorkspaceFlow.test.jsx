// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { HomeWorkspaceFlow, homeWorkflowPresentation } from '../LiteHome.jsx';

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
        'Device workspace flow step', 'Services workspace flow step',
        'Apps workspace flow step', 'Safety workspace flow step',
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
