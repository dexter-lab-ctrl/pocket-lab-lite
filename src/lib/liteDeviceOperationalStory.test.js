import { describe, expect, it } from 'vitest';
import { selectDeviceOperationalStory } from './liteViewModels.js';

describe('Devices operational story presentation', () => {
  it('keeps an online device distinct from remote access readiness', () => {
    const story = selectDeviceOperationalStory({
      id: 'phone',
      status: 'online',
      connection: 'online',
      remote_access: { ready: false, status: 'remote_access_not_ready' },
    });
    expect(story).toMatchObject({
      state: 'online',
      headline: 'Connected',
      remote_access: 'not_ready',
    });
    expect(story.consequence).toContain('remote access is not ready');
  });

  it('keeps joining, waiting, offline, and unknown truthful and separate', () => {
    expect(selectDeviceOperationalStory({ status: 'joining', connection: 'joining' })).toMatchObject({ state: 'joining', connection_state: 'disconnected' });
    expect(selectDeviceOperationalStory({ status: 'waiting', connection: 'waiting' })).toMatchObject({ state: 'waiting', headline: 'Waiting for this device' });
    expect(selectDeviceOperationalStory({ status: 'offline', connection: 'offline' })).toMatchObject({ state: 'offline', headline: 'Device is offline' });
    expect(selectDeviceOperationalStory({ status: 'offline', connection: 'offline', agent_status: 'running' })).toMatchObject({
      state: 'offline',
      headline: 'Device is disconnected',
    });
    expect(selectDeviceOperationalStory({ status: 'unknown' })).toMatchObject({ state: 'unknown', tone: 'unknown' });
  });

  it('does not advertise recovery unless the prepared assessment allows it', () => {
    const unavailable = selectDeviceOperationalStory({ status: 'agent_stopped', restart_agent_assessment: { allowed: false, command_deliverable: false } });
    expect(unavailable).toMatchObject({ state: 'agent_stopped', next_action: null });
    expect(unavailable.attention).toContain('cannot currently deliver');

    expect(selectDeviceOperationalStory({ status: 'agent_stopped', restart_agent_assessment: { allowed: true } })).toMatchObject({
      state: 'agent_stopped',
      next_action: { kind: 'restart', label: 'Restart agent' },
    });
  });

  it('keeps repairing, protected-host, and saved states out of live-ready presentation', () => {
    expect(selectDeviceOperationalStory({ status: 'offline', restart_progress: { status: 'repairing', summary: 'Supervisor is checking.' } })).toMatchObject({
      state: 'repairing',
      connection_state: 'repairing',
    });
    expect(selectDeviceOperationalStory({ role: 'server_host', status: 'online' })).toMatchObject({
      state: 'protected',
      headline: 'Pocket Lab server',
    });
    expect(selectDeviceOperationalStory({ status: 'online' }, { savedStateOnly: true })).toMatchObject({
      state: 'saved',
      tone: 'saved',
      next_action: null,
    });
  });
});
