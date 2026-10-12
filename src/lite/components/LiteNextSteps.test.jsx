// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import LiteNextSteps from './LiteNextSteps.jsx';

afterEach(cleanup);

describe('P1 evidence-only guidance', () => {
  it('does not render an empty recommendations container', () => {
    const { container } = render(<LiteNextSteps items={[]} />);
    expect(container.firstChild).toBeNull();
  });
  it('shows review actions only against current facts', () => {
    const open = vi.fn();
    const items = [{ id: 'device-1', label: 'Device disconnected', description: 'Connection not confirmed.', onClick: open }];
    const { rerender } = render(<LiteNextSteps title="Connection review" items={items} />);
    fireEvent.click(screen.getByRole('button', { name: 'Review Device disconnected' }));
    expect(open).toHaveBeenCalledTimes(1);
    rerender(<LiteNextSteps title="Connection review" saved items={items} />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText(/Saved information/)).toBeInTheDocument();
  });
  it('caps guidance for low-power mobile layouts and avoids actionable controls for unknown facts', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ id: String(i), label: 'Area ' + i }));
    render(<LiteNextSteps items={items} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByRole('button', { name: 'Show all 10 items' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Show all 10 items' }));
    expect(screen.getAllByRole('listitem')).toHaveLength(10);
  });
  it('keeps unavailable review controls disabled and explained', () => {
    render(<LiteNextSteps items={[{ label: 'Protected host', onClick: vi.fn(), disabled: true, disabledReason: 'Host cannot be removed' }]} />);
    expect(screen.getByRole('button', { name: /Review Protected host/ })).toBeDisabled();
    expect(screen.getByRole('button')).toHaveAttribute('title', 'Host cannot be removed');
  });
});
