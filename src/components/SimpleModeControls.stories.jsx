import React from 'react';
import { AdvancedDetails, SimpleStatus, TechnicalBadge } from './SimpleModeControls.jsx';

export default { title: 'Pocket Lab/SimpleModeControls' };

export const AdvancedDetailsCollapsed = () => <AdvancedDetails simpleMode title="Support details"><div>Operation: deploy_blueprint</div><div>Job: job-123</div></AdvancedDetails>;
export const SimpleStatusRunning = () => <SimpleStatus simpleMode phase="running" message="Installing your app..." jobId="job-123" />;
export const TechnicalBadgeHiddenInSimpleMode = () => <TechnicalBadge simpleMode><span>deploy_blueprint</span></TechnicalBadge>;
