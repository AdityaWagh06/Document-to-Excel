import { AlertTriangle, CheckCircle2, AlertCircle, Info } from 'lucide-react';

export default function ValidationWarningsBanner({ warnings = [], status = 'Pending Verification' }) {
  if (!warnings || warnings.length === 0) {
    return (
      <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50/80 p-4 text-emerald-900 shadow-sm flex items-start gap-3">
        <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-emerald-900">AI Validation Engine Audit: All Checks Passed</h4>
          <p className="text-xs text-emerald-700 mt-0.5">
            GSTIN format, tax calculation math (Subtotal + Tax = Total), item totals, and duplicate invoice checks verified.
          </p>
        </div>
      </div>
    );
  }

  const errors = warnings.filter((w) => w.type === 'error');
  const warningList = warnings.filter((w) => w.type === 'warning');
  const infoList = warnings.filter((w) => w.type === 'info');

  return (
    <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/90 p-4 shadow-sm">
      <div className="flex items-center justify-between border-b border-amber-200/70 pb-2 mb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600" />
          <h4 className="text-sm font-bold text-amber-900">
            AI Validation Engine Audit ({warnings.length} Flagged Item{warnings.length > 1 ? 's' : ''})
          </h4>
        </div>
        <span
          className={`px-2.5 py-0.5 text-xs font-bold rounded-full ${
            status === 'Flagged Error'
              ? 'bg-rose-100 text-rose-800 border border-rose-300'
              : 'bg-amber-100 text-amber-800 border border-amber-300'
          }`}
        >
          {status}
        </span>
      </div>

      <div className="space-y-2">
        {errors.map((err, idx) => (
          <div key={`err-${idx}`} className="flex items-start gap-2 text-xs text-rose-800 bg-rose-50 border border-rose-200 p-2 rounded-lg">
            <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-rose-900">[{err.code}]</span> {err.message}
            </div>
          </div>
        ))}

        {warningList.map((w, idx) => (
          <div key={`warn-${idx}`} className="flex items-start gap-2 text-xs text-amber-800 bg-amber-100/60 border border-amber-200 p-2 rounded-lg">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-amber-900">[{w.code}]</span> {w.message}
            </div>
          </div>
        ))}

        {infoList.map((info, idx) => (
          <div key={`info-${idx}`} className="flex items-start gap-2 text-xs text-blue-800 bg-blue-50 border border-blue-200 p-2 rounded-lg">
            <Info className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-blue-900">[{info.code}]</span> {info.message}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
