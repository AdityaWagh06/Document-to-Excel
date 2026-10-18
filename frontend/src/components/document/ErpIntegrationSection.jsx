import { useState } from 'react';
import { RefreshCw, CheckCircle2, Server, Globe, FileCode, Play } from 'lucide-react';
import { syncErpApi } from '../../services/api';

export default function ErpIntegrationSection() {
  const [tallyUrl, setTallyUrl] = useState('http://localhost:9000');
  const [customEndpoint, setCustomEndpoint] = useState('https://api.mycustomerp.com/v1/invoices');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  async function handleTestTallySync() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await syncErpApi('latest', { erp_type: 'tally', tally_url: tallyUrl });
      setTestResult({ success: true, message: res.message, xml: res.tally_xml });
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setTesting(false);
    }
  }

  async function handleTestCustomErp() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await syncErpApi('latest', { erp_type: 'custom', custom_endpoint: customEndpoint });
      setTestResult({ success: true, message: res.message });
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl">
            <RefreshCw className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900">ERP & Accounting Software Connectors</h3>
            <p className="text-xs text-slate-500">
              Integrate extracted invoice data automatically with Tally Solutions (Prime / ERP 9) and Custom ERP systems.
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          {/* Tally Connector Box */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="h-5 w-5 text-indigo-600" />
                <h4 className="font-bold text-slate-900 text-sm">Tally Solutions Connector</h4>
              </div>
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[11px] font-bold rounded-full">Active</span>
            </div>
            <p className="text-xs text-slate-600 mt-2">
              Exports Tally XML Vouchers (Purchase entries, Sales entries, Ledger posting & Stock item updates).
            </p>

            <div className="mt-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Local Tally HTTP Endpoint</label>
              <input
                type="text"
                value={tallyUrl}
                onChange={(e) => setTallyUrl(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white font-mono"
              />
            </div>

            <button
              onClick={handleTestTallySync}
              disabled={testing}
              className="mt-4 flex items-center justify-center gap-2 w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition shadow-sm"
            >
              <Play className="h-3.5 w-3.5" /> {testing ? 'Testing Tally XML...' : 'Generate & Test Tally Sync'}
            </button>
          </div>

          {/* Custom ERP API Connector Box */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-600" />
                <h4 className="font-bold text-slate-900 text-sm">Custom ERP Webhook API</h4>
              </div>
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[11px] font-bold rounded-full">REST API</span>
            </div>
            <p className="text-xs text-slate-600 mt-2">
              Pushes full JSON voucher payloads to your company's custom ERP, SAP, or QuickBooks REST endpoint.
            </p>

            <div className="mt-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Custom ERP Endpoint URL</label>
              <input
                type="text"
                value={customEndpoint}
                onChange={(e) => setCustomEndpoint(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white font-mono"
              />
            </div>

            <button
              onClick={handleTestCustomErp}
              disabled={testing}
              className="mt-4 flex items-center justify-center gap-2 w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition shadow-sm"
            >
              <Play className="h-3.5 w-3.5" /> {testing ? 'Pushing Payload...' : 'Test Custom ERP Endpoint'}
            </button>
          </div>
        </div>

        {/* Test Output Console */}
        {testResult && (
          <div className={`mt-6 rounded-xl p-4 border text-xs ${testResult.success ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-rose-50 border-rose-200 text-rose-900'}`}>
            <div className="flex items-center gap-2 font-bold mb-2">
              <CheckCircle2 className="h-4 w-4" />
              ERP Connector Execution Result
            </div>
            <p>{testResult.message}</p>
            {testResult.xml && (
              <div className="mt-3">
                <p className="font-bold mb-1 flex items-center gap-1">
                  <FileCode className="h-4 w-4" /> Preview Tally XML Voucher:
                </p>
                <pre className="bg-slate-900 text-emerald-400 p-3 rounded-lg overflow-x-auto text-[11px] font-mono max-h-48">
                  {testResult.xml}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
