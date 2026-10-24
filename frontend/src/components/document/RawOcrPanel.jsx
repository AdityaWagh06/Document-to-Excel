import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import STR from '../../constants/strings';

export default function RawOcrPanel({ rawText }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left hover:bg-slate-50"
      >
        <div>
          <h4 className="text-sm font-semibold text-slate-900">{STR.rawOCRTitle}</h4>
          <p className="mt-0.5 text-xs text-slate-500">{STR.rawOCRSubtitle}</p>
        </div>
        <ChevronDown className={`h-4 w-4 text-slate-500 transition ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open && (
        <pre className="max-h-72 overflow-auto border-t border-slate-100 bg-slate-50 p-5 font-mono text-xs leading-relaxed text-slate-600 whitespace-pre-wrap">
          {rawText || STR.noDataYet}
        </pre>
      )}
    </div>
  );
}
