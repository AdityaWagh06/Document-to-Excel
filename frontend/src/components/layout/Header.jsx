import { FileText, History, RefreshCw, MessageSquare, BarChart3, LayoutDashboard, LogOut, FileSpreadsheet } from 'lucide-react';
import STR from '../../constants/strings';

export const NAV_TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'extract', label: 'Scan & review', icon: FileText },
  { id: 'history', label: 'Invoices', icon: History },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'erp', label: 'ERP / Tally', icon: RefreshCw },
  { id: 'whatsapp', label: 'WhatsApp', icon: MessageSquare },
];

export default function Header({ activeTab, setActiveTab, authUser, onLogoutClick }) {
  return (
    <header className="sticky top-0 z-40 mb-6 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/30">
            <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold tracking-tight text-slate-900">{STR.appName}</p>
            <p className="hidden truncate text-xs text-slate-500 sm:block">{STR.appTagline}</p>
          </div>
        </div>

        <nav className="hidden items-center gap-0.5 rounded-xl bg-slate-100/80 p-1 lg:flex" aria-label="Main">
          {NAV_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  isActive ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {authUser && (
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden items-center gap-2 text-sm font-medium text-slate-700 sm:inline-flex">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink-950 text-[11px] font-semibold uppercase text-white" aria-hidden="true">
                {String(authUser).slice(0, 2)}
              </span>
              {authUser}
            </span>
            <button
              type="button"
              onClick={onLogoutClick}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        )}
      </div>

      <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-2 py-2 lg:hidden" aria-label="Main mobile">
        {NAV_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium ${
                isActive ? 'bg-ink-950 text-white' : 'bg-slate-100 text-slate-700'
              }`}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {tab.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
