import { Building2, CalendarDays, Hash, Receipt, ShieldCheck, Gauge } from 'lucide-react';
import { formatMoney, toNumber } from '../../utils/money';
import { StatusBadge, MethodBadge } from '../common/StatusBadge';

const nonZero = (v) => {
  const n = toNumber(v);
  return !Number.isNaN(n) && n !== 0;
};

function Field({ icon: Icon, label, value }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-400">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {label}
      </dt>
      <dd className="mt-1 truncate text-sm font-semibold text-slate-900" title={value || ''}>
        {value || <span className="font-normal text-slate-400">Not found</span>}
      </dd>
    </div>
  );
}

function ScoreChip({ label, value }) {
  const pct = Math.round((value || 0) * 100);
  const tone = pct >= 80 ? 'text-emerald-700 bg-emerald-50 ring-emerald-200' : pct >= 60 ? 'text-amber-700 bg-amber-50 ring-amber-200' : 'text-rose-700 bg-rose-50 ring-rose-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}>
      <Gauge className="h-3 w-3" aria-hidden="true" />
      {label} {pct}%
    </span>
  );
}

/** Read-only, document-style view of the extracted invoice: who, when, what, how much. */
export default function InvoiceSummary({ doc }) {
  const currency = (doc.currency || '').toUpperCase();
  const money = (v) => formatMoney(v, currency);
  const items = doc.items || [];
  const gstRows = [
    ['CGST', doc.cgst],
    ['SGST', doc.sgst],
    ['IGST', doc.igst],
  ].filter(([, v]) => nonZero(v));
  const gstSum = gstRows.reduce((sum, [, v]) => sum + toNumber(v), 0);
  const otherTax = nonZero(doc.tax_total) && Math.abs(toNumber(doc.tax_total) - gstSum) > 0.009 ? toNumber(doc.tax_total) - gstSum : 0;

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-label="Extracted invoice">
      <header className="relative overflow-hidden bg-ink-950 px-5 py-5 text-white sm:px-6">
        <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-indigo-500/30 blur-3xl" aria-hidden="true" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-200">Bill from</p>
            <h2 className="mt-1 truncate text-xl font-semibold tracking-tight sm:text-2xl" title={doc.vendor}>
              {doc.vendor || 'Unknown vendor'}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={doc.status} />
              <MethodBadge method={doc.extraction_method} model={doc.ai_model} />
            </div>
          </div>
          <div className="text-right">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-200">Total</p>
            <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{money(doc.total)}</p>
            <p className="mt-1 text-xs text-slate-300">
              {currency ? `Amounts in ${currency}, as printed` : 'Currency not detected: set it below'}
            </p>
          </div>
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-4 border-b border-slate-100 px-5 py-4 sm:grid-cols-4 sm:px-6">
        <Field icon={Hash} label="Invoice / bill #" value={doc.invoice_number} />
        <Field icon={CalendarDays} label="Date" value={doc.date} />
        <Field icon={CalendarDays} label="Due date" value={doc.due_date} />
        <Field icon={ShieldCheck} label={currency && currency !== 'INR' ? 'Tax ID' : 'GSTIN'} value={doc.gstin} />
      </dl>

      <div className="px-5 py-4 sm:px-6">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            <Receipt className="h-4 w-4 text-slate-400" aria-hidden="true" /> Line items
          </h3>
          <span className="text-xs text-slate-500">{items.length} item{items.length === 1 ? '' : 's'}</span>
        </div>
        {items.length === 0 ? (
          <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-sm text-slate-500">No line items were found on this document.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="py-2 pr-3 font-medium">Description</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-right font-medium">Rate</th>
                  <th className="py-2 pl-3 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item, idx) => (
                  <tr key={idx}>
                    <td className="max-w-[260px] py-2 pr-3 text-slate-800">
                      <span className="block truncate" title={item.description}>{item.description || `Item ${idx + 1}`}</span>
                      {item.hsn_sac && <span className="text-xs text-slate-400">HSN/SAC {item.hsn_sac}</span>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">{item.qty || '1'}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                      {nonZero(item.unit_price) ? money(item.unit_price) : '—'}
                    </td>
                    <td className="py-2 pl-3 text-right font-medium tabular-nums text-slate-900">{money(item.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4 border-t border-slate-100 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-6">
        <div className="flex flex-wrap gap-2">
          <ScoreChip label="Extraction" value={doc.confidence} />
          {doc.ocr_confidence > 0 && <ScoreChip label="Text read" value={doc.ocr_confidence} />}
          {doc.source && doc.source !== 'Manual Upload' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
              <Building2 className="h-3 w-3" aria-hidden="true" /> {doc.source}
            </span>
          )}
        </div>
        <dl className="w-full space-y-1.5 text-sm sm:w-72">
          {nonZero(doc.subtotal) && (
            <div className="flex justify-between text-slate-600"><dt>Subtotal</dt><dd className="tabular-nums">{money(doc.subtotal)}</dd></div>
          )}
          {gstRows.map(([label, v]) => (
            <div key={label} className="flex justify-between text-slate-600"><dt>{label}</dt><dd className="tabular-nums">{money(v)}</dd></div>
          ))}
          {gstRows.length === 0 && nonZero(doc.tax_total) && (
            <div className="flex justify-between text-slate-600"><dt>Tax</dt><dd className="tabular-nums">{money(doc.tax_total)}</dd></div>
          )}
          {gstRows.length > 0 && otherTax > 0 && (
            <div className="flex justify-between text-slate-600"><dt>Other tax</dt><dd className="tabular-nums">{money(otherTax)}</dd></div>
          )}
          {nonZero(doc.other_charges) && (
            <div className="flex justify-between text-slate-600"><dt>Tip / other charges</dt><dd className="tabular-nums">{money(doc.other_charges)}</dd></div>
          )}
          {nonZero(doc.discount) && (
            <div className="flex justify-between text-emerald-700"><dt>Discount</dt><dd className="tabular-nums">−{money(doc.discount)}</dd></div>
          )}
          <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold text-slate-900">
            <dt>Total{currency ? ` (${currency})` : ''}</dt>
            <dd className="tabular-nums">{money(doc.total)}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}
