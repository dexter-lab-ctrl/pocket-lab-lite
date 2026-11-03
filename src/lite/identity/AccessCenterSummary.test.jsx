// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import AccessCenterSummary from './AccessCenterSummary.jsx';
import AccessManageNavigation from './AccessManageNavigation.jsx';

afterEach(cleanup);

const view = { name: 'Fixture Owner', role: 'Owner', mode: 'Personal Mode', signedIn: true,
  fresh: true, authentication: 'Passkey', passkeys: 1, sessions: 1,
  currentSessionKnown: true, recoveryConfigured: true, remaining: 3 };

describe('Azure Horizon Access native composition — authored, not executed', () => {
  it('renders one hero and grouped navigation without duplicating large summaries', () => {
    const onManage = vi.fn();
    render(<AccessCenterSummary view={view} data={{ authenticated: true, enterprise: { enabled: false } }}
      onManage={onManage} onActivity={vi.fn()} onActivityDetails={vi.fn()} />);
    expect(screen.getByRole('region', { name: 'Access profile' })).toHaveAttribute('data-access-readiness', 'ready');
    expect(screen.getByRole('heading', { name: 'Sign-in & protection' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Manage Access' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Sign-in methods' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Passkeys, 1 active' }));
    expect(onManage).toHaveBeenCalledWith('passkeys');
  });
  it('shows backend-unknown status and a truthful empty activity state', () => {
    render(<AccessCenterSummary view={{ ...view, recoveryConfigured: null, fresh: false }} data={{ authenticated: true }}
      onManage={vi.fn()} onActivity={vi.fn()} onActivityDetails={vi.fn()} />);
    expect(screen.getByText('Showing saved access information')).toBeInTheDocument();
    expect(screen.getByText('No recent access activity was reported.')).toBeInTheDocument();
  });
  it('separates grouped index selection and Back from Close ownership', () => {
    const setSection = vi.fn();
    const { rerender } = render(<AccessManageNavigation section={null} setSection={setSection}>
      <div>Selected details</div>
    </AccessManageNavigation>);
    const nav = screen.getByRole('navigation', { name: 'Manage Access sections' });
    fireEvent.click(within(nav).getByRole('button', { name: 'Passkeys' }));
    expect(setSection).toHaveBeenCalledWith('passkeys');
    rerender(<AccessManageNavigation section="passkeys" setSection={setSection}><div>Selected details</div></AccessManageNavigation>);
    fireEvent.click(screen.getByRole('button', { name: 'All access settings' }));
    expect(setSection).toHaveBeenCalledWith(null);
  });
  it('does not surface a Personal Mode people directory', () => {
    render(<AccessManageNavigation section={null} setSection={vi.fn()}>
      <div>Overview</div>
    </AccessManageNavigation>);
    expect(screen.queryByRole('button', { name: /People & roles/i })).not.toBeInTheDocument();
  });
});
