// @vitest-environment jsdom
// Semantic hierarchy is a frontend projection, not scan authority.
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { SafetyStatusHierarchy } from './SafetyNativeCenter.jsx';
import { deriveSafetyStatusPresentation } from './safetyStatusPresentation.js';

afterEach(cleanup);

describe('Safety status hierarchy — source projection', () => {
  it('separates status, scanner execution, findings and safeguard copy', () => {
    const presentation = deriveSafetyStatusPresentation({
      status: 'running', hasRun: true, running: true, coverageReported: true,
      toolResults: { lynis: { status: 'running' }, trivy: { status: 'pending' } },
    });
    render(<SafetyStatusHierarchy presentation={presentation} />);
    const region = screen.getByRole('region', { name: 'Safety check result' });
    expect(within(region).getByText('Safety check in progress')).toBeInTheDocument();
    const scanners = within(region).getByRole('group', { name: 'Scanner execution' });
    expect(within(scanners).getByText('Lynis')).toBeInTheDocument();
    expect(within(scanners).getByText('Trivy')).toBeInTheDocument();
    expect(within(region).getByText('Critical finding assessment not final')).toBeInTheDocument();
    expect(within(region).getByText(/Sensitive values and private paths are hidden/)).toBeInTheDocument();
    expect(region.querySelector('.lite-security-safety-chip')).toBeNull();
  });

  it('does not show completed safety assurance from unknown tool records', () => {
    const presentation = deriveSafetyStatusPresentation({ status: 'completed', hasRun: true, coverageReported: true });
    render(<SafetyStatusHierarchy presentation={presentation} />);
    expect(screen.getByText('Check completed with limited detail')).toBeInTheDocument();
    expect(screen.getByText('Critical finding assessment not final')).toBeInTheDocument();
    expect(screen.queryByText('No critical findings reported')).not.toBeInTheDocument();
  });
});
