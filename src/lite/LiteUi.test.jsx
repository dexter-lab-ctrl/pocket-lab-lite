// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  LiteActionRow,
  LiteOperationalStory,
  LiteOutcomeNotice,
  LiteTechnicalDetails,
  operationalStoryPresentation,
} from './LiteUi.jsx';

describe('Lite shared operational storytelling primitives', () => {
  it('keeps missing story data unknown instead of presenting it as healthy', () => {
    expect(operationalStoryPresentation({})).toMatchObject({
      state: 'unknown',
      tone: 'unknown',
      headline: 'Status not available',
    });
    expect(operationalStoryPresentation({ state: 'saved', tone: 'ready' }).tone).toBe('saved');
    expect(operationalStoryPresentation({ state: 'signed_out' }).stateLabel).toBe('Signed Out');
  });

  it('renders supplied story content, actions, and disabled reasons without inventing an outcome', () => {
    const reconnect = vi.fn();
    const manageRef = React.createRef();
    render(<LiteOperationalStory
      story={{ state: 'saved', tone: 'saved', headline: 'Showing saved information', summary: 'Pocket Lab is not reachable.', consequence: 'Actions stay protected.', attention: 'Reconnect before making changes.', freshness: { label: 'Saved', detail: '12 minutes ago', state: 'stale' } }}
      primaryAction={{ label: 'Reconnect', onClick: reconnect }}
      manageAction={{ label: 'Manage', disabled: true, disabledReason: 'Saved state only.', buttonRef: manageRef, ariaExpanded: false }}
    />);
    expect(screen.getByText('Showing saved information')).toBeTruthy();
    expect(screen.getByText('Actions stay protected.')).toBeTruthy();
    expect(screen.getByText('Saved state only.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Manage' }).disabled).toBe(true);
    expect(manageRef.current).toBe(screen.getByRole('button', { name: 'Manage' }));
    expect(screen.getByRole('button', { name: 'Manage' }).getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(screen.getByRole('button', { name: 'Reconnect' }));
    expect(reconnect).toHaveBeenCalledOnce();
  });

  it('keeps compact actions, outcomes, and technical details independently optional', () => {
    render(<><LiteActionRow label="Backup" value="Ready" summary="No backup is running." action={{ label: 'Manage', onClick: vi.fn() }} /><LiteOutcomeNotice outcome={{ tone: 'blocked', headline: 'Restore blocked', summary: 'Preview is required.', nextAction: 'Create a preview first.' }} /><LiteTechnicalDetails>Sanitized detail</LiteTechnicalDetails></>);
    expect(screen.getByText('Backup')).toBeTruthy();
    expect(screen.getByText('Restore blocked')).toBeTruthy();
    expect(screen.getByText('Technical details').closest('details')?.open).toBe(false);
  });
});
