import { useState, useEffect, useMemo } from 'react';
import { RefreshCw, Trash2, Search, Loader2, FileSpreadsheet, Code, Send, FileText, Pencil } from 'lucide-react';
import { fetchDocumentsApi, syncErpApi, deleteDocumentApi } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import ConfirmDialog from '../common/ConfirmDialog';
import { StatusBadge, ErpBadge } from '../common/StatusBadge';
import { downloadDocumentExport } from '../../utils/download';
import { formatMoney } from '../../utils/money';

export default function InvoiceHistorySection({ onSelectDocument }) {
  const toast = useToast();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [syncingId, setSyncingId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  async function loadHistory() {
    setLoading(true);
    setError('');
    try {
      const docs = await fetchDocumentsApi();
      setDocuments(docs || []);
    } catch (err) {
      setError(err.message || 'Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function handleExport(doc, format) {
    try {
      await downloadDocumentExport(doc, format);
    } catch (err) {
      toast.error(`Export failed: ${err.message}`);
    }
  }

  async function handleSyncTally(doc) {
    setSyncingId(doc.id);
    try {
      const res = await syncErpApi(doc.id, { erp_type: 'tally' });
      if (res.status === 'Synced') toast.success(res.message, { title: 'Synced to Tally' });
      else toast.warning(res.message, { title: 'Tally XML generated', duration: 10000 });
      loadHistory();
    } catch (err) {
      toast.error(err.message, { title: 'Tally sync failed' });
    } finally {
      setSyncingId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteDocumentApi(pendingDelete.id);
      toast.success('Invoice deleted.');
      setPendingDelete(null);
      loadHistory();
    } catch (err) {
      toast.error(`Delete failed: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  }

  const counts = useMemo(() => {
    const c = { ALL: documents.length, 'Pending Verification': 0, Verified: 0, 'Flagged Error': 0 };
    documents.forEach((d) => {
      if (c[d.status] !== undefined) c[d.status] += 1;
    });
    return c;
  }, [documents]);

  const q = searchQuery.trim().toLowerCase();
  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      !q ||
      [doc.vendor, doc.invoice_number, doc.gstin, doc.source].some((v) => String(v || '').toLowerCase().includes(q));
    return matchesSearch && (statusFilter === 'ALL' || doc.status === statusFilter);
  });

  const filters = [
    ['ALL', 'All'],
    ['Pending Verification', 'To review'],
    ['Flagged Error', 'Errors'],
    ['Verified', 'Verified'],
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col justify-between gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Invoices</h1>
          <p className="text-sm text-slate-500">Review, export or sync processed invoices.</p>
        </div>
        <button
          type="button"
          onClick={loadHistory}
          className="inline-flex items-center gap-2 self-start rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="flex flex-col gap-3 p-5 pb-0 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search vendor, GSTIN, invoice #…"
            aria-label="Search invoices"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
        </div>
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Filter by status">
          {filters.map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={statusFilter === value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                statusFilter === value ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {label} <span className="opacity-60">{counts[value]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="p-5">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading invoices…
          </div>
        ) : error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-12 text-center">
            <FileText className="mx-auto h-8 w-8 text-slate-300" aria-hidden="true" />
            <p className="mt-2 text-sm text-slate-500">
              {documents.length === 0 ? 'No invoices yet. Upload one from “Scan & review”.' : 'No invoices match your filters.'}
            </p>
          </div>
        ) : (
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-y border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-5 py-2.5">Date</th>
                  <th scope="col" className="px-3 py-2.5">Vendor</th>
                  <th scope="col" className="px-3 py-2.5">Invoice #</th>
                  <th scope="col" className="px-3 py-2.5 text-right">Total</th>
                  <th scope="col" className="px-3 py-2.5">Status</th>
                  <th scope="col" className="px-3 py-2.5">ERP</th>
                  <th scope="col" className="px-5 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/70">
                    <td className="whitespace-nowrap px-5 py-3 text-slate-600">{doc.date || (doc.created_at || '').slice(0, 10) || '—'}</td>
                    <td className="max-w-[220px] px-3 py-3">
                      <p className="truncate font-medium text-slate-900">{doc.vendor || 'Unknown vendor'}</p>
                      <p className="truncate font-mono text-xs text-slate-500">{doc.gstin || 'No GSTIN'}</p>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-700">{doc.invoice_number || '—'}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-right font-semibold text-slate-900">{formatMoney(doc.total, doc.currency)}</td>
                    <td className="px-3 py-3"><StatusBadge status={doc.status} /></td>
                    <td className="px-3 py-3"><ErpBadge status={doc.erp_sync_status} /></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {onSelectDocument && (
                          <button
                            type="button"
                            onClick={() => onSelectDocument(doc)}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Review
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleExport(doc, 'excel')}
                          title="Download Excel"
                          aria-label={`Download Excel for ${doc.invoice_number || doc.vendor || 'invoice'}`}
                          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <FileSpreadsheet className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleExport(doc, 'tally')}
                          title="Download Tally XML"
                          aria-label="Download Tally XML"
                          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Code className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSyncTally(doc)}
                          disabled={syncingId === doc.id}
                          title="Send to Tally"
                          aria-label="Send to Tally"
                          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                        >
                          {syncingId === doc.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPendingDelete(doc)}
                          title="Delete"
                          aria-label="Delete invoice"
                          className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 className="h-4 w-4" />
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

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        destructive
        busy={deleting}
        title="Delete this invoice?"
        message={`${pendingDelete?.vendor || 'This invoice'}${pendingDelete?.invoice_number ? ` (#${pendingDelete.invoice_number})` : ''} and its extracted data will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete invoice"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
