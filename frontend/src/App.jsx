import { useEffect, useMemo, useRef, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { Upload, Download, Zap, CheckCircle, AlertCircle, Settings, HelpCircle } from 'lucide-react';
import STR from './strings';

function buildTableRows(payload) {
  const rows = [];
  rows.push({ id: 'vendor', section: STR.summarySection, field: STR.vendorLabel, value: payload?.vendor || '', confidence: payload?.confidence ?? 0 });
  rows.push({ id: 'date', section: STR.summarySection, field: STR.dateLabel, value: payload?.date || '', confidence: payload?.confidence ?? 0 });
  rows.push({ id: 'total', section: STR.summarySection, field: STR.totalLabel, value: payload?.total || '', confidence: payload?.confidence ?? 0 });
  rows.push({ id: 'ocr_confidence', section: STR.summarySection, field: STR.ocrConfidenceLabel, value: payload?.ocr_confidence?.toFixed ? payload.ocr_confidence.toFixed(3) : String(payload?.ocr_confidence ?? ''), confidence: payload?.ocr_confidence ?? 0 });

  (payload?.items || []).forEach((item, index) => {
    rows.push({
      id: `item-${index}`,
      section: STR.lineItemsSection,
      field: item?.description || `${STR.itemPrefix} ${index + 1}`,
      value: item?.amount || '',
      confidence: payload?.confidence ?? 0
    });
  });

  return rows;
}

function rowsToPayload(rows, basePayload) {
  const items = [];
  let vendor = '';
  let date = '';
  let total = '';

  rows.forEach((row) => {
    if (row.section === STR.summarySection && row.field === STR.vendorLabel) vendor = row.value;
    if (row.section === STR.summarySection && row.field === STR.dateLabel) date = row.value;
    if (row.section === STR.summarySection && row.field === STR.totalLabel) total = row.value;
    if (row.section === STR.lineItemsSection) {
      items.push({ description: row.field, amount: row.value });
    }
  });

  return {
    ...basePayload,
    vendor,
    date,
    total,
    items
  };
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const [rawText, setRawText] = useState('');
  const [documentState, setDocumentState] = useState({ vendor: '', date: '', total: '', confidence: 0, ocr_confidence: 0, items: [] });
  const [rowData, setRowData] = useState([]);
  const [processedCount, setProcessedCount] = useState(0);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl('');
      return undefined;
    }

    const nextUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [selectedFile]);

  useEffect(() => {
    setRowData(buildTableRows(documentState));
  }, [documentState]);

  const columnDefs = useMemo(() => [
    { field: 'section', headerName: STR.sectionColumn, editable: false, width: 150 },
    { field: 'field', headerName: STR.fieldColumn, editable: false, flex: 1 },
    { field: 'value', headerName: STR.valueColumn, editable: true, flex: 1.2 },
    { field: 'confidence', headerName: STR.confidenceColumn, editable: false, width: 140, valueFormatter: (params) => (typeof params.value === 'number' ? params.value.toFixed(3) : params.value) }
  ], []);

  function resetError() {
    setError('');
  }

  function handleFiles(files) {
    const nextFile = files && files[0];
    if (!nextFile) return;
    setSelectedFile(nextFile);
    resetError();
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError(STR.chooseImagePrompt);
      return;
    }

    const formData = new FormData();
    formData.append('image', selectedFile);

    setIsProcessing(true);
    resetError();

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || STR.uploadFailed);
      }

      setDocumentState({
        vendor: data.vendor || '',
        date: data.date || '',
        total: data.total || '',
        confidence: data.confidence ?? 0,
        ocr_confidence: data.ocr_confidence ?? 0,
        items: data.items || []
      });
      setRawText(data.raw_text || '');
      setProcessedCount(prev => prev + 1);
    } catch (uploadError) {
      setError(uploadError.message || STR.genericProcessError);
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleDownload() {
    setError('');
    try {
      const response = await fetch('/download');
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload?.error || STR.downloadFailed);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = STR.downloadFilename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError.message || STR.couldNotDownload);
    }
  }

  function handleGridChange(params) {
    const nextRows = [];
    params.api.forEachNode((node) => {
      nextRows.push(node.data);
    });
    setRowData(nextRows);
    setDocumentState((current) => rowsToPayload(nextRows, current));
  }

  const confidencePercent = Math.round((documentState.confidence || 0) * 100);
  const ocrConfidencePercent = Math.round((documentState.ocr_confidence || 0) * 100);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Navigation Bar */}
      <nav className="sticky top-0 z-50 border-b border-slate-200/60 bg-white/95 backdrop-blur-xl shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 shadow-lg">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">{STR.appName}</h1>
              <p className="text-xs text-slate-500">{STR.appTagline}</p>
            </div>
          </div>
          <div className="hidden flex-1 items-center justify-center gap-8 md:flex">
            <span className="text-sm font-medium text-slate-600">{STR.documentsProcessed}: <span className="text-blue-600 font-bold">{processedCount}</span></span>
          </div>
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 hover:bg-slate-100 transition">
              <HelpCircle className="h-5 w-5 text-slate-600" />
            </button>
            <button className="rounded-lg p-2 hover:bg-slate-100 transition">
              <Settings className="h-5 w-5 text-slate-600" />
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <div className="mb-8 rounded-2xl bg-white p-8 shadow-sm border border-slate-100">
          <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
            <div>
              <h2 className="text-3xl font-bold text-slate-900">{STR.heroTitle}</h2>
              <p className="mt-2 text-lg text-slate-600">{STR.heroSubtitle}</p>
              <div className="mt-6 grid gap-4 sm:grid-cols-3">
                <Feature icon={<Zap className="h-5 w-5" />} label={STR.feature1.label} desc={STR.feature1.desc} />
                <Feature icon={<CheckCircle className="h-5 w-5" />} label={STR.feature2.label} desc={STR.feature2.desc} />
                <Feature icon={<Download className="h-5 w-5" />} label={STR.feature3.label} desc={STR.feature3.desc} />
              </div>
            </div>
            <div className="flex items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-8 text-white shadow-lg">
              <div className="text-center">
                <Zap className="h-16 w-16 mx-auto mb-3" />
                <p className="text-sm font-medium">{STR.productionBadge}</p>
                <p className="text-2xl font-bold">{STR.appName}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-8 lg:grid-cols-[1.1fr_1.3fr]">
          {/* Left Column: Upload & Preview */}
          <section>
            {/* Upload Card */}
            <div className="mb-6 rounded-2xl bg-white shadow-sm border border-slate-100">
              <div
                onDragEnter={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={(e) => { e.preventDefault(); setIsDragging(false); handleFiles(e.dataTransfer.files); }}
                className={`p-8 rounded-2xl border-2 border-dashed transition cursor-pointer ${
                  isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                }`}
              >
                <div className="text-center">
                  <Upload className={`h-12 w-12 mx-auto mb-4 ${isDragging ? 'text-blue-600' : 'text-slate-400'}`} />
                  <h3 className="text-lg font-semibold text-slate-900">{STR.uploadTitle}</h3>
                  <p className="mt-1 text-sm text-slate-600">{STR.uploadSubtitle}</p>
                  <p className="mt-1 text-xs text-slate-500">{STR.uploadSupport}</p>
                  <div className="mt-6 flex flex-wrap gap-3 justify-center">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-6 py-3 font-medium hover:bg-slate-800 transition shadow-md"
                    >
                          <Upload className="h-4 w-4" /> {STR.chooseFile}
                    </button>
                    <button
                      onClick={handleUpload}
                      disabled={isProcessing || !selectedFile}
                      className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 font-medium hover:shadow-lg hover:scale-105 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Zap className="h-4 w-4" /> {isProcessing ? STR.processing : STR.extractData}
                    </button>
                  </div>
                  <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
                </div>
              </div>

              {/* Error Alert */}
              {error && (
                <div className="mx-4 mb-4 rounded-xl border border-red-200 bg-red-50 p-4 flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-red-900">{STR.errorTitle}</p>
                    <p className="text-sm text-red-800">{error}</p>
                  </div>
                </div>
              )}

              {/* Preview */}
              <div className="p-4 border-t border-slate-100">
                <h4 className="mb-3 text-sm font-semibold text-slate-900">{STR.previewSectionTitle}</h4>
                {previewUrl ? (
                  <img src={previewUrl} alt="preview" className="w-full rounded-lg shadow-md max-h-96 object-contain" />
                ) : (
                  <div className="rounded-lg bg-slate-100 h-48 flex items-center justify-center">
                    <p className="text-sm text-slate-500">{STR.previewPlaceholder}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Raw OCR Log */}
            <div className="rounded-2xl bg-white shadow-sm border border-slate-100 overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50 px-6 py-4 flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-slate-900">{STR.rawOCRTitle}</h4>
                  <p className="text-xs text-slate-600 mt-1">{STR.rawOCRSubtitle}</p>
                </div>
                <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">{STR.debugBadge}</span>
              </div>
              <pre className="p-6 text-xs leading-relaxed text-slate-600 overflow-auto max-h-64 font-mono bg-slate-50 border-t border-slate-100">
                {rawText || STR.noDataYet}
              </pre>
            </div>
          </section>

          {/* Right Column: Extracted Data & Grid */}
          <section className="flex flex-col gap-6">
            {/* Extraction Summary */}
            <div className="grid grid-cols-3 gap-4">
              <SummaryCard label={STR.vendorLabel} value={documentState.vendor || '—'} icon={<Zap className="h-5 w-5" />} />
              <SummaryCard label={STR.dateLabel} value={documentState.date || '—'} icon={<CheckCircle className="h-5 w-5" />} />
              <SummaryCard label={STR.totalLabel} value={documentState.total || '—'} icon={<Download className="h-5 w-5" />} />
            </div>

            {/* Confidence Metrics */}
            <div className="grid grid-cols-2 gap-4">
              <MetricCard label={STR.extractionConfidenceLabel} value={`${confidencePercent}%`} color={confidencePercent >= 80 ? 'green' : confidencePercent >= 60 ? 'yellow' : 'red'} />
              <MetricCard label={STR.ocrConfidenceLabel} value={`${ocrConfidencePercent}%`} color={ocrConfidencePercent >= 80 ? 'green' : ocrConfidencePercent >= 60 ? 'yellow' : 'red'} />
            </div>

            {/* AG Grid Table */}
            <div className="rounded-2xl bg-white shadow-sm border border-slate-100 overflow-hidden flex-1 flex flex-col">
              <div className="border-b border-slate-100 bg-slate-50 px-6 py-4">
                <h4 className="font-semibold text-slate-900">{STR.extractedDataTitle}</h4>
                <p className="text-xs text-slate-600 mt-1">{STR.extractedDataSubtitle}</p>
              </div>
              <div className="ag-theme-quartz flex-1 overflow-hidden">
                <AgGridReact
                  rowData={rowData}
                  columnDefs={columnDefs}
                  defaultColDef={{ resizable: true, sortable: true, filter: false }}
                  onCellValueChanged={handleGridChange}
                  animateRows
                  domLayout="autoHeight"
                />
              </div>
              <div className="border-t border-slate-100 bg-slate-50 p-4 flex gap-3">
                <button
                  onClick={handleDownload}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-green-600 to-emerald-600 text-white px-4 py-3 font-medium hover:shadow-lg hover:scale-105 transition"
                >
                  <Download className="h-4 w-4" /> {STR.downloadExcel}
                </button>
              </div>
            </div>
          </section>
        </div>

        {/* Footer Stats */}
        <div className="mt-12 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 p-8 text-white shadow-lg">
          <div className="grid gap-6 sm:grid-cols-4">
            <FooterStat label={STR.documentsProcessed} value={processedCount} />
            <FooterStat label={STR.itemsExtracted} value={(documentState.items || []).length} />
            <FooterStat label={STR.avgAccuracy} value={`${Math.round((confidencePercent + ocrConfidencePercent) / 2)}%`} />
            <FooterStat label={STR.processingSpeed} value={STR.processingSpeedValue} />
          </div>
        </div>
      </main>
    </div>
  );
}

function Feature({ icon, label, desc }) {
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

function SummaryCard({ label, value, icon }) {
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

function MetricCard({ label, value, color }) {
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

function FooterStat({ label, value }) {
  return (
    <div className="text-center">
      <p className="text-sm font-medium text-white/80">{label}</p>
      <p className="text-3xl font-bold mt-2 text-white">{value}</p>
    </div>
  );
}
