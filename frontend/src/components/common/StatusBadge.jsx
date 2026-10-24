import { CheckCircle2, AlertTriangle, Clock, XCircle, FileCode, CircleDashed } from 'lucide-react';

const PROVIDER_LABELS = { openai: 'OpenAI', gemini: 'Gemini', groq: 'Groq', openrouter: 'OpenRouter' };

const METHOD_LABELS = { ai: 'AI', 'ai-image': 'AI + image', 'ai-vision': 'AI vision' };

const STATUS = {
  Verified: { cls: 'bg-emerald-100 text-emerald-800 ring-emerald-200', icon: CheckCircle2 },
  'Pending Verification': { cls: 'bg-amber-100 text-amber-800 ring-amber-200', icon: Clock },
  'Flagged Error': { cls: 'bg-rose-100 text-rose-800 ring-rose-200', icon: AlertTriangle },
};

const ERP = {
  Synced: { cls: 'bg-blue-100 text-blue-800 ring-blue-200', icon: CheckCircle2, label: 'Synced' },
  'XML Generated': { cls: 'bg-violet-100 text-violet-800 ring-violet-200', icon: FileCode, label: 'XML generated' },
  // Legacy value written by older versions when Tally was offline
  'Synced (XML Generated)': { cls: 'bg-violet-100 text-violet-800 ring-violet-200', icon: FileCode, label: 'XML generated' },
  Failed: { cls: 'bg-rose-100 text-rose-800 ring-rose-200', icon: XCircle, label: 'Failed' },
  'Not Synced': { cls: 'bg-slate-100 text-slate-600 ring-slate-200', icon: CircleDashed, label: 'Not synced' },
};

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS['Pending Verification'];
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${s.cls}`}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {status || 'Pending Verification'}
    </span>
  );
}

export function ErpBadge({ status }) {
  const s = ERP[status] || ERP['Not Synced'];
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {s.label}
    </span>
  );
}

export function MethodBadge({ method, model }) {
  if (!method) return null;
  const isAi = method.startsWith('ai');
  const provider = method.split(':')[1] || '';
  const label = isAi
    ? `${METHOD_LABELS[method.split(':')[0]] || 'AI'} · ${PROVIDER_LABELS[provider] || provider}${model ? ` ${model}` : ''}`
    : 'Rule-based parser';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        isAi ? 'bg-indigo-50 text-indigo-700 ring-indigo-200' : 'bg-slate-100 text-slate-700 ring-slate-200'
      }`}
      title={isAi ? 'Fields extracted by the configured AI model' : 'Fields extracted by local pattern matching (no AI)'}
    >
      {label}
    </span>
  );
}
