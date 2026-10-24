import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Cpu,
  FileText,
  Layers,
  Loader2,
  RefreshCw,
  ScanText,
  Sparkles,
  Upload,
  MessageSquare,
} from 'lucide-react';
import { fetchAnalyticsApi, fetchDocumentsApi, fetchSystemStatusApi } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import { formatMoney, formatMoneyCompact } from '../../utils/money';

const AI_PROVIDER_LABELS = { openai: 'OpenAI', gemini: 'Google Gemini', groq: 'Groq', openrouter: 'OpenRouter' };
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  const [y, m] = String(ym).split('-');
  return `${MONTHS[Number(m) - 1] || m} ${String(y).slice(2)}`;
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

function initials(name) {
  return (
    String(name || '?')
      .replace(/[^A-Za-z0-9 ]/g, ' ')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join('') || '?'
  );
}

/* ---------- Spend trend: single-series area chart with hover tooltip ---------- */
function SpendTrend({ monthly, currency }) {
  const [hover, setHover] = useState(null);
  if (!monthly || monthly.length === 0) {
    return <p className="py-16 text-center text-sm text-slate-500">Your monthly spend appears here once invoices are processed.</p>;
  }
  const W = 600;
  const H = 200;
  const pad = { t: 12, b: 4 };
  const max = Math.max(...monthly.map((m) => m.total_spend), 1);
  const step = monthly.length > 1 ? W / (monthly.length - 1) : 0;
  const fewPoints = monthly.length < 3;
  const pts = monthly.map((m, i) => ({
    x: fewPoints ? ((i + 0.5) * W) / monthly.length : i * step,
    y: pad.t + (1 - m.total_spend / max) * (H - pad.t - pad.b),
    m,
  }));
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ');
  const area = `${line} L${pts[pts.length - 1].x},${H} L${pts[0].x},${H} Z`;
  const active = hover !== null ? pts[hover] : null;

  return (
    <div className="relative">
      <div className="relative h-52 overflow-hidden" onMouseLeave={() => setHover(null)}>
        {/* recessive grid */}
        {[0.25, 0.5, 0.75].map((g) => (
          <div key={g} className="absolute inset-x-0 border-t border-dashed border-slate-100" style={{ top: `${g * 100}%` }} aria-hidden="true" />
        ))}
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" role="img" aria-label={`Spend by month in ${currency || 'the main currency'}`}>
          <defs>
            <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
            </linearGradient>
          </defs>
          {fewPoints ? (
            pts.map((p) => (
              <rect key={p.m.month} x={p.x - 28} y={p.y} width="56" height={H - p.y} rx="4" fill="#6366f1" />
            ))
          ) : (
            <>
              <path d={area} fill="url(#spendFill)" />
              <path d={line} fill="none" stroke="#4f46e5" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
            </>
          )}
        </svg>
        {pts.map((p, i) => (
          <button
            key={p.m.month}
            type="button"
            className="absolute top-0 h-full -translate-x-1/2 focus:outline-none"
            style={{ left: `${(p.x / W) * 100}%`, width: `${Math.max(100 / pts.length, 6)}%` }}
            onMouseEnter={() => setHover(i)}
            onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}
            aria-label={`${monthLabel(p.m.month)}: ${formatMoney(p.m.total_spend, currency)}, ${p.m.count} invoices`}
          />
        ))}
        {active && (
          <>
            <div className="pointer-events-none absolute top-0 h-full border-l border-indigo-300" style={{ left: `${(active.x / W) * 100}%` }} aria-hidden="true" />
            <div
              className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-indigo-600 shadow"
              style={{ left: `${(active.x / W) * 100}%`, top: `${(active.y / H) * 100}%` }}
              aria-hidden="true"
            />
            <div
              className="pointer-events-none absolute top-1 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-ink-950 px-3 py-2 text-xs text-white shadow-lg"
              style={{ left: `${Math.min(88, Math.max(12, (active.x / W) * 100))}%` }}
            >
              <p className="font-semibold">{formatMoney(active.m.total_spend, currency)}</p>
              <p className="text-slate-300">
                {monthLabel(active.m.month)} · {active.m.count} invoice{active.m.count === 1 ? '' : 's'}
              </p>
            </div>
          </>
        )}
      </div>
      <div className={`mt-2 flex text-[11px] text-slate-400 ${fewPoints ? 'justify-around' : 'justify-between'}`}>
        {monthly.map((m) => (
          <span key={m.month}>{monthLabel(m.month)}</span>
        ))}
      </div>
    </div>
  );
}

