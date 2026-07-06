import React from 'react';
import { CheckCircle2, Info, TriangleAlert, X, XCircle } from 'lucide-react';
import { useLiteUiStore } from '../stores/liteUiStore.js';

const TOAST_ICONS = {
  success: CheckCircle2,
  warning: TriangleAlert,
  error: XCircle,
  info: Info,
};

export default function LiteToastHost() {
  const toasts = useLiteUiStore((state) => state.toasts);
  const dismissToast = useLiteUiStore((state) => state.dismissToast);

  React.useEffect(() => {
    const timers = toasts
      .filter((toast) => toast.timeoutMs > 0)
      .map((toast) => window.setTimeout(() => dismissToast(toast.id), toast.timeoutMs));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [dismissToast, toasts]);

  if (!toasts.length) return null;

  return (
    <div className="lite-toast-host" role="status" aria-live="polite" aria-relevant="additions text">
      {toasts.map((toast) => {
        const Icon = TOAST_ICONS[toast.kind] || Info;
        return (
          <div key={toast.id} className={`lite-toast is-${toast.kind || 'info'}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            <div className="lite-toast-copy">
              <strong>{toast.title}</strong>
              {toast.message ? <p>{toast.message}</p> : null}
            </div>
            <button type="button" className="lite-toast-close" onClick={() => dismissToast(toast.id)} aria-label="Dismiss message">
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export const LITE_TOAST_HOST_USES_ZUSTAND = true;
