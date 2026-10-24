import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { FileSpreadsheet, FileText, Code, Save, Loader2, CheckCircle, AlertTriangle, BadgeCheck, Download } from 'lucide-react';
import STR from '../../constants/strings';
import ValidationWarningsBanner from './ValidationWarningsBanner';

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
  handleVerify,
}) {
  const hasDoc = Boolean(documentState?.id);
  const hasErrors = (documentState?.validation_warnings || []).some((w) => w.type === 'error');
  const isVerified = documentState?.status === 'Verified';

  if (!hasDoc) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <FileSpreadsheet className="h-10 w-10 text-slate-300" aria-hidden="true" />
        <h3 className="mt-3 text-base font-semibold text-slate-900">No invoice loaded</h3>
        <p className="mt-1 max-w-sm text-sm text-slate-500">
          Upload an invoice on the left, or open one from Invoice History, to review and edit the extracted fields here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <ValidationWarningsBanner warnings={documentState.validation_warnings || []} />

      <div className="mb-4 flex flex-col justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center">
        <div>
          <h4 className="text-sm font-semibold text-slate-900">{STR.extractedDataTitle}</h4>
          <p className="mt-0.5 text-xs text-slate-600">{STR.extractedDataSubtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isSaving && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…
            </span>
          )}
          {!isSaving && hasUnsavedChanges && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true" /> Unsaved changes
            </span>
          )}
          {!isSaving && !hasUnsavedChanges && saveSuccess && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
              <CheckCircle className="h-3.5 w-3.5" /> Saved
            </span>
          )}

          <button
            type="button"
            onClick={handleSaveChanges}
            disabled={isSaving || !hasUnsavedChanges}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            <Save className="h-3.5 w-3.5" /> Save changes
          </button>
          <button
            type="button"
            onClick={handleVerify}
            disabled={isSaving || isVerified || hasErrors}
            title={
              hasErrors
                ? 'Fix the errors listed above before verifying'
                : isVerified
                ? 'Already verified'
                : 'Confirm that all fields are correct'
            }
            className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
          >
            <BadgeCheck className="h-3.5 w-3.5" /> {isVerified ? 'Verified' : 'Mark as verified'}
          </button>
        </div>
      </div>

      {saveError && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs" role="alert">
          <div className="flex items-center gap-2 font-medium text-rose-800">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
            <span>
              <strong>Save failed:</strong> {saveError} Your edits are kept in the table.
            </span>
          </div>
          <button
            type="button"
            onClick={handleSaveChanges}
            className="shrink-0 rounded bg-rose-600 px-2.5 py-1 font-semibold text-white hover:bg-rose-700"
          >
            Retry
          </button>
        </div>
      )}

      <div className="ag-theme-quartz min-h-[250px] w-full overflow-x-auto">
        <AgGridReact
          rowData={rowData}
          columnDefs={columnDefs}
          defaultColDef={{ resizable: true, sortable: false, filter: false }}
          onCellValueChanged={handleGridChange}
          singleClickEdit
          stopEditingWhenCellsLoseFocus
          domLayout="autoHeight"
        />
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <Download className="h-3.5 w-3.5" /> Export
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleDownload('excel')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
          >
            <FileSpreadsheet className="h-4 w-4" /> Excel (.xlsx)
          </button>
          <button
            type="button"
            onClick={() => handleDownload('csv')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <FileText className="h-4 w-4" /> CSV
          </button>
          <button
            type="button"
            onClick={() => handleDownload('doc')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <FileText className="h-4 w-4" /> Text summary
          </button>
          <button
            type="button"
            onClick={() => handleDownload('tally')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Code className="h-4 w-4" /> Tally XML
          </button>
        </div>
      </div>
    </div>
  );
}
