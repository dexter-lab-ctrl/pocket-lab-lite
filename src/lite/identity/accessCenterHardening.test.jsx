// @vitest-environment jsdom
// P0–P7 Access hardening: AUTHORED — NOT EXECUTED.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import AccessCenterSummary from './AccessCenterSummary.jsx';
import AccessDetailPresentation from './AccessDetailPresentation.jsx';
import AccessHowItWorks, { accessEducationContext } from './AccessHowItWorks.jsx';
import IdentityDetailsContent from './IdentityDetailsContent.jsx';
import { formatAccessTimestamp } from './accessCenterPresentation.js';
import { LiteTechnicalFacts } from '../LiteUx.jsx';

afterEach(cleanup);
const noop = () => {};
const owner = { name:'Test Owner', role:'Owner', mode:'Personal Mode', fresh:true,
  signedIn:true, authentication:'Passkey', passkeys:1, sessions:1, recoveryConfigured:true };

describe('Access Center global component and presentation hardening — not executed', () => {
  it('preserves backend-reported data and opens the compact education entry', () => {
    const explain = vi.fn();
    render(<AccessCenterSummary view={owner} data={{ authenticated:true, enterprise:{enabled:false} }}
      onManage={noop} onActivity={noop} onActivityDetails={noop} onExplain={explain} />);
    expect(screen.getByText('Test Owner')).toBeInTheDocument();
    const button = screen.getByRole('button', { name:/How Access works/i });
    fireEvent.click(button);
    expect(explain).toHaveBeenCalledTimes(1);
    expect(button.querySelector('svg:last-child')).toBeTruthy();
  });
  it('does not manufacture readiness when the projection is stale', () => {
    render(<AccessCenterSummary view={{ ...owner, fresh:false, recoveryConfigured:null }}
      data={{ authenticated:true }} onManage={noop} onActivity={noop}
      onActivityDetails={noop} onExplain={noop} />);
    expect(screen.getByText('Showing saved access information')).toBeInTheDocument();
    expect(screen.queryByText('Access is ready')).not.toBeInTheDocument();
  });
  it('uses native details with the same chevron class as shared progressive disclosures', () => {
    const { container } = render(<LiteTechnicalFacts title="Technical facts"
      facts={[{ id:'source', label:'Source', value:'Identity & Access API' }]} />);
    const disclosure = container.querySelector('details.lite-ux-technical-facts');
    const summary = within(disclosure).getByText('Technical facts');
    expect(disclosure).not.toHaveAttribute('open');
    expect(summary.closest('summary').querySelector('.lite-shared-disclosure-chevron')).toBeTruthy();
    fireEvent.click(summary);
    expect(disclosure).toHaveAttribute('open');
    fireEvent.click(summary);
    expect(disclosure).not.toHaveAttribute('open');
  });
  it('formats real instants without guessing absent or invalid dates', () => {
    expect(formatAccessTimestamp(null)).toBe('Not reported');
    expect(formatAccessTimestamp('not a date')).toBe('Not reported');
    expect(formatAccessTimestamp('2026-11-05T13:00:00.000Z', 'en-US')).toMatch(/Nov/);
  });
  it('shows the common icon and explanation layout without inventing status', () => {
    render(<AccessDetailPresentation kind="passkey" title="Example passkey"
      status={null} summary="Server reports this record." />);
    expect(screen.getByRole('heading', { name:'Example passkey' })).toBeInTheDocument();
    expect(screen.getByText('Not reported')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name:'What this means' })).toBeInTheDocument();
  });
  it('explains Personal, Enterprise, signed-out and offline limitations', () => {
    expect(accessEducationContext(owner, true)).toMatch(/Personal Mode/);
    expect(accessEducationContext({ ...owner, role:'Viewer', mode:'Enterprise Mode' }, true)).toMatch(/server checks/);
    expect(accessEducationContext(owner, false)).toMatch(/Sign in/);
    expect(accessEducationContext({ ...owner, fresh:false }, true)).toMatch(/fresh server decision/);
    render(<AccessHowItWorks view={owner} signedIn />);
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText('Make protected changes')).toBeInTheDocument();
  });
  it('keeps missing credential state distinct from revoked and does not expose raw dates', () => {
    render(<IdentityDetailsContent selection={{ kind:'passkey', item:{ friendly_name:'Passkey without state', created_at:'invalid' } }}
      view={owner} onRename={noop} onRemovePasskey={noop} onSignOutSession={noop}
      onRegenerate={noop} onSignOutOtherSessions={noop} onOpenManage={noop} disabled />);
    expect(screen.getByText('Passkey without state')).toBeInTheDocument();
    expect(screen.getAllByText('Not reported').length).toBeGreaterThan(0);
    expect(screen.queryByText('Revoked')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name:/Remove passkey/i })).not.toBeInTheDocument();
  });
  it('keeps protected actions disabled for stale reads', () => {
    render(<IdentityDetailsContent selection={{ kind:'passkey', item:{ friendly_name:'Current passkey', active:true } }}
      view={{ ...owner, fresh:false }} onRename={noop} onRemovePasskey={noop}
      onSignOutSession={noop} onRegenerate={noop} onSignOutOtherSessions={noop}
      onOpenManage={noop} disabled />);
    expect(screen.getByRole('button', { name:'Remove passkey' })).toBeDisabled();
    expect(screen.getByText('Live access unavailable')).toBeInTheDocument();
  });
});
