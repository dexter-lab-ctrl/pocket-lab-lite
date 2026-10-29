// @vitest-environment jsdom
// Authored component coverage only — intentionally NOT EXECUTED in this PR.
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import AppStatusChips from './AppStatusChips.jsx';
import AppActionRow from './AppActionRow.jsx';
import AppSummaryCard from './AppSummaryCard.jsx';

afterEach(cleanup);

describe('Apps balanced-density primitives — qualification pending', () => {
  it('keeps long readiness indicators as real visible text without dropping any chip', () => {
    const chips = [
      { key: 'health', label: 'Healthy' },
      { key: 'media', label: 'Connected to the approved photo source with a long display label' },
      { key: 'backup', label: 'Backup destination not ready' },
    ];
    const { container } = render(<AppStatusChips chips={chips} />);
    const region = screen.getByLabelText('App readiness indicators');
    expect(region).toHaveClass('lite-catalog-status-chips');
    expect(container.querySelectorAll('.lite-catalog-status-chips > span')).toHaveLength(3);
    for (const chip of chips) expect(region).toHaveTextContent(chip.label);
  });

  it('preserves existing summary card identity and full descriptive content', () => {
    render(<AppSummaryCard className="is-featured">
      <h2>Long self-hosted photo application</h2>
      <p>Readable supporting content with long words and detailed runtime information.</p>
    </AppSummaryCard>);
    expect(screen.getByText('Long self-hosted photo application').closest('.lite-catalog-app-card'))
      .toHaveClass('lite-catalog-card', 'is-featured');
    expect(screen.getByText(/Readable supporting content/)).toBeVisible();
  });

  it('keeps action text, backend label and enabled click ownership', () => {
    const onClick = vi.fn();
    render(<AppActionRow actionId="check_app" className="lite-app-action-row"
      icon={<span aria-hidden="true">Icon</span>} eyebrow="Safety" label="Check app"
      summary="Check whether app protection is ready without changing its files."
      displayStatus="ready" displayLabel="Ready" buttonLabel="Check app"
      buttonTone="secondary" onClick={onClick} />);
    expect(screen.getByText(/Check whether app protection/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Check app' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('preserves disabled action semantics and does not dispatch backend work', () => {
    const onClick = vi.fn();
    render(<AppActionRow actionId="backup_to_storage" className="lite-app-action-row"
      icon={<span aria-hidden="true">Icon</span>} eyebrow="Recovery" label="Back up to storage"
      summary="A destination is not connected." disabled
      displayStatus="review" displayLabel="Not ready" buttonLabel="Back up"
      disabledReason={<p>Connect a supported destination before backing up.</p>}
      onClick={onClick} />);
    expect(screen.getByRole('button', { name: 'Back up' })).toBeDisabled();
    expect(screen.getByText('Connect a supported destination before backing up.')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Back up' }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
