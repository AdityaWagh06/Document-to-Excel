import STR from '../../constants/strings';

export function Feature({ icon, label, desc }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex-shrink-0 mt-1 p-2 bg-blue-100 rounded-lg text-blue-600">
        {icon}
      </div>
      <div>
        <p className="font-semibold text-slate-900">{label}</p>
        <p className="text-sm text-slate-600">{desc}</p>
      </div>
    </div>
  );
}

export function SummaryCard({ label, value, icon }) {
  return (
    <div className="rounded-2xl bg-white shadow-sm border border-slate-100 p-6 hover:shadow-md transition">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600">{label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-900 truncate">{value}</p>
        </div>
        <div className="p-3 bg-blue-100 rounded-lg text-blue-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

export function MetricCard({ label, value, color }) {
  const colorClasses = {
    green: 'border-green-200 bg-green-50',
    yellow: 'border-yellow-200 bg-yellow-50',
    red: 'border-red-200 bg-red-50'
  };
  const textClasses = {
    green: 'text-green-900',
    yellow: 'text-yellow-900',
    red: 'text-red-900'
  };
  const badgeClasses = {
    green: 'bg-green-200 text-green-800',
    yellow: 'bg-yellow-200 text-yellow-800',
    red: 'bg-red-200 text-red-800'
  };

  return (
    <div className={`rounded-2xl border p-4 ${colorClasses[color]}`}>
      <p className={`text-sm font-medium ${textClasses[color]}`}>{label}</p>
      <div className="mt-3 flex items-center justify-between">
        <p className={`text-3xl font-bold ${textClasses[color]}`}>{value}</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeClasses[color]}`}>
          {color === 'green' ? STR.excellentBadge : color === 'yellow' ? STR.goodBadge : STR.lowBadge}
        </span>
      </div>
    </div>
  );
}

export function FooterStat({ label, value }) {
  return (
    <div className="text-center">
      <p className="text-sm font-medium text-white/80">{label}</p>
      <p className="text-3xl font-bold mt-2 text-white">{value}</p>
    </div>
  );
}
