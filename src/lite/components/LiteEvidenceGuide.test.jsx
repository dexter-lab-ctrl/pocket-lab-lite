import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import LiteEvidenceGuide from './LiteEvidenceGuide.jsx';

describe('P2 Safety Access Rules evidence guidance', () => {
  it('does not imply success or render an empty guide', () => {
    const { container } = render(<LiteEvidenceGuide title="Safety" />);
    expect(container.firstChild).toBeNull();
  });
  it('shows only supplied evidence and never fabricates missing facts', () => {
    render(<LiteEvidenceGuide title="Safety result" facts={[{ id: 'scan', label: 'Score', value: 'Not reported' }, { id: 'none', label: 'Missing', value: null }]} />);
    expect(screen.getByRole('region', { name: 'Safety result' })).toBeInTheDocument();
    expect(screen.getByText('Not reported')).toBeInTheDocument();
    expect(screen.queryByText('Missing')).toBeNull();
  });
  it('distinguishes saved state and announces protection cautions', () => {
    render(<LiteEvidenceGuide title="Access" saved caution="Changing mode may sign you out." facts={[{ label: 'Mode', value: 'Personal Mode' }]} />);
    expect(screen.getByText(/Saved information/)).toBeInTheDocument();
    expect(screen.getByText(/may sign you out/)).toBeInTheDocument();
  });
  it('keeps bounded responsive facts with no browser-side actions', () => {
    render(<LiteEvidenceGuide title="Rules" facts={Array.from({ length: 9 }, (_, k) => ({ id: String(k), label: 'Fact '+k, value: k }))} />);
    expect(screen.getAllByRole('term')).toHaveLength(5);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
