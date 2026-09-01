import { describe, expect, it } from 'vitest';
import { deviceConnectionFlowLabel, deviceConnectionFlowState } from './DeviceCard.jsx';
import { fleetOperationalStory, remoteAccessPresentation } from '../LiteDevices.jsx';

describe('DeviceCard connection presentation', () => {
  it('keeps connected, repairing, disconnected, and protected server states distinct', () => {
    expect(deviceConnectionFlowState({ isServerCard: false, linkState: 'joined', presentation: { state: 'online' } })).toBe('connected');
    expect(deviceConnectionFlowState({ isServerCard: false, linkState: 'repairing', presentation: { state: 'repairing' } })).toBe('repairing');
    expect(deviceConnectionFlowState({ isServerCard: false, linkState: 'disconnected', presentation: { state: 'offline' } })).toBe('disconnected');
    expect(deviceConnectionFlowState({ isServerCard: true, linkState: 'server', presentation: { state: 'online' } })).toBe('server');
  });

  it('provides status text independent of connection color or motion', () => {
    expect(deviceConnectionFlowLabel('connected', 'Studio phone', false)).toContain('connected');
    expect(deviceConnectionFlowLabel('repairing', 'Studio phone', false)).toContain('restoring');
    expect(deviceConnectionFlowLabel('disconnected', 'Studio phone', false)).toContain('disconnected');
    expect(deviceConnectionFlowLabel('server', 'Pocket Lab Lite Server', true)).toContain('protected server host');
  });

  it('keeps healthy remote access compact while retaining an explicit not-ready state', () => {
    expect(remoteAccessPresentation({ status: 'healthy', ready: true }).title).toBe('Ready');
    expect(remoteAccessPresentation({ status: 'not_ready', ready: false }).title).toBe('Remote access not ready');
    expect(remoteAccessPresentation({ status: 'healthy', ready: true }, true)).toMatchObject({ ready: false, saved: true });
  });

  it('keeps fleet saved and unknown state out of live-ready copy', () => {
    expect(fleetOperationalStory({ savedStateOnly: true }).state).toBe('saved');
    expect(fleetOperationalStory({ data: null }).state).toBe('unknown');
    expect(fleetOperationalStory({ data: {}, devices: [{ id: 'offline' }], onlineDevices: 0 }).state).toBe('review');
  });
});