/* ---------- Review pipeline: one stacked bar with labelled segments ---------- */
const PIPELINE = [
  { key: 'verified_count', label: 'Verified', color: 'bg-emerald-500', icon: CheckCircle2, text: 'text-emerald-700' },
  { key: 'pending_verification', label: 'Awaiting review', color: 'bg-amber-400', icon: Clock, text: 'text-amber-700' },
  { key: 'flagged_errors', label: 'Needs fixing', color: 'bg-rose-500', icon: AlertTriangle, text: 'text-rose-700' },
];

function Pipeline({ analytics }) {
  const total = analytics?.total_invoices || 0;
  return (
    <div>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-slate-100" role="img" aria-label="Invoices by review status">
        {total > 0 &&
          PIPELINE.map((s) => {
            const v = analytics?.[s.key] || 0;
            return v > 0 ? <div key={s.key} className={`${s.color} h-full`} style={{ width: `${(v / total) * 100}%` }} title={`${s.label}: ${v}`} /> : null;
          })}
      </div>
      <ul className="mt-4 space-y-3">
        {PIPELINE.map((s) => {
          const v = analytics?.[s.key] || 0;
          const Icon = s.icon;
          return (
            <li key={s.key} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-slate-600">
                <span className={`h-2.5 w-2.5 rounded-full ${s.color}`} aria-hidden="true" />
                <Icon className={`h-4 w-4 ${s.text}`} aria-hidden="true" />
                {s.label}
              </span>
              <span className="font-semibold tabular-nums text-slate-900">
                {v}
                <span className="ml-1.5 text-xs font-normal text-slate-400">{total ? Math.round((v / total) * 100) : 0}%</span>
              </span>
            </li>
          );
        })}
        <li className="flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
          <span className="flex items-center gap-2 text-slate-600">
            <RefreshCw className="h-4 w-4 text-indigo-600" aria-hidden="true" /> Synced to ERP
          </span>
          <span className="font-semibold tabular-nums text-slate-900">{analytics?.synced_erp || 0}</span>
        </li>
      </ul>
    </div>
  );
}

