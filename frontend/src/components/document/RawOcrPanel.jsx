import STR from '../../constants/strings';

export default function RawOcrPanel({ rawText }) {
  return (
    <div className="rounded-2xl bg-white shadow-sm border border-slate-100 overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50 px-6 py-4 flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-slate-900">{STR.rawOCRTitle}</h4>
          <p className="text-xs text-slate-600 mt-1">{STR.rawOCRSubtitle}</p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
          {STR.debugBadge}
        </span>
      </div>
      <pre className="p-6 text-xs leading-relaxed text-slate-600 overflow-auto max-h-64 font-mono bg-slate-50 border-t border-slate-100">
        {rawText || STR.noDataYet}
      </pre>
    </div>
  );
}
