// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import AppActionDetailsLazy from './AppActionDetailsLazy.jsx';

afterEach(cleanup);

const details = (status, extras = {}) => ({
  title:'Back up app', status, summary:'Backend status is not independently confirmed.',
  what_happened:['The request was recorded.'],
  what_changed:['Nothing changed.'],
  what_did_not_happen:['No media was copied.'],
  saved_for_troubleshooting:{saved:true,backend_only:true,summary:'A troubleshooting record was saved.'},
  ...extras
});

describe('Azure premium Action Details — AUTHORED NOT EXECUTED', () => {
  it.each(['requested','queued','blocked','skipped','unknown'])('does not turn %s into a success because a record was saved', async status => {
    const {container} = render(<AppActionDetailsLazy actionId="backup_app" details={details(status)} />);
    expect(container.querySelector('.lite-app-premium-details.is-ready')).toBeNull();
    expect(await screen.findByText(/Nothing changed/)).toBeInTheDocument();
  });
  it('preserves structured evidence and explicit non-change text', async () => {
    render(<AppActionDetailsLazy actionId="backup_app" details={details('failed', {what_needs_attention:['Backup destination unavailable.']})} />);
    expect(await screen.findByText(/Backup destination unavailable/)).toBeInTheDocument();
    expect(await screen.findByText(/No media was copied/)).toBeInTheDocument();
  });
  it('distinguishes readiness from execution completion', () => {
    const {container}=render(<AppActionDetailsLazy actionId="backup_app" details={details('ready')} />);
    expect(container.querySelector('.lite-app-premium-details.is-ready')).toBeNull();
    expect(screen.getByText('Ready to start')).toBeInTheDocument();
  });
  it('recognizes explicit terminal backend completion, not mere description copy', () => {
    const {container}=render(<AppActionDetailsLazy actionId="backup_app" details={details('completed')} />);
    expect(container.querySelector('.lite-app-premium-details.is-ready')).not.toBeNull();
  });
});
