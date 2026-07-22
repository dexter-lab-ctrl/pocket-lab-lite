import React, { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  applyLiteServiceWorkerUpdate,
  getLiteServiceWorkerUpdateState,
  liteQueryCacheHasRiskyWorkflow,
  setLiteServiceWorkerUpdateBlocker,
  subscribeLiteServiceWorkerUpdates,
} from '../lib/liteServiceWorkerRuntime.js';
import { LiteButton } from './LiteUi.jsx';

export default function LiteServiceWorkerUpdateNotice() {
  const queryClient = useQueryClient();
  const [state, setState] = useState(getLiteServiceWorkerUpdateState);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => subscribeLiteServiceWorkerUpdates(setState), []);

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
