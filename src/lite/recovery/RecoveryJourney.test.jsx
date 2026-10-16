// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, afterEach } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/react';
import RecoveryJourney from './RecoveryJourney.jsx';
import RecoveryPremiumTimeline from './RecoveryPremiumTimeline.jsx';
afterEach(() => cleanup());

describe('Recovery Journey and timeline semantics', () => {
  it('renders four native educational buttons and never advances on selection', () => {
    render(<RecoveryJourney stages={{ backup:'completed', verify:'needs_action', preview:'blocked', restore:'unknown' }} />);
    expect(screen.getAllByRole('button')).toHaveLength(4);
    expect(screen.getByText(/Illustrative guide, not a live execution trace/i)).toBeTruthy();
    const verify = screen.getByRole('button', { name:/Verify Needs action/i });
    fireEvent.click(verify);
    expect(verify.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText(/Check the integrity/i)).toBeTruthy();
    expect(screen.getByRole('button', { name:/Back Up Completed/i })).toBeTruthy();
    fireEvent.click(verify);
    expect(verify.getAttribute('aria-expanded')).toBe('false');
  });
  it('supports keyboard button semantics and unknown saved state', () => {
    render(<RecoveryJourney stages={{ backup:'completed' }} saved />);
    const backup = screen.getByRole('button',{name:/Back Up Unknown/i});
    backup.focus();
    fireEvent.keyDown(backup,{key:'Enter'});
    fireEvent.click(backup);
    expect(backup.getAttribute('aria-expanded')).toBe('true');
  });
  it('distinguishes empty, unavailable and current-record timeline', () => {
    const { rerender } = render(<RecoveryPremiumTimeline items={[]} onViewActivity={() => {}} />);
    expect(screen.getByText(/No recovery activity yet/i)).toBeTruthy();
    rerender(<RecoveryPremiumTimeline items={[]} unavailable onViewActivity={() => {}} />);
    expect(screen.getByText(/cannot be confirmed/i)).toBeTruthy();
    rerender(<RecoveryPremiumTimeline items={[{id:'backup:a',kind:'backup',title:'Latest backup record',summary:'Verified as reported',time:'',state:'completed',origin:'snapshot'}]} onViewActivity={() => {}} />);
    expect(screen.getByText(/Current record, not a separate historical event/i)).toBeTruthy();
    expect(screen.getByText(/Time not reported/i)).toBeTruthy();
  });
});