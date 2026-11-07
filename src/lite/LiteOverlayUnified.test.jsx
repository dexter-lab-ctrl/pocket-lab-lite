// @vitest-environment jsdom
// Executed shared overlay geometry, snap and focus regression coverage.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { LiteDesktopPanelControls, LiteSheet } from './LiteOverlay.jsx';

afterEach(cleanup);

describe('Shared LiteSheet / Apps geometry reuse', () => {
  it('uses one accessible desktop Move/Reset/Resize control implementation', () => {
    const reset = vi.fn();
    const move = vi.fn();
    const keyboard = vi.fn();
    render(<LiteDesktopPanelControls title="Safety" geometry={{
      announcement: 'Panel moved',
      reset,
      startPanelInteraction: move,
      adjustPanelWithKeyboard: keyboard,
    }} />);
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Move Safety panel' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Resize Safety panel' }), { key: 'ArrowDown' });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Safety position and size' }));
    expect(move).toHaveBeenCalledWith('move', expect.anything());
    expect(keyboard).toHaveBeenCalledWith('resize', expect.anything());
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status')).toHaveTextContent('Panel moved');
  });

  it('selects Compact and Expand from the same shared mobile snap controller', () => {
    const close = vi.fn();
    render(<LiteSheet open onClose={close} mobileSnap variant="security"
      title="Manage Safety" mobileHeaderVariant="safety">
      <p>Persisted Safety summary</p>
    </LiteSheet>);
    const dialog = screen.getByRole('dialog', { name: 'Manage Safety' });
    expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    const compact = within(dialog).getByRole('button', { name: 'Compact' });
    const expand = within(dialog).getByRole('button', { name: 'Expand' });
    fireEvent.click(compact);
    expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
    expect(compact).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(expand);
    expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    fireEvent.click(expand);
    expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    expect(expand).toHaveAttribute('aria-pressed', 'true');
    expect(dialog).toHaveTextContent('Persisted Safety summary');
    expect(dialog).not.toHaveTextContent('DRAG HANDLE TO RESIZE');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close security details' }));
    expect(close).toHaveBeenCalledTimes(1);
  });
});
