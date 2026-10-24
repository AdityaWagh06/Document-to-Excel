export function SummaryCard({ label, value, icon }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <span className="text-slate-400" aria-hidden="true">{icon}</span>
      </div>
      <p className="mt-1.5 truncate text-base font-semibold text-slate-900" title={typeof value === 'string' ? value : undefined}>
        {value}
      </p>
    </div>
  );
}

export function StatCard({ label, value, hint, icon, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    blue: 'bg-blue-100 text-blue-700',
    emerald: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    rose: 'bg-rose-100 text-rose-700',
    violet: 'bg-violet-100 text-violet-700',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-1 truncate text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
          {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
        </div>
        {icon && <div className={`rounded-lg p-2 ${tones[tone]}`} aria-hidden="true">{icon}</div>}
      </div>
    </div>
  );
}

export function MetricCard({ label, value, color }) {
  const styles = {
    green: { bar: 'bg-emerald-500', text: 'text-emerald-700', label: 'High' },
    yellow: { bar: 'bg-amber-500', text: 'text-amber-700', label: 'Medium' },
    red: { bar: 'bg-rose-500', text: 'text-rose-700', label: 'Low' },
  };
  const s = styles[color] || styles.red;
  const pct = parseInt(value, 10) || 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <span className={`text-xs font-semibold ${s.text}`}>{s.label}</span>
      </div>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
      <div className="mt-2 h-1.5 w-full rounded-full bg-slate-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={`h-1.5 rounded-full ${s.bar}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
}
