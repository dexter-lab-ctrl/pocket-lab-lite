import React from 'react';
import LiteEvidenceGuide from './components/LiteEvidenceGuide.jsx';

export default { title: 'Pocket Lab Lite/P2 Safety Access Rules Guidance', component: LiteEvidenceGuide, tags: ['autodocs'] };
const frame = (element) => <main className="theme-pocket-lite-daylight" style={{ padding: 24, minHeight: '100vh' }}>{element}</main>;
export const SafetyPartialCoverage = { render: () => frame(<LiteEvidenceGuide title="Safety result and coverage" facts={[{ label: 'Check profile', value: 'Quick' }, { label: 'Score', value: 'Not reported' }, { label: 'Coverage', value: 'Partial' }]} caution="Coverage and freshness matter before taking action." />) };
export const AccessSavedReadOnly = { render: () => frame(<LiteEvidenceGuide title="Your current access" saved facts={[{ label: 'Current role', value: 'Owner' }, { label: 'Workspace mode', value: 'Personal Mode' }]} caution="Mode changes can end the session." />) };
export const RulesActivationReview = { render: () => frame(<LiteEvidenceGuide title="How protection decisions work" facts={[{ label: 'Protection engine', value: 'Readiness not confirmed' }, { label: 'Update state', value: 'Change in progress' }]} caution="A simulated decision never grants authorization." />) };
