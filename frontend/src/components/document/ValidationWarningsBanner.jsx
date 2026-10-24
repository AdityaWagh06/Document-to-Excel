import { AlertTriangle, CheckCircle2, AlertCircle, Info } from 'lucide-react';

const GROUPS = [
  { type: 'error', icon: AlertCircle, cls: 'border-rose-200 bg-rose-50 text-rose-900', iconCls: 'text-rose-600' },
  { type: 'warning', icon: AlertTriangle, cls: 'border-amber-200 bg-amber-50 text-amber-900', iconCls: 'text-amber-600' },
  { type: 'info', icon: Info, cls: 'border-blue-200 bg-blue-50 text-blue-900', iconCls: 'text-blue-600' },
];

export default function ValidationWarningsBanner({ warnings = [] }) {
  if (!warnings || warnings.length === 0) {
    return (
      <div className="mb-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-emerald-900">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
        <div>
          <h4 className="text-sm font-semibold">All validation checks passed</h4>
          <p className="mt-0.5 text-xs text-emerald-800">
            Required fields, GSTIN format and check digit, GST totals, line-item maths and duplicates were checked.
          </p>
        </div>
      </div>
    );
  }

  const errors = warnings.filter((w) => w.type === 'error').length;

  return (
    <div className="mb-4 space-y-2" aria-label="Validation results">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Validation · {warnings.length} item{warnings.length > 1 ? 's' : ''}
        {errors > 0 ? ` · ${errors} must be fixed` : ''}
      </p>
      {GROUPS.map((group) =>
        warnings
          .filter((w) => w.type === group.type)
          .map((w, idx) => {
            const Icon = group.icon;
            return (
              <div key={`${group.type}-${idx}`} className={`flex items-start gap-2 rounded-lg border p-2.5 text-xs ${group.cls}`}>
                <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${group.iconCls}`} aria-hidden="true" />
                <p>{w.message}</p>
              </div>
            );
          })
      )}
    </div>
  );
}
