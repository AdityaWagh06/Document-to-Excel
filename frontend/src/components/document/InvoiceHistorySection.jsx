import { useState, useEffect } from 'react';
import { History, Download, RefreshCw, FileText, CheckCircle2, AlertTriangle, Trash2, Search } from 'lucide-react';
import { fetchDocumentsApi, downloadExportApi, syncErpApi, deleteDocumentApi } from '../../services/api';

export default function InvoiceHistorySection({ onSelectDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [syncingId, setSyncingId] = useState(null);

  async function loadHistory() {
    setLoading(true);
    setError('');
    try {
      const docs = await fetchDocumentsApi();
      setDocuments(docs || []);
    } catch (err) {
      setError(err.message || 'Failed to load document history');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function handleExport(docId, format) {
    try {
      const blob = await downloadExportApi(docId, format);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const ext = format === 'tally' ? 'xml' : format === 'doc' ? 'txt' : format;
      anchor.download = `invoice_${docId}_export.${ext}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  }

  async function handleSyncTally(docId) {
    setSyncingId(docId);
    try {
      const res = await syncErpApi(docId, { erp_type: 'tally' });
      alert(res.message);
      loadHistory();
    } catch (err) {
      alert(`ERP Sync failed: ${err.message}`);
    } finally {
      setSyncingId(null);
    }
  }

  async function handleDelete(docId) {
    if (!window.confirm('Are you sure you want to delete this invoice record?')) return;
    try {
      await deleteDocumentApi(docId);
      loadHistory();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      (doc.vendor || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.invoice_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.gstin || '').toLowerCase().includes(searchQuery.toLowerCase());

    if (statusFilter === 'ALL') return matchesSearch;
    return matchesSearch && doc.status === statusFilter;
  });

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <History className="h-6 w-6 text-blue-600" />
            Invoice History & Verification Dashboard
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Review, verify, export, or sync extracted invoices directly to Tally or ERP.
          </p>
        </div>
        <button
          onClick={loadHistory}
          className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search vendor, GSTIN, invoice #..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-slate-600">Filter Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-2 bg-white font-semibold text-slate-700"
          >
            <option value="ALL">All Invoices ({documents.length})</option>
            <option value="Pending Verification">Pending Verification</option>
            <option value="Verified">Verified</option>
            <option value="Flagged Error">Flagged Error</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-12 text-center text-sm text-slate-500">Loading invoice history...</div>
      ) : error ? (
        <div className="py-8 text-center text-sm text-rose-600">{error}</div>
      ) : filteredDocs.length === 0 ? (
        <div className="py-12 text-center text-sm text-slate-500">
          No invoice documents found. Upload invoices in the Scanner tab to get started.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-700 font-bold">
                <th className="py-3 px-3">Date</th>
                <th className="py-3 px-3">Vendor Name</th>
                <th className="py-3 px-3">GSTIN</th>
                <th className="py-3 px-3">Invoice #</th>
                <th className="py-3 px-3 text-right">Total (₹)</th>
                <th className="py-3 px-3 text-center">Status</th>
                <th className="py-3 px-3 text-center">ERP Sync</th>
                <th className="py-3 px-3 text-right">Actions / Export</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredDocs.map((doc) => (
                <tr key={doc.id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3 text-slate-600 whitespace-nowrap">{doc.date || '—'}</td>
                  <td className="py-3 px-3 font-semibold text-slate-900">{doc.vendor || 'Unknown'}</td>
                  <td className="py-3 px-3 text-slate-600 font-mono">{doc.gstin || 'N/A'}</td>
                  <td className="py-3 px-3 text-slate-800 font-mono">{doc.invoice_number || 'N/A'}</td>
                  <td className="py-3 px-3 text-right font-bold text-slate-900">₹ {doc.total || '0.00'}</td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                        doc.status === 'Verified'
                          ? 'bg-emerald-100 text-emerald-800'
                          : doc.status === 'Flagged Error'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {doc.status === 'Verified' ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                      {doc.status}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        doc.erp_sync_status?.includes('Synced')
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {doc.erp_sync_status || 'Not Synced'}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      {onSelectDocument && (
                        <button
                          onClick={() => onSelectDocument(doc)}
                          title="Open & Edit in Grid"
                          className="px-2 py-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-semibold border border-indigo-200 transition"
                        >
                          Edit
                        </button>
                      )}
                      {/* Export Dropdown */}
                      <button
                        onClick={() => handleExport(doc.id, 'excel')}
                        title="Download Excel (.xlsx)"
                        className="px-2 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded text-xs font-semibold border border-emerald-200"
                      >
                        Excel
                      </button>
                      <button
                        onClick={() => handleExport(doc.id, 'csv')}
                        title="Download CSV"
                        className="px-2 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-xs font-semibold border border-blue-200"
                      >
                        CSV
                      </button>
                      <button
                        onClick={() => handleExport(doc.id, 'tally')}
                        title="Download Tally XML Voucher"
                        className="px-2 py-1 bg-purple-50 text-purple-700 hover:bg-purple-100 rounded text-xs font-semibold border border-purple-200"
                      >
                        Tally XML
                      </button>

                      {/* Sync to Tally button */}
                      <button
                        onClick={() => handleSyncTally(doc.id)}
                        disabled={syncingId === doc.id}
                        title="Sync to Tally / ERP"
                        className="p-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${syncingId === doc.id ? 'animate-spin' : ''}`} />
                      </button>

                      <button
                        onClick={() => handleDelete(doc.id)}
                        title="Delete record"
                        className="p-1 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
