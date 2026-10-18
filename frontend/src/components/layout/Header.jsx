import { Zap, HelpCircle, Settings, CheckCircle, Download, FileText, History, RefreshCw, MessageSquare, BarChart3 } from 'lucide-react';
import STR from '../../constants/strings';

export default function Header({ processedCount, activeTab, setActiveTab }) {
  const navTabs = [
    { id: 'extract', label: 'Scanner & Extraction', icon: FileText },
    { id: 'history', label: 'Invoice History', icon: History },
    { id: 'erp', label: 'ERP Integration', icon: RefreshCw },
    { id: 'whatsapp', label: 'WhatsApp Automation', icon: MessageSquare },
    { id: 'analytics', label: 'Analytics & Vendors', icon: BarChart3 },
  ];

  return (
    <header className="mb-6">
      {/* Navigation Bar */}
      <nav className="sticky top-0 z-50 border-b border-slate-200/60 bg-white/95 backdrop-blur-xl shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 shadow-lg">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">{STR.appName}</h1>
              <p className="text-xs text-slate-500">AI-Powered Invoice & ERP Automation</p>
            </div>
          </div>

          {/* Nav Tabs */}
          <div className="hidden md:flex items-center gap-1 bg-slate-100/80 p-1.5 rounded-xl border border-slate-200/60">
            {navTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    isActive
                      ? 'bg-white text-blue-600 shadow-sm border border-slate-200/50'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-blue-600' : 'text-slate-500'}`} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-semibold border border-blue-200">
              Processed: <span className="font-bold">{processedCount}</span>
            </span>
            <button className="rounded-lg p-2 hover:bg-slate-100 transition" aria-label="Help">
              <HelpCircle className="h-5 w-5 text-slate-600" />
            </button>
          </div>
        </div>

        {/* Mobile Navigation Tabs */}
        <div className="flex md:hidden overflow-x-auto border-t border-slate-200 px-2 py-2 gap-1 bg-slate-50">
          {navTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  isActive ? 'bg-blue-600 text-white' : 'bg-white text-slate-700 border border-slate-200'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
