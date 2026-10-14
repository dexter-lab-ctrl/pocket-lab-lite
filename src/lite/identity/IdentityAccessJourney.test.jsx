// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import IdentityAccessJourney from './IdentityAccessJourney.jsx';
import IdentityDetailsContent from './IdentityDetailsContent.jsx';
import { identityPremiumProjection } from './identityPremiumView.js';

describe('Identity Journey and safe Details', () => {
  const view = identityPremiumProjection({
    authenticated: true, person: { display_name: 'Owner Example', role: 'Owner' },
    enterprise: { enabled: false }, passkeys: [{ active: true }],
    sessions: [{ active: true, current: true, auth_method: 'passkey' }],
    recovery: { configured: true, remaining: 6 },
  });
  it('exposes four explicit conceptual stages with accessible actions', () => {
    const onSelect = vi.fn(); render(<IdentityAccessJourney view={view} onSelect={onSelect} />);
    expect(screen.getByText(/not a live sign-in sequence/i)).toBeTruthy();
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    fireEvent.click(screen.getByRole('button', { name: 'View Recovery details' }));
    expect(onSelect).toHaveBeenCalledWith('recovery'); cleanup();
  });
  it('never renders raw passkey identifiers in Details', () => {
    render(<IdentityDetailsContent selection={{ kind: 'passkey', item: { credential_id: 'TOPSECRET', friendly_name: 'Phone passkey', active: true } }} view={view} />);
    expect(screen.getByRole('heading', { name: 'Phone passkey' })).toBeTruthy();
    expect(screen.queryByText('TOPSECRET')).toBeNull(); cleanup();
  });
  it('presents unvalidated authority and disables protected actions', () => {
    render(<IdentityDetailsContent selection={{ kind: 'recovery', item: {} }} view={{ ...view, fresh: false }} disabled onRegenerate={() => { throw Error('should not run'); }} />);
    expect(screen.getByRole('button', { name: /Generate new recovery codes/i }).disabled).toBe(true);
    expect(screen.getByText(/Live access unavailable/i)).toBeTruthy(); cleanup();
  });
});
