import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Receipt, Building2, CheckCircle2, RefreshCw } from 'lucide-react';
import { fetchAnalyticsApi } from '../../services/api';
import { formatMoney } from '../../utils/money';

export default function AnalyticsSection() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadAnalytics() {
    setLoading(true);
    try {
      const data = await fetchAnalyticsApi();
      setAnalytics(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalytics();
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-sm text-slate-500">Loading analytics…</div>;
  }

  if (!analytics) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
        Failed to load analytics data.{' '}
        <button type="button" onClick={loadAnalytics} className="font-semibold underline">Try again</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
              <BarChart3 className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Analytics & vendors</h1>
              <p className="text-xs text-slate-500">Financial insights, total spend, GST tax breakdowns, and vendor performance.</p>
            </div>
          </div>

          <button
            onClick={loadAnalytics}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 rounded-lg"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh Analytics
          </button>
        </div>

        {/* Analytics Cards */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-100 bg-gradient-to-br from-blue-50 to-indigo-50 p-4">
            <div className="flex items-center justify-between text-blue-700">
              <span className="text-xs font-bold uppercase tracking-wider">Total Spend</span>
              <TrendingUp className="h-5 w-5 text-blue-600" />
            </div>
            <p className="mt-2 text-2xl font-extrabold text-slate-900">{formatMoney(analytics.total_spend, analytics.currency)}</p>
            <p className="text-[11px] text-slate-500 mt-1">
              {(analytics.currency_totals || []).length > 1
                ? `Main currency only. Also: ${analytics.currency_totals.slice(1).map((c) => formatMoney(c.total_spend, c.currency)).join(', ')}`
                : `Across ${analytics.total_invoices} invoices`}
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-gradient-to-br from-emerald-50 to-teal-50 p-4">
            <div className="flex items-center justify-between text-emerald-700">
              <span className="text-xs font-bold uppercase tracking-wider">Tax amount</span>
              <Receipt className="h-5 w-5 text-emerald-600" />
            </div>
            <p className="mt-2 text-2xl font-extrabold text-slate-900">{formatMoney(analytics.total_tax, analytics.currency)}</p>
            <p className="text-[11px] text-slate-500 mt-1">{analytics.currency === 'INR' ? 'GST on processed invoices (potential ITC)' : 'Tax on processed invoices'}</p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-gradient-to-br from-purple-50 to-pink-50 p-4">
            <div className="flex items-center justify-between text-purple-700">
              <span className="text-xs font-bold uppercase tracking-wider">Verified Invoices</span>
              <CheckCircle2 className="h-5 w-5 text-purple-600" />
            </div>
            <p className="mt-2 text-2xl font-extrabold text-slate-900">{analytics.verified_count}</p>
            <p className="text-[11px] text-slate-500 mt-1">{analytics.pending_verification} pending audit</p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-gradient-to-br from-amber-50 to-orange-50 p-4">
            <div className="flex items-center justify-between text-amber-700">
              <span className="text-xs font-bold uppercase tracking-wider">Active Vendors</span>
              <Building2 className="h-5 w-5 text-amber-600" />
            </div>
            <p className="mt-2 text-2xl font-extrabold text-slate-900">{(analytics.vendors_summary || []).length}</p>
            <p className="text-[11px] text-slate-500 mt-1">Unique suppliers</p>
          </div>
        </div>

        {/* Vendors Summary Table */}
        <div className="mt-8">
          <h4 className="font-bold text-slate-900 text-sm mb-3">Top Vendors by Spend</h4>
          {(analytics.vendors_summary || []).length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-500">No vendor data recorded yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b text-slate-700 font-bold">
                    <th className="py-2.5 px-3">Vendor Name</th>
                    <th className="py-2.5 px-3 text-center">Invoice Count</th>
                    <th className="py-2.5 px-3 text-right">Total spend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {analytics.vendors_summary.map((v, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-semibold text-slate-900">{v.vendor}</td>
                      <td className="py-2.5 px-3 text-center text-slate-700">{v.count}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-slate-900">{formatMoney(v.total_spend, v.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
