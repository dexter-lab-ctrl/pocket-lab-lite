/**
 * Devices-only presentation rules. Backend fleet, health, trust and capability
 * projections remain authoritative; these helpers never produce live status.
 */
export const DEVICE_MANAGE_GROUPS = Object.freeze([
  {
    id: 'device', label: 'Device',
    sections: [
      { id: 'overview', label: 'Overview', description: 'Identity and system', icon: 'server' },
      { id: 'connection', label: 'Connection', description: 'Heartbeat and private access', icon: 'link' },
      { id: 'health', label: 'Health', description: 'Resources and recovery', icon: 'heart' },
      { id: 'roles', label: 'Roles', description: 'Assigned responsibilities', icon: 'shield', peerOnly: true },
      { id: 'services', label: 'Services', description: 'Reported services and apps', icon: 'layers' },
      { id: 'backup', label: 'Backup', description: 'Photo backup availability', icon: 'backup', peerOnly: true },
    ],
  },
  {
    id: 'activity', label: 'Activity & details',
    sections: [
      { id: 'history', label: 'History', description: 'Reported device changes', icon: 'history' },
      { id: 'technical', label: 'Technical', description: 'Protected diagnostics', icon: 'settings' },
    ],
  },
]);

export function deviceManageSections(isProtectedServer = false) {
  return DEVICE_MANAGE_GROUPS.map((group) => ({
    ...group,
    sections: group.sections.filter((section) => !section.peerOnly || !isProtectedServer),
  }));
}

const serviceGroupFor = (service = {}) => {
  const id = String(service.service_id || service.id || '').toLowerCase();
  if (/photo|prism|gitea|hosted|app[-_]/.test(id)) return 'Hosted apps';
  if (/tailscale|nats|caddy|proxy|network|connect/.test(id)) return 'Connectivity';
  if (/supervisor|recover|backup/.test(id)) return 'Recovery';
  return 'Pocket Lab core';
};

export function groupDeviceServices(services = []) {
  const order = ['Pocket Lab core', 'Connectivity', 'Recovery', 'Hosted apps'];
  const groups = new Map(order.map((id) => [id, []]));
  for (const service of Array.isArray(services) ? services : []) {
    groups.get(serviceGroupFor(service)).push(service);
  }
  return order.filter((id) => groups.get(id).length).map((label) => ({
    label, services: groups.get(label),
  }));
}

/** Date grouping only for backend-supplied timestamps; no synthetic events. */
export function deviceEventDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return '';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

export function deviceEventIcon(state = '') {
  const value = String(state || '').toLowerCase();
  if (/offline|lost|stopped|blocked|failed/.test(value)) return 'alert';
  if (/repair|recover|restart/.test(value)) return 'recover';
  if (/online|restored|joined|ready|accepted/.test(value)) return 'online';
  return 'activity';
}
