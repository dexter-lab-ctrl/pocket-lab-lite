import { useEffect } from 'react';
import { setLiteServiceWorkerUpdateBlocker } from '../lib/liteServiceWorkerRuntime.js';

export function useLiteServiceWorkerUpdateBlocker(blockerId, active) {
  useEffect(() => {
    setLiteServiceWorkerUpdateBlocker(blockerId, Boolean(active));
    return () => setLiteServiceWorkerUpdateBlocker(blockerId, false);
  }, [active, blockerId]);
}
