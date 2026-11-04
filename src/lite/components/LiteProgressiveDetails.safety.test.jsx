// @vitest-environment jsdom
// R6 regression contract — AUTHORED, NOT EXECUTED.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import LiteProgressiveDetails from './LiteProgressiveDetails.jsx';

afterEach(cleanup);

describe('Safety progressive details presentation — authored only', () => {
  const base = {
    presentation: 'safety',
    title: 'Quick safety coverage',
    summary: 'Coverage is incomplete because a tool timed out.',
    status: 'review',
    statusLabel: 'Partial — review required',
    what_happened: ['Pocket Lab checked the available configuration.'],
    what_changed: ['Opening these details did not alter a device.'],
    what_needs_attention: ['One check timed out.'],
    what_did_not_happen: ['No repair started.'],
    saved_for_troubleshooting: { saved: false, summary: 'No protected record was confirmed.' },
    next_step: 'Review unavailable checks before relying on this result.',
    technicalDetails: [{ label: 'Tool outcome', value: 'Timed out' }],
    history: { title: 'History', items: [] },
    sectionRenderMode: 'css-contained',
  };
  it('uses one sheet-owned title and only the sanitized summary inside Safety', () => {
    render(<LiteProgressiveDetails {...base} />);
    const article = document.querySelector('[data-lite-detail-presentation="safety"]');
    expect(article).toBeInTheDocument();
    expect(within(article).queryByRole('heading', { name: 'Quick safety coverage' })).not.toBeInTheDocument();
    expect(within(article).getByText('Coverage is incomplete because a tool timed out.')).toBeInTheDocument();
    expect(article).toHaveClass('is-review');
  });
  it('decorates all comparable sections consistently, without fabricated success', () => {
    render(<LiteProgressiveDetails {...base} />);
    const sections = document.querySelectorAll('.lite-progressive-detail-section');
    const titles = ['What happened','What changed','What needs attention','What did not happen','Saved for troubleshooting','Next step'];
    expect(sections.length).toBeGreaterThanOrEqual(titles.length);
    for (const title of titles) {
      const section = [...sections].find((element) => element.textContent?.includes(title));
      expect(section, title).toBeTruthy();
      expect(section.querySelector('.lite-safety-detail-title .lite-safety-detail-icon svg')).not.toBeNull();
    }
    expect(screen.getByText('No protected record was confirmed.')).toBeInTheDocument();
    expect(screen.queryByText('Evidence saved')).not.toBeInTheDocument();
  });
  it('reuses the collapsed sanitized technical and history disclosures with icons', () => {
    render(<LiteProgressiveDetails {...base} />);
    const technical = document.querySelector('.lite-technical-details[data-lite-detail-presentation="safety"]');
    const history = document.querySelector('.lite-history-section[data-lite-detail-presentation="safety"]');
    expect(technical).toBeInTheDocument();
    expect(history).toBeInTheDocument();
    expect(within(technical).getByRole('button', { name: /Technical details/ })).toHaveAttribute('aria-expanded', 'false');
    expect(within(history).getByRole('button', { name: /History/ })).toHaveAttribute('aria-expanded', 'false');
    expect(technical.querySelector('.lite-safety-detail-icon svg')).not.toBeNull();
    expect(history.querySelector('.lite-safety-detail-icon svg')).not.toBeNull();
    expect(screen.queryByText('Timed out')).not.toBeInTheDocument();
  });
  it('does not add the Safety decorator variant to other shared consumers', () => {
    render(<LiteProgressiveDetails title="App details" what_happened={['App detail only']} />);
    expect(document.querySelector('[data-lite-detail-presentation="default"]')).toBeInTheDocument();
    expect(document.querySelector('.lite-safety-detail-icon')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'App details' })).toBeInTheDocument();
  });
});