function TopVendors({ vendors, currency }) {
  const list = (vendors || []).filter((v) => v.currency === currency).slice(0, 5);
  if (list.length === 0) return <p className="py-6 text-center text-sm text-slate-500">No vendors yet.</p>;
  const max = Math.max(...list.map((v) => v.total_spend), 1);
  return (
    <ul className="space-y-3">
      {list.map((v) => (
        <li key={`${v.vendor}-${v.currency}`}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium text-slate-800" title={v.vendor}>{v.vendor}</span>
            <span className="shrink-0 tabular-nums text-slate-900">{formatMoney(v.total_spend, v.currency)}</span>
          </div>
          <div className="mt-1.5 h-1.5 rounded-full bg-slate-100">
            <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${Math.max(3, (v.total_spend / max) * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function KpiCard({ label, value, hint, icon: Icon, accent }) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:-translate-y-0.5 hover:shadow-lg">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className={`rounded-xl p-2 ${accent}`} aria-hidden="true">
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function SetupRow({ ok, icon: Icon, label, detail }) {
  return (
    <li className="flex items-start gap-3">
      <span className={`mt-0.5 rounded-lg p-1.5 ${ok ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`} aria-hidden="true">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-sm font-medium text-slate-800">
          {label}
          {ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-label="ready" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-label="needs setup" />}
        </p>
        <p className="break-words text-xs text-slate-500">{detail}</p>
      </div>
    </li>
  );
}

function Panel({ title, subtitle, action, children, className = '' }) {
  return (
    <section className={`min-w-0 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] sm:p-6 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function DashboardSection({ authUser, onOpenDocument, onGoToUpload, onGoToHistory }) {
  const [analytics, setAnalytics] = useState(null);
  const [recent, setRecent] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([fetchAnalyticsApi(), fetchDocumentsApi(), fetchSystemStatusApi()]).then(([a, d, s]) => {
      if (cancelled) return;
      if (a.status === 'fulfilled') setAnalytics(a.value);
      if (d.status === 'fulfilled') setRecent((d.value || []).slice(0, 6));
      if (s.status === 'fulfilled') setStatus(s.value);
      if (a.status === 'rejected' && d.status === 'rejected') setError(a.reason?.message || 'Could not load dashboard data.');
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const currency = analytics?.currency || '';
  const trend = useMemo(() => {
    const m = analytics?.monthly || [];
    if (m.length < 2) return null;
    const [prev, cur] = m.slice(-2);
    if (!prev.total_spend) return null;
    return ((cur.total_spend - prev.total_spend) / prev.total_spend) * 100;
  }, [analytics]);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading dashboard…
      </div>
    );
  }
  if (error) {
    return <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>;
  }

  const ai = status?.ai;
  const ocr = status?.ocr;
  const ocrReady = ocr?.paddleocr || ocr?.easyocr;
  const total = analytics?.total_invoices || 0;
  const otherCurrencies = (analytics?.currency_totals || []).filter((c) => c.currency !== currency);
  const needsAttention = (analytics?.pending_verification || 0) + (analytics?.flagged_errors || 0);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-ink-950 px-6 py-8 text-white shadow-glow sm:px-10 sm:py-10">
        <div className="hero-grid pointer-events-none absolute inset-0 opacity-40" aria-hidden="true" />
        <div className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-indigo-600/40 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-32 right-0 h-80 w-80 rounded-full bg-cyan-400/20 blur-3xl" aria-hidden="true" />

        <div className="relative grid gap-8 lg:grid-cols-[1.3fr_1fr] lg:items-end">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-indigo-100 ring-1 ring-inset ring-white/15">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {ai?.configured ? `AI extraction on · ${AI_PROVIDER_LABELS[ai.provider] || ai.provider}` : 'Rule-based extraction'}
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              {greeting()}
              {authUser ? `, ${authUser}` : ''}.
            </h1>
            <p className="mt-2 max-w-lg text-sm text-slate-300 sm:text-base">
              {total === 0
                ? 'Drop in your first invoice or receipt and we will turn it into clean, reviewable data.'
                : needsAttention > 0
                ? `${needsAttention} invoice${needsAttention === 1 ? '' : 's'} need${needsAttention === 1 ? 's' : ''} a quick review before export.`
                : 'Everything is reviewed. Nice work.'}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onGoToUpload}
                className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-ink-950 shadow-sm transition hover:bg-indigo-50"
              >
                <Upload className="h-4 w-4" /> Upload invoice
              </button>
              <button
                type="button"
                onClick={onGoToHistory}
                className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white ring-1 ring-inset ring-white/25 transition hover:bg-white/10"
              >
                Review invoices <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="rounded-2xl bg-white/[0.06] p-5 ring-1 ring-inset ring-white/10 backdrop-blur">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-indigo-200">Total spend{currency ? ` · ${currency}` : ''}</p>
            <p className="mt-2 text-4xl font-semibold tracking-tight tabular-nums">{formatMoneyCompact(analytics?.total_spend || 0, currency)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-300">
              <span>Tax {formatMoney(analytics?.total_tax || 0, currency)}</span>
              {trend !== null && (
                <span className={`inline-flex items-center gap-0.5 font-medium ${trend >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  <ArrowUpRight className={`h-3.5 w-3.5 ${trend < 0 ? 'rotate-90' : ''}`} aria-hidden="true" />
                  {Math.abs(trend).toFixed(0)}% vs last month
                </span>
              )}
            </div>
            {otherCurrencies.length > 0 && (
              <div className="mt-4 border-t border-white/10 pt-3">
                <p className="text-[11px] uppercase tracking-wider text-slate-400">Other currencies (not converted)</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {otherCurrencies.map((c) => (
                    <span key={c.currency || 'none'} className="rounded-lg bg-white/10 px-2.5 py-1 text-xs font-medium tabular-nums">
                      {c.currency ? formatMoney(c.total_spend, c.currency) : `${formatMoney(c.total_spend, '')} (no currency)`}
                      <span className="ml-1 text-slate-400">· {c.count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <KpiCard label="Invoices processed" value={total} hint={`${(analytics?.currency_totals || []).length || 0} currenc${(analytics?.currency_totals || []).length === 1 ? 'y' : 'ies'}`} icon={Layers} accent="bg-indigo-50 text-indigo-600" />
        <KpiCard label="Awaiting review" value={analytics?.pending_verification || 0} hint="Check, then mark as verified" icon={Clock} accent="bg-amber-50 text-amber-600" />
        <KpiCard label="Needs fixing" value={analytics?.flagged_errors || 0} hint="Missing or inconsistent fields" icon={AlertTriangle} accent="bg-rose-50 text-rose-600" />
        <KpiCard label="Verified" value={analytics?.verified_count || 0} hint={`${analytics?.synced_erp || 0} synced to ERP`} icon={CheckCircle2} accent="bg-emerald-50 text-emerald-600" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Panel
          className="lg:col-span-2"
          title="Spend trend"
          subtitle={currency ? `Monthly total in ${currency}. Other currencies are counted but not added in.` : 'Monthly total'}
        >
          <SpendTrend monthly={analytics?.monthly} currency={currency} />
        </Panel>
        <Panel title="Review pipeline" subtitle="Where your invoices are right now">
          <Pipeline analytics={analytics} />
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Panel
          className="lg:col-span-2"
          title="Recent invoices"
          subtitle="Amounts in each invoice's own currency"
          action={
            recent.length > 0 && (
              <button type="button" onClick={onGoToHistory} className="inline-flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline">
                View all <ArrowRight className="h-4 w-4" />
              </button>
            )
          }
        >
          {recent.length === 0 ? (
            <div className="py-12 text-center">
              <FileText className="mx-auto h-8 w-8 text-slate-300" aria-hidden="true" />
              <p className="mt-2 text-sm text-slate-500">No invoices yet. Upload your first invoice to get started.</p>
            </div>
          ) : (
            <ul className="-mx-2 divide-y divide-slate-100">
              {recent.map((doc) => (
                <li key={doc.id}>
                  <button
                    type="button"
                    onClick={() => onOpenDocument(doc)}
                    className="flex w-full items-center gap-3 rounded-xl px-2 py-3 text-left transition hover:bg-slate-50"
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-xs font-semibold text-white" aria-hidden="true">
                      {initials(doc.vendor)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-900">{doc.vendor || 'Unknown vendor'}</span>
                      <span className="block truncate text-xs text-slate-500">
                        {doc.invoice_number || 'No invoice #'} · {doc.date || (doc.created_at || '').slice(0, 10)}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
                      <span className="text-sm font-semibold tabular-nums text-slate-900">{formatMoney(doc.total, doc.currency)}</span>
                      <StatusBadge status={doc.status} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel title="Top vendors" subtitle={currency ? `By spend in ${currency}` : 'By spend'}>
            <TopVendors vendors={analytics?.vendors_summary} currency={currency} />
          </Panel>
          <Panel title="System setup" subtitle="Read from the server .env">
            {status ? (
              <ul className="space-y-3">
                <SetupRow
                  ok={ai?.configured}
                  icon={Cpu}
                  label={ai?.configured ? AI_PROVIDER_LABELS[ai.provider] || ai.provider : 'AI extraction off'}
                  detail={ai?.configured ? `Model ${ai.model}` : ai?.errors?.[0] || 'Add OPENAI_API_KEY or a free GEMINI_API_KEY for better accuracy.'}
                />
                <SetupRow
                  ok={ocrReady || ai?.vision_fallback}
                  icon={ScanText}
                  label={ocrReady ? 'Local OCR ready' : ocr?.initialized ? 'Local OCR not installed' : 'Local OCR loads on first use'}
                  detail={
                    ocrReady
                      ? [ocr.paddleocr && 'PaddleOCR', ocr.easyocr && 'EasyOCR'].filter(Boolean).join(' + ')
                      : ai?.vision_fallback
                      ? 'Photos are read by the AI model instead.'
                      : 'Digital PDFs still work. Photos need OCR or an AI key.'
                  }
                />
                <SetupRow
                  ok={status.whatsapp?.media_download_configured}
                  icon={MessageSquare}
                  label="WhatsApp intake"
                  detail={status.whatsapp?.media_download_configured ? 'Cloud API connected.' : 'Optional. Needs a Meta WhatsApp Business account.'}
                />
              </ul>
            ) : (
              <p className="text-sm text-slate-500">Status unavailable.</p>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
