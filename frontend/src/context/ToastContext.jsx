import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const STYLES = {
  success: { icon: CheckCircle2, cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', iconCls: 'text-emerald-600' },
  error: { icon: XCircle, cls: 'border-rose-200 bg-rose-50 text-rose-900', iconCls: 'text-rose-600' },
  warning: { icon: AlertTriangle, cls: 'border-amber-200 bg-amber-50 text-amber-900', iconCls: 'text-amber-600' },
  info: { icon: Info, cls: 'border-slate-200 bg-white text-slate-900', iconCls: 'text-blue-600' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (type, message, options = {}) => {
      const id = ++idRef.current;
      setToasts((current) => [...current.slice(-3), { id, type, message, title: options.title }]);
      const duration = options.duration ?? (type === 'error' ? 8000 : 4500);
      if (duration > 0) setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss]
  );

  const api = useMemo(
    () => ({
      success: (msg, opts) => show('success', msg, opts),
      error: (msg, opts) => show('error', msg, opts),
      warning: (msg, opts) => show('warning', msg, opts),
      info: (msg, opts) => show('info', msg, opts),
      dismiss,
    }),
    [show, dismiss]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
        aria-live="polite"
        role="status"
      >
        {toasts.map((toast) => {
          const style = STYLES[toast.type] || STYLES.info;
          const Icon = style.icon;
          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border p-3.5 shadow-lg ${style.cls}`}
            >
              <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.iconCls}`} aria-hidden="true" />
              <div className="min-w-0 flex-1 text-sm">
                {toast.title && <p className="font-semibold">{toast.title}</p>}
                <p className="break-words">{toast.message}</p>
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded p-0.5 opacity-60 hover:opacity-100"
                aria-label="Dismiss notification"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
