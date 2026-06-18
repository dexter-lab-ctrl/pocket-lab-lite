import React from 'react';
import LiveEventPanel from './LiveEventPanel.jsx';

export default { title: 'Pocket Lab/LiveEventPanel', component: LiveEventPanel };

export const Operations = { args: { title: 'Operation events', description: 'Recent typed operation activity', operations: ['deploy_blueprint', 'git_sync'], maxItems: 5 } };
export const SimpleMode = { args: { simpleMode: true, title: 'Recent Pocket Lab activity', maxItems: 5 } };
export const Compact = { args: { compact: true, subjectPrefixes: ['pocketlab.events.health'], maxItems: 3 } };
