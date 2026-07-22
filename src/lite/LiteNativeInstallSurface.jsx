import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Download, Share2 } from 'lucide-react';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import {
  applyLiteAppBadge,
  canOfferLiteInstall,
  clearLiteInstallCooldown,
  collectLiteInstallDiagnostics,
  deriveLiteAppBadgeState,
  isLiteStandaloneDisplay,
  LITE_INSTALL_DISMISSAL_KEY,
  requestLiteInstall,
  shareLiteSafeWorkspace,
} from '../lib/liteNativeInstall.js';
import {
  getLiteNavigationPreloadDiagnostics,
  getLiteServiceWorkerUpdateState,
  liteQueryCacheHasRiskyWorkflow,
  subscribeLiteServiceWorkerUpdates,
} from '../lib/liteServiceWorkerRuntime.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';

function standaloneMediaQuery(windowObject = globalThis.window) {
  try {
    return windowObject?.matchMedia?.('(display-mode: standalone)') || null;
  } catch {
    return null;
  }
}

export default function LiteNativeInstallSurface() {
  const queryClient = useQueryClient();
  const online = useOnlineStatus();
  const activeTab = useLiteUiStore((state) => state.activeTab);
  const activeOverlay = useLiteUiStore((state) => state.activeOverlay);
  const pushToast = useLiteUiStore((state) => state.pushToast);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [installed, setInstalled] = useState(() => isLiteStandaloneDisplay());
  const [workflowActive, setWorkflowActive] = useState(false);
  const [prompting, setPrompting] = useState(false);
  const [cooldownRevision, setCooldownRevision] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [updateState, setUpdateState] = useState(getLiteServiceWorkerUpdateState);
  const previousBadgeCountRef = useRef(null);

  useEffect(() => subscribeLiteServiceWorkerUpdates(setUpdateState), []);

  useEffect(() => {
    const onStorage = (event) => {
      if (event.key === LITE_INSTALL_DISMISSAL_KEY) setCooldownRevision((value) => value + 1);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  useEffect(() => {
    const media = standaloneMediaQuery();
    const syncInstalled = () => setInstalled(isLiteStandaloneDisplay());
    const onBeforeInstallPrompt = (event) => {
      event.preventDefault?.();
      if (isLiteStandaloneDisplay()) return;
      setDeferredPrompt(event);
    };
    const onAppInstalled = () => {
      clearLiteInstallCooldown();
      setInstalled(true);
      setDeferredPrompt(null);
      setPrompting(false);
      setStatusMessage('Pocket Lab Lite is installed.');
    };

    syncInstalled();
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', onAppInstalled);
    media?.addEventListener?.('change', syncInstalled);
    media?.addListener?.(syncInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
      window.removeEventListener('appinstalled', onAppInstalled);
      media?.removeEventListener?.('change', syncInstalled);
      media?.removeListener?.(syncInstalled);
    };
  }, []);

  useEffect(() => {
    const queryCache = queryClient.getQueryCache();
    const syncWorkflowState = () => {
      setWorkflowActive(liteQueryCacheHasRiskyWorkflow(queryCache.getAll()));
    };
    syncWorkflowState();
    return queryCache.subscribe(syncWorkflowState);
  }, [queryClient]);

  useEffect(() => {
    const queryCache = queryClient.getQueryCache();
    let active = true;
    const syncBadge = async () => {
      const badge = deriveLiteAppBadgeState(queryCache.getAll(), { online });
      const result = await applyLiteAppBadge(navigator, badge.count, previousBadgeCountRef.current);
      if (active && result.reason !== 'failed') previousBadgeCountRef.current = result.count;
    };
    syncBadge();
    const unsubscribe = queryCache.subscribe(syncBadge);
    return () => {
      active = false;
      unsubscribe();
    };
  }, [online, queryClient]);

  const installAvailable = useMemo(() => canOfferLiteInstall({
    promptAvailable: Boolean(deferredPrompt),
    installed,
    workflowActive: !online || workflowActive || updateState.update_blocked,
    criticalOverlayOpen: Boolean(activeOverlay),
  }), [activeOverlay, cooldownRevision, deferredPrompt, installed, online, updateState.update_blocked, workflowActive]);

  useEffect(() => {
    if (!import.meta.env.DEV) return undefined;
    let active = true;
    const baseDiagnostics = collectLiteInstallDiagnostics({
      promptAvailable: Boolean(deferredPrompt),
      installed,
      updateWaiting: updateState.update_ready,
    });
    getLiteNavigationPreloadDiagnostics().then((navigationPreload) => {
      if (active) console.info('[Pocket Lab Lite install diagnostics]', { ...baseDiagnostics, ...navigationPreload });
    });
    return () => { active = false; };
  }, [deferredPrompt, installed, updateState.update_ready]);

  const installApp = async () => {
    if (!installAvailable || prompting) return;
    setPrompting(true);
    setStatusMessage('');
    const outcome = await requestLiteInstall(deferredPrompt);
    setDeferredPrompt(null);
    setPrompting(false);
    setCooldownRevision((value) => value + 1);
    if (outcome.status === 'accepted_pending_confirmation') {
      const message = 'Installation requested. Pocket Lab will confirm when the browser finishes.';
      setStatusMessage(message);
      pushToast({ kind: 'info', title: 'Install requested', message });
    } else if (outcome.status === 'dismissed') {
      const message = 'Install dismissed. The option will return later.';
      setStatusMessage(message);
      pushToast({ kind: 'info', title: 'Install dismissed', message });
    } else if (outcome.status === 'failed') {
      const message = 'Install is not available right now. You can keep using Pocket Lab in this browser.';
      setStatusMessage(message);
      pushToast({ kind: 'warning', title: 'Install unavailable', message });
    }
  };

  const shareWorkspace = async () => {
    const outcome = await shareLiteSafeWorkspace({ screenId: activeTab });
    if (outcome.status === 'shared') {
      setStatusMessage('Pocket Lab Lite shared.');
      pushToast({ kind: 'success', title: 'Shared', message: 'Pocket Lab Lite shared.' });
    } else if (outcome.status === 'copied') {
      setStatusMessage('Safe Pocket Lab link copied.');
      pushToast({ kind: 'success', title: 'Link copied', message: 'Safe Pocket Lab link copied.' });
    } else if (outcome.status === 'cancelled') {
      setStatusMessage('Sharing cancelled.');
    } else {
      setStatusMessage('Sharing is not available in this browser.');
      pushToast({ kind: 'warning', title: 'Sharing unavailable', message: 'Sharing is not available in this browser.' });
    }
  };

  return (
    <div className="lite-native-install-surface" data-lite-native-install-surface="true">
      <button
        type="button"
        className="lite-native-surface-button"
        onClick={shareWorkspace}
        aria-label="Share Pocket Lab Lite"
        title="Share Pocket Lab Lite"
      >
        <Share2 className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">Share</span>
      </button>
      {installAvailable ? (
        <button
          type="button"
          className="lite-native-surface-button lite-native-surface-button--install"
          onClick={installApp}
          disabled={prompting}
          aria-label="Install Pocket Lab Lite"
          title="Install Pocket Lab Lite"
        >
          <Download className="h-4 w-4" aria-hidden="true" />
          <span className="lite-native-install-label">{prompting ? 'Opening…' : 'Install'}</span>
        </button>
      ) : null}
      <span className="sr-only" role="status" aria-live="polite">{statusMessage}</span>
    </div>
  );
}
