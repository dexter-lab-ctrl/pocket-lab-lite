import React, { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  applyLiteServiceWorkerUpdate,
  getLiteServiceWorkerUpdateState,
  isLiteTextEntryElement,
  liteQueryCacheHasRiskyWorkflow,
  setLiteServiceWorkerUpdateBlocker,
  subscribeLiteServiceWorkerUpdates,
} from '../lib/liteServiceWorkerRuntime.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';
import { LiteButton } from './LiteUi.jsx';

export default function LiteServiceWorkerUpdateNotice() {
  const queryClient = useQueryClient();
  const activeOverlay = useLiteUiStore((store) => store.activeOverlay);
  const [state, setState] = useState(getLiteServiceWorkerUpdateState);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => subscribeLiteServiceWorkerUpdates(setState), []);

  useEffect(() => {
    setLiteServiceWorkerUpdateBlocker('critical-overlay', Boolean(activeOverlay));
    return () => setLiteServiceWorkerUpdateBlocker('critical-overlay', false);
  }, [activeOverlay]);

  useEffect(() => {
    let timer = null;
    const syncTextEntry = () => {
      setLiteServiceWorkerUpdateBlocker('important-text-entry', isLiteTextEntryElement(document.activeElement));
    };
    const scheduleTextEntrySync = () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = window.setTimeout(syncTextEntry, 0);
    };
    syncTextEntry();
    document.addEventListener('focusin', scheduleTextEntrySync);
    document.addEventListener('focusout', scheduleTextEntrySync);
    return () => {
      if (timer !== null) window.clearTimeout(timer);
      document.removeEventListener('focusin', scheduleTextEntrySync);
      document.removeEventListener('focusout', scheduleTextEntrySync);
      setLiteServiceWorkerUpdateBlocker('important-text-entry', false);
    };
  }, []);

  useEffect(() => {
    const queryCache = queryClient.getQueryCache();
    const syncBlocker = () => {
      setLiteServiceWorkerUpdateBlocker(
        'backend-live-operation',
        liteQueryCacheHasRiskyWorkflow(queryCache.getAll()),
      );
    };
    syncBlocker();
    const unsubscribe = queryCache.subscribe(syncBlocker);
    return () => {
      unsubscribe();
      setLiteServiceWorkerUpdateBlocker('backend-live-operation', false);
    };
  }, [queryClient]);

  if (!state.update_ready) return null;

  const applyUpdate = async () => {
    if (state.update_blocked || applying) return;
    setApplying(true);
    setError('');
    const applied = await applyLiteServiceWorkerUpdate();
    if (!applied) {
      setApplying(false);
      setError('The update is still waiting. Finish active work, then try again.');
    }
  };

  return (
    <aside className="lite-service-worker-update-notice" role="status" aria-live="polite" data-lite-sw-update-ready="true">
      <div>
        <strong>App update ready</strong>
        <p>{state.update_blocked ? 'Finish the active Pocket Lab operation before updating.' : 'Update when you are ready. Saved reads and backend work remain protected.'}</p>
        {error ? <small role="alert">{error}</small> : null}
      </div>
      <LiteButton tone="secondary" onClick={applyUpdate} disabled={state.update_blocked || applying}>
        {applying ? 'Updating…' : state.update_blocked ? 'Update paused' : 'Update app'}
      </LiteButton>
    </aside>
  );
}
