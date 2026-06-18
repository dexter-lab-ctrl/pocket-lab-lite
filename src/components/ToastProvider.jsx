import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, ShieldAlert, X } from 'lucide-react';

const ToastContext = createContext({
  notify: () => {},
  success: () => {},
  info: () => {},
  warning: () => {},
  error: () => {},
});

const toneIcon = {
  success: CheckCircle2,
  info: Info,
  warning: AlertTriangle,
  error: ShieldAlert,
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback(({ tone = 'info', title, message, actionLabel, onAction, ttl = 5200 }) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const toast = { id, tone, title, message, actionLabel, onAction };
    setToasts((items) => [toast, ...items].slice(0, 4));
    if (ttl > 0) window.setTimeout(() => dismiss(id), ttl);
    return id;
  }, [dismiss]);

  const value = useMemo(() => ({
    notify,
    success: (message, options = {}) => notify({ tone: 'success', title: options.title || 'Done', message, ...options }),
    info: (message, options = {}) => notify({ tone: 'info', title: options.title || 'Notice', message, ...options }),
    warning: (message, options = {}) => notify({ tone: 'warning', title: options.title || 'Needs attention', message, ...options }),
    error: (message, options = {}) => notify({ tone: 'error', title: options.title || 'Failed', message, ...options }),
  }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-viewport" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => {
          const Icon = toneIcon[toast.tone] || Info;
          return (
            <section key={toast.id} className={`toast-card toast-${toast.tone}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
              <div className="toast-icon"><Icon className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1">
                <p className="toast-title">{toast.title}</p>
                {toast.message ? <p className="toast-message">{toast.message}</p> : null}
                {toast.actionLabel ? (
                  <button
                    type="button"
                    className="toast-action"
                    onClick={() => {
                      toast.onAction?.();
                      dismiss(toast.id);
                    }}
                  >
                    {toast.actionLabel}
                  </button>
                ) : null}
              </div>
              <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification"><X className="h-4 w-4" /></button>
            </section>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
