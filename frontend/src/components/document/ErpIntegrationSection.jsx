import { useEffect, useState } from 'react';
import { Server, Globe, FileCode, Play, Loader2, Info, Download } from 'lucide-react';
import { syncErpApi, fetchSystemStatusApi } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { saveBlob } from '../../utils/download';

export default function ErpIntegrationSection() {
  const toast = useToast();
  const [erpConfig, setErpConfig] = useState(null);
  const [customEndpoint, setCustomEndpoint] = useState('');
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState('');

  useEffect(() => {
    fetchSystemStatusApi()
      .then((s) => setErpConfig(s.erp))
      .catch(() => setErpConfig(null));
  }, []);

  async function run(kind) {
    setRunning(kind);
    setResult(null);
    try {
      const payload = kind === 'tally' ? { erp_type: 'tally' } : { erp_type: 'custom', custom_endpoint: customEndpoint.trim() };
      const res = await syncErpApi('latest', payload);
      setResult({ kind, ...res });
      if (res.status === 'Synced') toast.success(res.message);
      else toast.warning(res.message, { duration: 10000 });
    } catch (err) {
      setResult({ kind, status: 'Failed', message: err.message });
      toast.error(err.message);
    } finally {
      setRunning('');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">ERP & Tally</h1>
        <p className="text-sm text-slate-500">Send the most recently processed invoice to Tally or your own ERP API.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="tally-title">
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5 text-indigo-600" aria-hidden="true" />
            <h2 id="tally-title" className="font-semibold text-slate-900">Tally Prime / ERP 9</h2>
          </div>
          <p className="mt-2 text-sm text-slate-600">
            Posts a purchase voucher to Tally's XML server. If Tally is not reachable, the voucher XML is generated so you can import it manually.
          </p>
          <dl className="mt-4 space-y-1 rounded-lg bg-slate-50 p-3 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-slate-500">Tally endpoint</dt>
              <dd className="truncate font-mono text-slate-800">{erpConfig?.tally_url || '—'}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-slate-500">Company</dt>
              <dd className="truncate text-slate-800">{erpConfig?.tally_company || 'Currently open company'}</dd>
            </div>
          </dl>
          <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Requires Tally running with the XML/ODBC server enabled, and the vendor, purchase and GST ledgers created. The endpoint is set by your administrator (PERMITTED_TALLY_URL).
          </p>
          <button
            type="button"
            onClick={() => run('tally')}
            disabled={Boolean(running)}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {running === 'tally' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Send latest invoice to Tally
          </button>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="custom-title">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-blue-600" aria-hidden="true" />
            <h2 id="custom-title" className="font-semibold text-slate-900">Custom ERP (REST API)</h2>
          </div>
          <p className="mt-2 text-sm text-slate-600">
            POSTs the invoice as JSON to an HTTPS endpoint you provide (SAP, Zoho, Odoo or an in-house system via its API or middleware).
          </p>
          <label htmlFor="custom-endpoint" className="mb-1 mt-4 block text-xs font-medium text-slate-700">
            Endpoint URL {erpConfig?.custom_erp_configured && <span className="text-slate-400">(leave empty to use the configured one)</span>}
          </label>
          <input
            id="custom-endpoint"
            type="url"
            placeholder="https://erp.example.com/api/invoices"
            value={customEndpoint}
            onChange={(e) => setCustomEndpoint(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
          <p className="mt-2 text-xs text-slate-500">
            Only public HTTPS endpoints are allowed. The API key (CUSTOM_ERP_API_KEY) is only sent to the configured endpoint.
          </p>
          <button
            type="button"
            onClick={() => run('custom')}
            disabled={Boolean(running) || (!customEndpoint.trim() && !erpConfig?.custom_erp_configured)}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {running === 'custom' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Send latest invoice
          </button>
        </section>
      </div>

      {result && (
        <section
          className={`rounded-2xl border p-5 text-sm ${
            result.status === 'Synced'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
              : result.status === 'XML Generated'
              ? 'border-violet-200 bg-violet-50 text-violet-900'
              : 'border-rose-200 bg-rose-50 text-rose-900'
          }`}
          aria-live="polite"
        >
          <p className="font-semibold">Result: {result.status}</p>
          <p className="mt-1">{result.message}</p>
          {result.tally_xml && (
            <div className="mt-3">
              <div className="mb-1 flex items-center justify-between">
                <p className="flex items-center gap-1 text-xs font-semibold">
                  <FileCode className="h-4 w-4" /> Voucher XML
                </p>
                <button
                  type="button"
                  onClick={() => saveBlob(new Blob([result.tally_xml], { type: 'application/xml' }), 'tally_voucher.xml')}
                  className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                >
                  <Download className="h-3.5 w-3.5" /> Download
                </button>
              </div>
              <pre className="max-h-56 overflow-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] text-emerald-300">{result.tally_xml}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
