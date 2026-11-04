// @vitest-environment jsdom
// Native Safety source tests. AUTHORED ONLY — not executed in this PR.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { SafetyCenterHero, SafetyDestinations, SafetyManageNavigation } from './SafetyNativeCenter.jsx';

vi.mock('../LiteUi.jsx', () => ({
  LiteButton: ({ children, onClick, disabled, ariaLabel }) =>
    <button type="button" aria-label={ariaLabel} disabled={disabled} onClick={onClick}>{children}</button>,
}));

afterEach(cleanup);
const base = {
  status: 'No urgent safety issues', profile: 'Quick Scan', reportedScore: true,
  score: 92, hasRun: true, freshness: 'Last checked recently', saved: false,
  offline: false, findings: 1, coverageReported: true, checkedCount: 4,
  coverageQuality: 'reported', evidenceSaved: true, busy: false, writeBlocked: false,
  onQuickCheck: vi.fn(), onOpenChecks: vi.fn(),
};

describe('Native Safety Center — backend-truthful presentation (unexecuted)', () => {
  it('shows one reported score, review, coverage and protected evidence without a second action grid', () => {
    const onQuickCheck = vi.fn();
    render(<SafetyCenterHero {...base} onQuickCheck={onQuickCheck} />);
    expect(screen.getByRole('region', { name: 'Safety overview' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Reported safety score 92' })).toBeInTheDocument();
    expect(screen.getByText('4 checked')).toBeInTheDocument();
    expect(screen.getByText('Saved')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Run Quick Scan' }));
    expect(onQuickCheck).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Run Full Scan' })).not.toBeInTheDocument();
  });
  it('does not convert a missing score or missing coverage to zero or success', () => {
    render(<SafetyCenterHero {...base} reportedScore={false} score={undefined}
      coverageReported={false} hasRun={false} evidenceSaved={false} />);
    expect(screen.getByRole('img', { name: 'Safety score not reported' })).toBeInTheDocument();
    expect(screen.getByText('Not reported')).toBeInTheDocument();
    expect(screen.getByText('Not checked')).toBeInTheDocument();
    expect(screen.getByText('Not available')).toBeInTheDocument();
  });
  it('rejects null and empty numeric score even when reported flag is set', () => {
    const { rerender } = render(<SafetyCenterHero {...base} reportedScore score={null} />);
    expect(screen.getByRole('img', { name: 'Safety score not reported' })).toBeInTheDocument();
    rerender(<SafetyCenterHero {...base} reportedScore score="" />);
    expect(screen.getByRole('img', { name: 'Safety score not reported' })).toBeInTheDocument();
  });
  it('preserves partial scope and flags saved offline truth', () => {
    render(<SafetyCenterHero {...base} offline saved coverageQuality="incomplete" />);
    expect(screen.getByText('Incomplete coverage')).toBeInTheDocument();
    expect(screen.getByText(/Offline — showing saved information/)).toBeInTheDocument();
  });
  it('blocks duplicate or unreachable writes but keeps Manage navigation available', () => {
    const run = vi.fn(), checks = vi.fn();
    const { rerender } = render(<SafetyCenterHero {...base} busy onQuickCheck={run} onOpenChecks={checks} />);
    expect(screen.getByRole('button', { name: 'Safety check already in progress' })).toBeDisabled();
    rerender(<SafetyCenterHero {...base} writeBlocked blockedReason="Reconnect to continue"
      onQuickCheck={run} onOpenChecks={checks} />);
    expect(screen.getByRole('button', { name: 'Reconnect to run Quick Scan' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Other checks in Manage Safety/ }));
    expect(checks).toHaveBeenCalledOnce();
    expect(run).not.toHaveBeenCalled();
  });
  it('keeps destinations clickable without fabricating result detail', () => {
    const open = vi.fn();
    render(<SafetyDestinations onOpen={open} hasRun={false} findings={0}
      coverageReported={false} lastChecked={null} />);
    const nav = screen.getByRole('navigation', { name: 'Safety destinations' });
    expect(within(nav).getAllByRole('button')).toHaveLength(3);
    fireEvent.click(within(nav).getByRole('button', { name: 'Open Coverage & Checks' }));
    expect(open).toHaveBeenCalledWith('coverage');
    expect(nav).toHaveTextContent('Scope not reported');
  });
});

const sections = [
  { id: 'overview', label: 'Overview' }, { id: 'issues', label: 'Issues' },
  { id: 'coverage', label: 'Coverage' }, { id: 'checks', label: 'Checks' },
  { id: 'changes', label: 'Changes' }, { id: 'history', label: 'History' },
  { id: 'evidence', label: 'Evidence' }, { id: 'check_path', label: 'Check path' },
  { id: 'technical_details', label: 'Technical details' },
];
const descriptions = Object.fromEntries(sections.map(({ id }) => [id, 'Backend-reported ' + id]));
describe('Safety Manage grouped navigation — authored only', () => {
  it('retains all nine destinations, grouped semantics, selected state and dedicated Back', () => {
    const choose = vi.fn(), back = vi.fn();
    const { rerender } = render(<SafetyManageNavigation sections={sections} descriptions={descriptions}
      selected="overview" mobileDetailOpen={false} onChoose={choose} onBack={back}>
      <p>Selected backend detail</p>
    </SafetyManageNavigation>);
    const nav = screen.getByRole('navigation', { name: 'Manage Safety sections' });
    expect(within(nav).getAllByRole('button')).toHaveLength(9);
    expect(within(nav).getByText('Run Checks')).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('button', { name: 'Open Coverage in Manage Safety' }));
    expect(choose).toHaveBeenCalledWith('coverage');
    rerender(<SafetyManageNavigation sections={sections} descriptions={descriptions}
      selected="coverage" mobileDetailOpen onChoose={choose} onBack={back}>
      <p>Selected backend detail</p>
    </SafetyManageNavigation>);
    expect(within(nav).getByRole('button', { name: 'Open Coverage in Manage Safety' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getAllByRole('heading', { name: 'Coverage' })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'Coverage', level: 2 })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Coverage', level: 3 })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Back to Manage Safety' }));
    expect(back).toHaveBeenCalledOnce();
  });
});
