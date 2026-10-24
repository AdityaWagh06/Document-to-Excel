import { useState } from 'react';
import { Lock, User, AlertCircle, Loader2, FileSpreadsheet } from 'lucide-react';
import { loginApi } from '../../services/api';
import STR from '../../constants/strings';

/**
 * variant="page": full-screen sign-in shown before the app loads.
 * variant="modal": shown over the app when the session expires, so unsaved
 * edits stay in memory while the user signs in again.
 */
export default function LoginModal({ isOpen, onLoginSuccess, variant = 'modal' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Enter both username and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await loginApi(username.trim(), password);
      setPassword('');
      onLoginSuccess?.(data);
    } catch (err) {
      setError(err.message || 'Sign-in failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  const form = (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
      <div>
        <label htmlFor="login-username" className="mb-1 block text-sm font-medium text-slate-700">Username</label>
        <div className="relative">
          <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            disabled={loading}
            autoFocus
            required
          />
        </div>
      </div>
      <div>
        <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-slate-700">Password</label>
        <div className="relative">
          <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            disabled={loading}
            required
          />
        </div>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Signing in…
          </>
        ) : (
          'Sign in'
        )}
      </button>
    </form>
  );

  if (variant === 'page') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white">
              <FileSpreadsheet className="h-6 w-6" aria-hidden="true" />
            </div>
            <h1 className="mt-3 text-xl font-semibold text-slate-900">{STR.appName}</h1>
            <p className="text-sm text-slate-500">Sign in to continue</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">{form}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-labelledby="session-expired-title">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
        <h2 id="session-expired-title" className="text-lg font-semibold text-slate-900">Your session has expired</h2>
        <p className="mb-4 mt-1 text-sm text-slate-600">Sign in again to continue. Unsaved edits on this page are kept.</p>
        {form}
      </div>
    </div>
  );
}
