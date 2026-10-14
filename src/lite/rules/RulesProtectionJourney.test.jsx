// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react';
import RulesProtectionJourney from './RulesProtectionJourney.jsx';
import RulesDecisionInsight from './RulesDecisionInsight.jsx';
import { RulesActivationTimeline, RulesRevisionTimeline } from './RulesPremiumTimeline.jsx';

describe('Premium Rules Journey, Decision Insight and source timelines', () => {
  it('has exactly four selectable educational stages, no automatic advancement', () => {
    render(<RulesProtectionJourney />);
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText(/Illustrative guide/i)).toBeTruthy();
    const stage = screen.getByRole('button', { name: /Who Request/ });
    fireEvent.click(stage);
    expect(stage.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText(/authenticated actor/i)).toBeTruthy();
    fireEvent.click(stage);
    expect(stage.getAttribute('aria-expanded')).toBe('false');
    cleanup();
  });
  it('does not reconstruct backend checks during decision inspection', () => {
    render(<RulesProtectionJourney mode="inspect" decision={{ status: 'Blocked', action: 'Remove a device' }} />);
    fireEvent.click(screen.getByRole('button', { name: /Check Evaluate/ }));
    expect(screen.getByText(/not a reconstructed trace/i)).toBeTruthy();
    cleanup();
  });
  it('distinguishes decision permission from execution and masks unreturned actor facts', () => {
    render(<RulesDecisionInsight decision={{ allow: true, action_id: 'device.remove', reason_code: 'unknown_reason' }} />);
    expect(screen.getByText(/Actor information unavailable/i)).toBeTruthy();
    expect(screen.getByText(/does not establish that execution/i)).toBeTruthy();
    const actionRow = screen.getByRole('heading', { name: 'What would change?' }).parentElement;
    expect(within(actionRow).getByText('Remove a device')).toBeTruthy();
    cleanup();
  });
  it('displays a simulation disclaimer without granting authority', () => {
    render(<RulesDecisionInsight simulated decision={{ allow: true }} />);
    expect(screen.getByText(/No real permission or system change is granted/i)).toBeTruthy();
    cleanup();
  });
  it('renders uncertain recovery and only factual revision comparison', () => {
    render(<RulesActivationTimeline operation={{ state: 'uncertain' }} backendReachable={false} />);
    const activationHeader = screen.getByRole('heading', { name: 'Rules activation' }).parentElement;
    expect(within(activationHeader).getByText('Uncertain')).toBeTruthy();
    expect(screen.queryByText('Server-reported activation success')).toBeNull();
    cleanup();
    render(<RulesRevisionTimeline health={{ db_active_revision: 'rev-a', known_good_revision: 'rev-b' }} />);
    expect(screen.getByText(/no historical transitions are inferred/i)).toBeTruthy();
    cleanup();
  });
});
