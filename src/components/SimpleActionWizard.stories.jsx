import React from 'react';
import SimpleActionWizard from './SimpleActionWizard.jsx';

export default { title: 'Pocket Lab/SimpleActionWizard', component: SimpleActionWizard };

export const InstallApp = { args: { title: 'Install', operation: 'deploy_blueprint', target: { blueprint: 'gitea' }, params: { source: 'catalog' } } };
export const AddDevice = { args: { title: 'Add Device', operation: 'fleet_join', target: { node: 'android-lab-02' }, params: { role: 'edge' } } };
export const ChangePassword = { args: { title: 'Change Password', operation: 'rotate_secret', target: { secret: 'gitea' }, params: { reason: 'story' } } };
