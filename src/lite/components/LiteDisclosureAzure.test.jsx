// @vitest-environment jsdom
// Author-only regression coverage; no test execution or snapshot generation.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import LiteTechnicalDetails from './LiteTechnicalDetails.jsx';
import LiteHistorySection from './LiteHistorySection.jsx';

afterEach(cleanup);

describe('Shared Azure disclosure presentation', () => {
  it('uses one accessible chevron with associated sanitized technical facts', () => {
    const { container } = render(<LiteTechnicalDetails presentation="safety" rows={[
      { label: 'Run by', value: 'Pocket Lab' },
      { label: 'Private path', value: '/data/data/private' },
    ]} />);
    const button = screen.getByRole('button', { name: 'Technical details' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button.querySelector('.lite-shared-disclosure-chevron')).toBeInTheDocument();
    expect(container).not.toHaveTextContent(/Show|Hide/);
    expect(screen.queryByText('Pocket Lab')).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('region', { name: 'Technical details values' })).toHaveTextContent('Pocket Lab');
    expect(screen.queryByText('/data/data/private')).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('groups reported exclusions into a single lazy list without repeating the profile subtitle', () => {
    const { container } = render(<LiteHistorySection
      title="Skipped by Quick Safety Check"
      summary="Excluded to keep daily checks lightweight."
      presentation="safety"
      items={[{ id: 'media', title: 'Photo library and media' }, { id: 'cache', title: 'Go/npm/cache folders' }]}
    />);
    const section = container.querySelector('[data-lite-safety-coverage-list="true"]');
    const toggle = within(section).getByRole('button', { name: 'Skipped by Quick Safety Check' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle.querySelector('.lite-shared-disclosure-chevron')).toBeInTheDocument();
    expect(section).toHaveTextContent('Excluded to keep daily checks lightweight.');
    expect(section).not.toHaveTextContent('skipped by quick profile');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(section).getByText('Photo library and media')).toBeInTheDocument();
    expect(within(section).getByText('Go/npm/cache folders')).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });
});
