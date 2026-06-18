export const PRODUCT_AREAS = {
  operate: {
    label: 'Operate',
    simpleLabel: 'Run',
    description: 'Apps, updates, and releases',
    tabs: ['appstore', 'gitops', 'release'],
  },
  protect: {
    label: 'Protect',
    simpleLabel: 'Protect',
    description: 'Safety, access, policy, and recovery',
    tabs: ['security', 'opa', 'vault', 'recovery'],
  },
  observe: {
    label: 'Observe',
    simpleLabel: 'Check',
    description: 'System status, activity evidence, configuration health, and system map',
    tabs: ['telemetry', 'logs', 'drift', 'blueprint'],
  },
  scale: {
    label: 'Scale',
    simpleLabel: 'Devices',
    description: 'Device onboarding and fleet growth',
    tabs: ['fleet'],
  },
  configure: {
    label: 'Configure',
    simpleLabel: 'Settings',
    description: 'Modes, preferences, and governance controls',
    tabs: ['settings'],
  },
};

export function productAreaForTab(tabId) {
  return Object.entries(PRODUCT_AREAS).find(([, area]) => area.tabs.includes(tabId))?.[0] || 'operate';
}

export function groupedNavItems(items) {
  return Object.entries(PRODUCT_AREAS).map(([key, area]) => ({
    key,
    ...area,
    items: items.filter((item) => area.tabs.includes(item.id)),
  })).filter((area) => area.items.length > 0);
}
