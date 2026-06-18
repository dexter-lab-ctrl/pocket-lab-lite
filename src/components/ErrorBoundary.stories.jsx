import React from 'react';
import ErrorBoundary from './ErrorBoundary.jsx';

function BrokenPanel() { throw new Error('Storybook simulated render failure'); }

export default { title: 'Pocket Lab/ErrorBoundary', component: ErrorBoundary };
export const IsolatedFailure = () => <ErrorBoundary><BrokenPanel /></ErrorBoundary>;
export const HealthyChild = () => <ErrorBoundary><div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 text-emerald-100">Healthy child rendered safely</div></ErrorBoundary>;
