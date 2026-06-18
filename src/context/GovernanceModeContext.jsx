import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'pocketlab_governance_mode';

const GovernanceModeContext = createContext({
  governanceMode: 'personal',
  enterpriseModeEnabled: false,
  setGovernanceMode: () => {},
  syncGovernanceMode: async () => {},
  status: 'local',
  error: null,
});

export const GovernanceModeProvider = ({ children }) => {
  const [governanceMode, setGovernanceModeState] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem(STORAGE_KEY) || 'personal';
    }
    return 'personal';
  });
  const [status, setStatus] = useState('local');
  const [error, setError] = useState(null);

  const applyLocal = (mode) => {
    const normalized = mode === 'enterprise' ? 'enterprise' : 'personal';
    setGovernanceModeState(normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, normalized);
    }
    return normalized;
  };

  const syncGovernanceMode = async (mode) => {
    const normalized = applyLocal(mode);
    setStatus('syncing');
    setError(null);
    try {
      const res = await fetch('/api/settings/governance', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ governanceMode: normalized, enterpriseModeEnabled: normalized === 'enterprise' }),
      });
      if (!res.ok) throw new Error(`Governance settings update failed: ${res.status}`);
      const data = await res.json();
      applyLocal(data.governanceMode || normalized);
      setStatus('synced');
    } catch (err) {
      setError(err.message || String(err));
      setStatus('local');
    }
  };

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/api/settings/governance', { cache: 'no-store', headers: { Accept: 'application/json' } });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data?.governanceMode) {
          applyLocal(data.governanceMode);
          setStatus('synced');
        }
      } catch {
        setStatus('local');
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const value = useMemo(() => ({
    governanceMode,
    enterpriseModeEnabled: governanceMode === 'enterprise',
    setGovernanceMode: syncGovernanceMode,
    syncGovernanceMode,
    status,
    error,
  }), [governanceMode, status, error]);

  return (
    <GovernanceModeContext.Provider value={value}>
      {children}
    </GovernanceModeContext.Provider>
  );
};

export const useGovernanceMode = () => useContext(GovernanceModeContext);
