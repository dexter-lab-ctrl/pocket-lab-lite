import React from 'react';
import HealthEnginePanel from './HealthEnginePanel.jsx';
import { healthAllGreen, healthVaultSealed } from '../mocks/fixtures/pocketlab.js';

export default { title: 'Pocket Lab/HealthEnginePanel', component: HealthEnginePanel };

export const AllGreen = { args: { health: healthAllGreen, simpleMode: false, liveStatus: { ready: true } } };
export const VaultSealedObjectValue = { args: { health: healthVaultSealed, simpleMode: false, liveStatus: { ready: false } } };
export const SimpleDegraded = { args: { health: healthVaultSealed, simpleMode: true, liveStatus: { ready: false } } };
