import { create } from 'zustand';

const DEFAULT_TAB = 'home';
const DEFAULT_MANAGE_SECTION = 'media';
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
  closeOverlay: (typeOrId) => set((state) => {
    if (!typeOrId) return { activeOverlay: null };
    const wanted = normalizeId(typeOrId);
    const current = state.activeOverlay;
    if (!current || current.type === wanted || current.id === wanted) return { activeOverlay: null };
    return {};
  }),
  closeAllOverlays: () => set({ activeOverlay: null, manageAppId: null, activeDetailsActionId: null }),

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

export const LITE_UI_STORE_IS_UI_ONLY = true;
export const LITE_UI_STORE_UI_COORDINATION_ONLY = true;
