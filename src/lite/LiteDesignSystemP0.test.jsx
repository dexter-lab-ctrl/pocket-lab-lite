import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { StatusBadge, statusLanguage } from '../components/ui.jsx';
import { LiteButton, LiteActionRow } from './LiteUi.jsx';
import { LiteConsequenceSummary } from './LiteUx.jsx';

describe('Lite P0 shared interaction safety', () => {
  it('distinguishes accepted, verifying, uncertain and stale from success', () => {
    for (const state of ['accepted', 'verifying', 'uncertain', 'stale']) {
      expect(statusLanguage(state).label).not.toBe('Done');
    }
    render(<StatusBadge status="uncertain" />);
    expect(screen.getByText('Needs confirmation').getAttribute('data-lite-status')).toBe('uncertain');
  });

  it('blocks busy actions and explains disabled controls', () => {
    const action = vi.fn();
    const { rerender } = render(<LiteButton busy onClick={action}>Restore</LiteButton>);
    const button = screen.getByRole('button', { name: 'Restore' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    fireEvent.click(button);
    expect(action).not.toHaveBeenCalled();
    rerender(<LiteButton disabled disabledReason="Device is unreachable" onClick={action}>Restore</LiteButton>);
    expect(button).toHaveAttribute('title', 'Device is unreachable');
  });

  it('keeps action row controls separately owned and exposes the blocker', () => {
    const action = vi.fn();
    render(<LiteActionRow label="Restart Agent" disabledReason="Protected host" action={{ label: 'Restart', disabled: true, onClick: action }} />);
    expect(screen.getByRole('button', { name: /Restart/ })).toBeDisabled();
    expect(screen.getByText('Protected host')).toBeInTheDocument();
    expect(action).not.toHaveBeenCalled();
  });

  it('labels consequence summaries for assistive technology', () => {
    render(<LiteConsequenceSummary value={{ title: 'Before continuing', summary: 'Review the change.' }} />);
    expect(screen.getByRole('region', { name: 'Action consequences' })).toBeInTheDocument();
  });
});
