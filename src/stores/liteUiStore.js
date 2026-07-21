import { create } from 'zustand';

const DEFAULT_TAB = 'home';
const DEFAULT_MANAGE_SECTION = 'media';
const DEFAULT_SECURITY_PROFILE = 'quick';
const DEFAULT_SECURITY_MANAGE_SECTION = 'overview';
const DEFAULT_SECURITY_HISTORY_LIMIT = 20;
const DEFAULT_RECOVERY_MANAGE_SECTION = 'backup';
const RECOVERY_MANAGE_SECTIONS = new Set(['backup', 'restore', 'protection', 'history']);
const RECOVERY_DETAILS_PANELS = new Set(['verify', 'preview', 'restore']);
const RECOVERY_CONFIRMATION_KINDS = new Set(['lite', 'database']);
const TOAST_KINDS = new Set(['info', 'success', 'warning', 'error']);
const REFRESH_RESULTS = new Set(['refreshing', 'fresh', 'saved', 'stale', 'expired', 'unreachable', 'failed']);

function normalizeId(value, fallback = '') {
  return String(value || fallback).trim().toLowerCase();
}

function normalizeToast(input = {}) {
  const kind = TOAST_KINDS.has(input.kind) ? input.kind : 'info';
  const id = input.id || `lite-toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return {
    id,
    kind,
    title: String(input.title || '').trim() || (kind === 'success' ? 'Updated' : 'Pocket Lab'),
    message: String(input.message || '').trim(),
    timeoutMs: Number.isFinite(input.timeoutMs) ? Math.max(0, input.timeoutMs) : kind === 'error' || kind === 'warning' ? 0 : 4200,
    createdAt: Date.now(),
  };
}

function normalizeOverlay(input = {}) {
  if (!input || typeof input !== 'object') return null;
  const type = normalizeId(input.type, 'details');
  return {
    type,
    id: normalizeId(input.id, input.actionId || input.appId || type),
    appId: normalizeId(input.appId),
    actionId: normalizeId(input.actionId),
    source: String(input.source || '').trim(),
    openedAt: Date.now(),
  };
}


function normalizeSecurityProfile(value = DEFAULT_SECURITY_PROFILE) {
  const normalized = normalizeId(value, DEFAULT_SECURITY_PROFILE).replace(/[\s-]+/g, '_');
  if (['full', 'full_local', 'full_local_check'].includes(normalized)) return 'full';
  if (['app', 'app_check', 'application'].includes(normalized)) return 'app';
  return 'quick';
}

function normalizeSecurityDetailsPanel(value = null) {
  const panel = normalizeId(value);
  if (panel === 'checkpath' || panel === 'check_path') return 'checkPath';
  return ['changes', 'attention', 'coverage', 'evidence', 'history', 'technical_details'].includes(panel)
    ? panel
    : null;
}

function normalizeSecurityFindingId(value = null) {
  return normalizeId(value).slice(0, 160) || null;
}

function normalizeRecoveryManageSection(value = DEFAULT_RECOVERY_MANAGE_SECTION) {
  const section = normalizeId(value, DEFAULT_RECOVERY_MANAGE_SECTION);
  return RECOVERY_MANAGE_SECTIONS.has(section) ? section : DEFAULT_RECOVERY_MANAGE_SECTION;
}

function normalizeRecoveryDetailsPanel(value = null) {
  const panel = normalizeId(value);
  return RECOVERY_DETAILS_PANELS.has(panel) ? panel : null;
}

function normalizeRecoveryConfirmation(value = null) {
  const kind = normalizeId(value);
  return RECOVERY_CONFIRMATION_KINDS.has(kind) ? kind : null;
}

function recoveryOverlayFallback(state = {}) {
  return state.recoveryManageOpen
    ? normalizeOverlay({ type: 'manage', id: 'recovery', source: 'recovery' })
    : null;
}

function normalizeRefreshResult(result) {
  const normalized = normalizeId(result, 'fresh');
  return REFRESH_RESULTS.has(normalized) ? normalized : 'fresh';
}

function refreshTitleForResult(result) {
  switch (normalizeRefreshResult(result)) {
    case 'refreshing': return 'Refreshing…';
    case 'saved': return 'Showing saved state';
    case 'stale': return 'Showing saved state';
    case 'expired': return 'Saved state expired';
    case 'unreachable': return 'Pocket Lab is not reachable';
    case 'failed': return 'Reconnect to continue';
    case 'fresh':
    default:
      return 'Updated just now';
  }
}

function refreshSummaryForResult(result) {
  switch (normalizeRefreshResult(result)) {
    case 'refreshing': return 'Pocket Lab is checking for fresh state.';
    case 'saved': return 'Saved state is visible while Pocket Lab refreshes.';
    case 'stale': return 'Pocket Lab is showing saved state until fresh state is reachable.';
    case 'expired': return 'Reconnect to continue.';
    case 'unreachable': return 'Reconnect to continue.';
    case 'failed': return 'Pocket Lab could not refresh this view.';
    case 'fresh':
    default:
      return 'Fresh state is visible.';
  }
}

function buildRefreshFeedback(scope, result, extra = {}) {
  const normalizedResult = normalizeRefreshResult(result);
  return {
    scope: normalizeId(scope, 'global'),
    result: normalizedResult,
    title: String(extra.title || '').trim() || refreshTitleForResult(normalizedResult),
    summary: String(extra.summary || '').trim() || refreshSummaryForResult(normalizedResult),
    detail: String(extra.detail || '').trim(),
    checkedAt: extra.checkedAt || new Date().toISOString(),
  };
}

export const useLiteUiStore = create((set, get) => ({
  activeTab: DEFAULT_TAB,
  setActiveTab: (tabId) => set({ activeTab: normalizeId(tabId, DEFAULT_TAB), mobileMenuOpen: false, moreSheetOpen: false }),

  mobileMenuOpen: false,
  setMobileMenuOpen: (open) => set({ mobileMenuOpen: Boolean(open) }),
  toggleMobileMenu: () => set((state) => ({ mobileMenuOpen: !state.mobileMenuOpen })),

  moreSheetOpen: false,
  setMoreSheetOpen: (open) => set({ moreSheetOpen: Boolean(open) }),

  activeOverlay: null,
  openOverlay: (overlay) => set({ activeOverlay: normalizeOverlay(overlay) }),

  securityManageOpen: false,
  activeSecurityProfile: DEFAULT_SECURITY_PROFILE,
  activeSecurityManageSection: DEFAULT_SECURITY_MANAGE_SECTION,
  activeSecurityDetailsPanel: null,
  expandedSecurityFindingId: null,
  lastSecurityRunIdViewed: null,
  activeSecurityHistoryLimit: DEFAULT_SECURITY_HISTORY_LIMIT,
  activeSecurityEvidenceRunId: null,
  activeSecurityDetailsRunId: null,
  setSecurityManageOpen: (open) => set((state) => ({
    securityManageOpen: Boolean(open),
    activeSecurityDetailsPanel: open ? state.activeSecurityDetailsPanel : null,
    expandedSecurityFindingId: open ? state.expandedSecurityFindingId : null,
    activeOverlay: open
      ? normalizeOverlay({ type: 'manage', id: 'security', source: 'security' })
      : state.activeOverlay?.source === 'security' ? null : state.activeOverlay,
  })),
  setActiveSecurityProfile: (profile) => {
    const nextProfile = normalizeSecurityProfile(profile);
    set((state) => ({
      activeSecurityProfile: nextProfile,
      activeSecurityDetailsPanel: state.activeSecurityProfile === nextProfile ? state.activeSecurityDetailsPanel : null,
      expandedSecurityFindingId: state.activeSecurityProfile === nextProfile ? state.expandedSecurityFindingId : null,
      activeSecurityEvidenceRunId: state.activeSecurityProfile === nextProfile ? state.activeSecurityEvidenceRunId : null,
      activeSecurityDetailsRunId: state.activeSecurityProfile === nextProfile ? state.activeSecurityDetailsRunId : null,
    }));
  },
  setActiveSecurityManageSection: (sectionId) => set({ activeSecurityManageSection: normalizeId(sectionId, DEFAULT_SECURITY_MANAGE_SECTION) }),
  setActiveSecurityDetailsPanel: (panelId, runId = null) => {
    const nextPanel = normalizeSecurityDetailsPanel(panelId);
    set({
      activeSecurityDetailsPanel: nextPanel,
      activeSecurityDetailsRunId: nextPanel ? normalizeSecurityFindingId(runId) : null,
      lastSecurityRunIdViewed: runId ? normalizeSecurityFindingId(runId) : get().lastSecurityRunIdViewed,
      activeOverlay: nextPanel ? normalizeOverlay({ type: 'details', id: nextPanel, source: 'security' }) : null,
    });
  },
  setExpandedSecurityFindingId: (findingId) => set({ expandedSecurityFindingId: normalizeSecurityFindingId(findingId) }),
  setLastSecurityRunIdViewed: (runId) => set({ lastSecurityRunIdViewed: normalizeSecurityFindingId(runId) }),
  setActiveSecurityHistoryLimit: (limit = DEFAULT_SECURITY_HISTORY_LIMIT) => {
    const nextLimit = Number.isFinite(Number(limit)) ? Math.max(1, Math.min(50, Number(limit))) : DEFAULT_SECURITY_HISTORY_LIMIT;
    set({ activeSecurityHistoryLimit: nextLimit });
  },
  setActiveSecurityEvidenceRunId: (runId) => set({ activeSecurityEvidenceRunId: normalizeSecurityFindingId(runId) }),


  recoveryManageOpen: false,
  activeRecoveryManageSection: DEFAULT_RECOVERY_MANAGE_SECTION,
  activeRecoveryDetailsPanel: null,
  recoveryDatabaseDetailsOpen: false,
  recoveryEvidenceOpen: false,
  recoveryRestoreConfirmation: null,
  setRecoveryManageOpen: (open) => set((state) => {
    const nextOpen = Boolean(open);
    return {
      recoveryManageOpen: nextOpen,
      activeRecoveryDetailsPanel: nextOpen ? state.activeRecoveryDetailsPanel : null,
      recoveryDatabaseDetailsOpen: nextOpen ? state.recoveryDatabaseDetailsOpen : false,
      recoveryEvidenceOpen: nextOpen ? state.recoveryEvidenceOpen : false,
      recoveryRestoreConfirmation: nextOpen ? state.recoveryRestoreConfirmation : null,
      activeOverlay: nextOpen
        ? normalizeOverlay({ type: 'manage', id: 'recovery', source: 'recovery' })
        : state.activeOverlay?.source === 'recovery' ? null : state.activeOverlay,
    };
  }),
  setActiveRecoveryManageSection: (sectionId) => set({
    activeRecoveryManageSection: normalizeRecoveryManageSection(sectionId),
  }),
  setActiveRecoveryDetailsPanel: (panelId) => set((state) => {
    const nextPanel = normalizeRecoveryDetailsPanel(panelId);
    return {
      activeRecoveryDetailsPanel: nextPanel,
      activeOverlay: nextPanel
        ? normalizeOverlay({ type: 'details', id: nextPanel, source: 'recovery' })
        : recoveryOverlayFallback(state),
    };
  }),
  setRecoveryDatabaseDetailsOpen: (open) => set((state) => {
    const nextOpen = Boolean(open);
    return {
      recoveryDatabaseDetailsOpen: nextOpen,
      activeOverlay: nextOpen
        ? normalizeOverlay({ type: 'details', id: 'database', source: 'recovery' })
        : recoveryOverlayFallback(state),
    };
  }),
  setRecoveryEvidenceOpen: (open) => set((state) => {
    const nextOpen = Boolean(open);
    return {
      recoveryEvidenceOpen: nextOpen,
      activeOverlay: nextOpen
        ? normalizeOverlay({ type: 'details', id: 'evidence', source: 'recovery' })
        : recoveryOverlayFallback(state),
    };
  }),
  setRecoveryRestoreConfirmation: (kind) => set((state) => {
    const nextKind = normalizeRecoveryConfirmation(kind);
    return {
      recoveryRestoreConfirmation: nextKind,
      activeOverlay: nextKind
        ? normalizeOverlay({ type: 'confirmation', id: nextKind, source: 'recovery' })
        : recoveryOverlayFallback(state),
    };
  }),
  resetRecoveryTransientUi: () => set((state) => ({
    activeRecoveryDetailsPanel: null,
    recoveryDatabaseDetailsOpen: false,
    recoveryEvidenceOpen: false,
    recoveryRestoreConfirmation: null,
    activeOverlay: recoveryOverlayFallback(state),
  })),
  resetRecoveryUi: () => set((state) => ({
    recoveryManageOpen: false,
    activeRecoveryManageSection: DEFAULT_RECOVERY_MANAGE_SECTION,
    activeRecoveryDetailsPanel: null,
    recoveryDatabaseDetailsOpen: false,
    recoveryEvidenceOpen: false,
    recoveryRestoreConfirmation: null,
    activeOverlay: state.activeOverlay?.source === 'recovery' ? null : state.activeOverlay,
  })),

  closeOverlay: (typeOrId) => set((state) => {
    if (!typeOrId) return { activeOverlay: null };
    const wanted = normalizeId(typeOrId);
    const current = state.activeOverlay;
    if (!current || current.type === wanted || current.id === wanted) return { activeOverlay: null };
    return {};
  }),
  closeAllOverlays: () => set({ activeOverlay: null, manageAppId: null, activeDetailsActionId: null, securityManageOpen: false, activeSecurityDetailsPanel: null, expandedSecurityFindingId: null, recoveryManageOpen: false, activeRecoveryDetailsPanel: null, recoveryDatabaseDetailsOpen: false, recoveryEvidenceOpen: false, recoveryRestoreConfirmation: null }),

  toasts: [],
  pushToast: (toast) => {
    const nextToast = normalizeToast(toast);
    set((state) => ({ toasts: [...state.toasts.filter((item) => item.id !== nextToast.id), nextToast].slice(-4) }));
    return nextToast.id;
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
  clearToasts: () => set({ toasts: [] }),

  refreshByScope: {},
  beginRefresh: (scope = 'global') => {
    const normalizedScope = normalizeId(scope, 'global');
    set((state) => ({
      refreshByScope: {
        ...state.refreshByScope,
        [normalizedScope]: buildRefreshFeedback(normalizedScope, 'refreshing'),
      },
    }));
  },
  finishRefresh: (scope = 'global', result = 'fresh', extra = {}) => {
    const normalizedScope = normalizeId(scope, 'global');
    set((state) => ({
      refreshByScope: {
        ...state.refreshByScope,
        [normalizedScope]: buildRefreshFeedback(normalizedScope, result, extra),
      },
    }));
  },
  clearRefresh: (scope = 'global') => {
    const normalizedScope = normalizeId(scope, 'global');
    set((state) => {
      const next = { ...state.refreshByScope };
      delete next[normalizedScope];
      return { refreshByScope: next };
    });
  },

  manageAppId: null,
  manageSectionByAppId: {},
  activeManageSection: DEFAULT_MANAGE_SECTION,
  activeActionId: null,
  activeDetailsActionId: null,
  setManageApp: (appId, sectionId) => {
    const appKey = normalizeId(appId, 'photoprism');
    const storedSection = get().manageSectionByAppId[appKey];
    const nextSection = normalizeId(sectionId || storedSection || get().activeManageSection, DEFAULT_MANAGE_SECTION);
    set((state) => ({
      manageAppId: appKey,
      activeManageSection: nextSection,
      manageSectionByAppId: sectionId ? { ...state.manageSectionByAppId, [appKey]: nextSection } : state.manageSectionByAppId,
      activeOverlay: normalizeOverlay({ type: 'manage', id: appKey, appId: appKey, source: 'app-catalog' }),
    }));
  },
  clearManageApp: () => set((state) => ({
    manageAppId: null,
    activeActionId: null,
    activeDetailsActionId: null,
    activeOverlay: state.activeOverlay?.type === 'manage' ? null : state.activeOverlay,
  })),
  setManageSection: (appIdOrSectionId, maybeSectionId) => {
    const hasApp = maybeSectionId !== undefined;
    const appKey = normalizeId(hasApp ? appIdOrSectionId : get().manageAppId, 'photoprism');
    const sectionId = normalizeId(hasApp ? maybeSectionId : appIdOrSectionId, DEFAULT_MANAGE_SECTION);
    set((state) => ({
      activeManageSection: sectionId,
      manageSectionByAppId: { ...state.manageSectionByAppId, [appKey]: sectionId },
    }));
  },
  setActiveAction: (actionId) => set({ activeActionId: normalizeId(actionId) || null }),
  setActiveDetailsAction: (actionId) => {
    const nextActionId = normalizeId(actionId);
    set({
      activeDetailsActionId: nextActionId || null,
      activeOverlay: nextActionId ? normalizeOverlay({ type: 'details', id: nextActionId, actionId: nextActionId, appId: get().manageAppId, source: 'app-catalog' }) : null,
    });
  },
  clearActiveDetailsAction: () => set((state) => ({
    activeDetailsActionId: null,
    activeOverlay: state.activeOverlay?.type === 'details' ? null : state.activeOverlay,
  })),
}));

export function useLiteActiveTab() {
  return useLiteUiStore((state) => state.activeTab);
}

export function useLiteOverlayState() {
  return useLiteUiStore((state) => state.activeOverlay);
}

export function useLiteToasts() {
  return useLiteUiStore((state) => state.toasts);
}

export function useLiteRefreshFeedback(scope = 'global') {
  return useLiteUiStore((state) => state.refreshByScope[normalizeId(scope, 'global')] || null);
}

export function useLiteCatalogManageState(appId = 'photoprism') {
  const appKey = normalizeId(appId, 'photoprism');
  return useLiteUiStore((state) => ({
    manageAppId: state.manageAppId,
    isManaging: state.manageAppId === appKey,
    activeManageSection: state.manageSectionByAppId[appKey] || state.activeManageSection,
    activeActionId: state.activeActionId,
    activeDetailsActionId: state.activeDetailsActionId,
  }));
}

export function useLiteSecurityManageState() {
  return useLiteUiStore((state) => ({
    securityManageOpen: state.securityManageOpen,
    activeSecurityProfile: state.activeSecurityProfile,
    activeSecurityManageSection: state.activeSecurityManageSection,
    activeSecurityDetailsPanel: state.activeSecurityDetailsPanel,
    expandedSecurityFindingId: state.expandedSecurityFindingId,
    lastSecurityRunIdViewed: state.lastSecurityRunIdViewed,
    activeSecurityHistoryLimit: state.activeSecurityHistoryLimit,
    activeSecurityEvidenceRunId: state.activeSecurityEvidenceRunId,
    activeSecurityDetailsRunId: state.activeSecurityDetailsRunId,
  }));
}


export function useLiteRecoveryManageState() {
  return useLiteUiStore((state) => ({
    recoveryManageOpen: state.recoveryManageOpen,
    activeRecoveryManageSection: state.activeRecoveryManageSection,
    activeRecoveryDetailsPanel: state.activeRecoveryDetailsPanel,
    recoveryDatabaseDetailsOpen: state.recoveryDatabaseDetailsOpen,
    recoveryEvidenceOpen: state.recoveryEvidenceOpen,
    recoveryRestoreConfirmation: state.recoveryRestoreConfirmation,
  }));
}

export const LITE_UI_STORE_RECOVERY_UI_ONLY = true;
export const LITE_UI_STORE_DOES_NOT_STORE_RECOVERY_PAYLOADS = true;
export const LITE_UI_STORE_SECURITY_UI_ONLY = true;
export const LITE_UI_STORE_DOES_NOT_STORE_SECURITY_PAYLOADS = true;
export const LITE_UI_STORE_IS_UI_ONLY = true;
export const LITE_UI_STORE_UI_COORDINATION_ONLY = true;
