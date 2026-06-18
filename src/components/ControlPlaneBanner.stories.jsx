import React from 'react';
import ControlPlaneBanner from './ControlPlaneBanner.jsx';

export default { title: 'Pocket Lab/ControlPlaneBanner', component: ControlPlaneBanner };

export const Professional = { args: { compact: false, simpleMode: false } };
export const SimpleMode = { args: { compact: false, simpleMode: true } };
export const Compact = { args: { compact: true, simpleMode: false } };
