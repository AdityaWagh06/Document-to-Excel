import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { Download, FileSpreadsheet, FileText, Code, Save, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';
import STR from '../../constants/strings';
import ValidationWarningsBanner from './ValidationWarningsBanner';
import { downloadExportApi } from '../../services/api';

export default function DataGridSection({
  rowData,
  columnDefs,
  handleGridChange,
  handleDownload,
  documentState,
  isSaving = false,
  hasUnsavedChanges = false,
  saveSuccess = false,
  saveError = '',
  handleSaveChanges,
}) {
  async function exportFormat(format) {
    // If there are unsaved changes, prompt save or notify
    const docId = documentState?.id || 'latest';
    try {
      const blob = await downloadExportApi(docId, format);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const ext = format === 'tally' ? 'xml' : format === 'doc' ? 'txt' : format;
      anchor.download = `extracted_invoice_${docId}.${ext}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  }

  return (
    <div className="rounded-2xl bg-white shadow-sm border border-slate-100 overflow-hidden flex-1 flex flex-col p-6">
      {/* Validation Warnings */}
      <ValidationWarningsBanner
        warnings={documentState?.validation_warnings || []}
        status={documentState?.status || 'Pending Verification'}
      />

      {/* Grid Toolbar & Persistence Status Bar */}
      <div className="border-b border-slate-100 bg-slate-50 px-4 py-3 rounded-xl mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h4 className="font-semibold text-slate-900 text-sm">{STR.extractedDataTitle}</h4>
          <p className="text-xs text-slate-600 mt-0.5">{STR.extractedDataSubtitle}</p>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          {/* Save Status Indicators */}
          {isSaving && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-100 text-blue-700 animate-pulse">
              <RefreshCw className="h-3 w-3 animate-spin" /> Saving changes...
            </span>
          )}

          {!isSaving && hasUnsavedChanges && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping"></span>
              Unsaved Changes
            </span>
          )}

          {!isSaving && !hasUnsavedChanges && saveSuccess && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-100 text-emerald-800">
              <CheckCircle className="h-3.5 w-3.5" /> All changes saved
            </span>
          )}

          {/* Explicit Save Changes Button */}
          {handleSaveChanges && (
            <button
              onClick={handleSaveChanges}
              disabled={isSaving || !hasUnsavedChanges || !documentState?.id}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition shadow-xs ${
                hasUnsavedChanges && documentState?.id
                  ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer hover:shadow-md'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
              title={
                !documentState?.id
                  ? 'Upload or select an invoice first'
                  : hasUnsavedChanges
                  ? 'Save corrections to server'
                  : 'No changes to save'
              }
            >
              <Save className="h-3.5 w-3.5" /> Save Changes
            </button>
          )}

          <div className="text-xs font-mono bg-slate-200/70 text-slate-700 px-2.5 py-1 rounded-md font-semibold">
            GSTIN: {documentState?.gstin || 'N/A'}
          </div>
        </div>
      </div>

      {/* Save Error & Retry Banner */}
      {saveError && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3.5 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-rose-800 font-medium">
            <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0" />
            <span>
              <strong>Save failed:</strong> {saveError} (Your edits are kept in the grid)
            </span>
          </div>
          {handleSaveChanges && (
            <button
              onClick={handleSaveChanges}
              className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded shadow-xs transition"
            >
              Retry Save
            </button>
          )}
        </div>
      )}

      {/* AG-Grid React */}
      <div className="ag-theme-quartz flex-1 overflow-hidden min-h-[250px]">
        <AgGridReact
          rowData={rowData}
          columnDefs={columnDefs}
          defaultColDef={{ resizable: true, sortable: true, filter: false }}
          onCellValueChanged={handleGridChange}
          animateRows
          domLayout="autoHeight"
        />
      </div>

      {/* Multi-Format Export Bar */}
      <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap gap-2">
        <button
          onClick={() => exportFormat('excel')}
          className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 text-xs font-bold transition shadow-sm"
        >
          <FileSpreadsheet className="h-4 w-4" /> Download Excel (.xlsx)
        </button>

        <button
          onClick={() => exportFormat('csv')}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 text-xs font-bold transition shadow-sm"
        >
          <Download className="h-4 w-4" /> CSV
        </button>

        <button
          onClick={() => exportFormat('doc')}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-700 hover:bg-slate-800 text-white px-3 py-2 text-xs font-bold transition shadow-sm"
        >
          <FileText className="h-4 w-4" /> DOC Summary
        </button>

        <button
          onClick={() => exportFormat('tally')}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white px-3 py-2 text-xs font-bold transition shadow-sm"
        >
          <Code className="h-4 w-4" /> Tally XML
        </button>
      </div>
    </div>
  );
}
