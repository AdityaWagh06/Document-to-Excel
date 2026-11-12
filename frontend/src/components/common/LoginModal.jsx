import { useState } from 'react';
import { Lock, User, AlertCircle, Loader2, FileSpreadsheet, X } from 'lucide-react';
import { loginApi } from '../../services/api';
import STR from '../../constants/strings';

/**
 * variant="page": full-screen sign-in.
 * variant="modal": floating dialog (used over landing page or upon session expiry).
 */
export default function LoginModal({ isOpen, onLoginSuccess, onClose, title, subtitle, variant = 'modal' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  async function performLogin(u, p) {
    if (!u.trim() || !p) {
      setError('Enter both username and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await loginApi(u.trim(), p);
      setPassword('');
      onLoginSuccess?.(data);
    } catch (err) {
      setError(err.message || 'Sign-in failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    await performLogin(username, password);
  }

  const form = (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <div>
        <label htmlFor="login-username" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-700">
          Username
        </label>
        <div className="relative">
          <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-xl border border-slate-300 py-2.5 pl-9 pr-3 text-sm font-medium text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/20"
            disabled={loading}
            autoFocus
            required
          />
        </div>
      </div>

      <div>
        <label htmlFor="login-password" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-700">
          Password
        </label>
        <div className="relative">
          <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-slate-300 py-2.5 pl-9 pr-3 text-sm font-medium text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/20"
            disabled={loading}
            required
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-indigo-600/20 transition hover:from-indigo-700 hover:to-violet-700 hover:shadow-indigo-600/30 disabled:opacity-60 active:scale-[0.99]"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Signing in…
          </>
        ) : (
          'Sign in to Workspace'
        )}
      </button>

    </form>
  );

  if (variant === 'page') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-md">
          {onClose && (
            <div className="mb-4">
              <button
                type="button"
                onClick={onClose}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-semibold"
              >
                ← Back to Landing Page
              </button>
            </div>
          )}
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-500/30">
              <FileSpreadsheet className="h-6 w-6" aria-hidden="true" />
            </div>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-white">{STR.appName}</h1>
            <p className="text-sm text-slate-400">Sign in to your private workspace</p>
          </div>
          <div className="rounded-3xl border border-slate-800 bg-white p-7 shadow-2xl">{form}</div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-dialog-title"
    >
      <div className="relative w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl ring-1 ring-slate-900/10">
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="absolute top-5 right-5 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        )}

        <div className="flex items-center gap-3 mb-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/20">
            <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 id="login-dialog-title" className="text-lg font-bold text-slate-900">
              {title || `Sign in to ${STR.appName}`}
            </h2>
            <p className="text-xs text-slate-500">{subtitle || 'Access document extraction, history & ERP sync'}</p>
          </div>
        </div>

        {form}
      </div>
    </div>
  );
}
