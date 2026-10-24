import { Upload, Zap, AlertCircle, FileText, Image as ImageIcon, Camera, Loader2, CheckCircle2 } from 'lucide-react';
import STR from '../../constants/strings';

function ProcessingSteps({ phase, uploadProgress }) {
  const steps = [
    { key: 'uploading', label: phase === 'uploading' ? `Uploading ${uploadProgress}%` : 'Uploaded' },
    { key: 'processing', label: 'Reading text & extracting fields' },
    { key: 'done', label: 'Validated' },
  ];
  const order = { uploading: 0, processing: 1, done: 2 };
  const current = order[phase] ?? -1;

  return (
    <ol className="mt-5 space-y-2 text-left" aria-label="Processing progress">
      {steps.map((step, idx) => {
        const state = idx < current || phase === 'done' ? 'done' : idx === current ? 'active' : 'todo';
        return (
          <li key={step.key} className="flex items-center gap-2 text-sm">
            {state === 'done' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            ) : state === 'active' ? (
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" aria-hidden="true" />
            ) : (
              <span className="h-4 w-4 rounded-full border-2 border-slate-300" aria-hidden="true" />
            )}
            <span className={state === 'todo' ? 'text-slate-400' : 'text-slate-700'}>{step.label}</span>
          </li>
        );
      })}
      {phase === 'processing' && (
        <li className="pl-6 text-xs text-slate-500">
          Scanned or multi-page documents can take up to a minute.
        </li>
      )}
    </ol>
  );
}

export default function UploadPreviewCard({
  selectedFile,
  previewUrl,
  isDragging,
  isProcessing,
  phase,
  uploadProgress,
  error,
  handleFiles,
  handleUpload,
  fileInputRef,
  setIsDragging,
}) {
  const isPdf = selectedFile?.type === 'application/pdf' || selectedFile?.name?.toLowerCase().endsWith('.pdf');
  const isImage = selectedFile?.type?.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(selectedFile?.name || '');

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div
        onDragEnter={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (!isProcessing) handleFiles(e.dataTransfer.files);
        }}
        className={`m-4 rounded-xl border-2 border-dashed p-6 text-center transition sm:p-8 ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50'
        }`}
      >
        <Upload className={`mx-auto mb-3 h-10 w-10 ${isDragging ? 'text-blue-600' : 'text-slate-400'}`} aria-hidden="true" />
        <h3 className="text-base font-semibold text-slate-900">{STR.uploadTitle}</h3>
        <p className="mt-1 text-sm text-slate-600">{STR.uploadSubtitle}</p>
        <p className="mt-1 text-xs text-slate-500">{STR.uploadSupport}</p>

        {selectedFile && (
          <div className="mt-4 inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700">
            {isPdf ? <FileText className="h-4 w-4 shrink-0 text-rose-500" /> : <ImageIcon className="h-4 w-4 shrink-0 text-blue-500" />}
            <span className="truncate font-semibold text-slate-800">{selectedFile.name}</span>
            <span className="shrink-0 text-slate-400">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isProcessing}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
          >
            <Upload className="h-4 w-4" /> {STR.chooseFile}
          </button>
          <label
            className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50 sm:hidden ${
              isProcessing ? 'pointer-events-none opacity-50' : ''
            }`}
          >
            <Camera className="h-4 w-4" /> Take photo
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </label>
          <button
            type="button"
            onClick={handleUpload}
            disabled={isProcessing || !selectedFile}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {isProcessing ? STR.processing : STR.extractData}
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp,application/pdf"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = '';
          }}
        />

        {(isProcessing || phase === 'done') && selectedFile && (
          <div className="mx-auto max-w-xs">
            <ProcessingSteps phase={phase} uploadProgress={uploadProgress} />
          </div>
        )}
      </div>

      {error && (
        <div className="mx-4 mb-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4" role="alert">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
          <div>
            <p className="font-semibold text-rose-900">{STR.errorTitle}</p>
            <p className="text-sm text-rose-800">{error}</p>
          </div>
        </div>
      )}

      <div className="border-t border-slate-100 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">{STR.previewSectionTitle}</h4>
          {selectedFile && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              {isPdf ? 'PDF' : isImage ? 'Image' : 'Document'}
            </span>
          )}
        </div>

        {previewUrl && isPdf ? (
          <div className="h-96 w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
            <iframe src={previewUrl} title="PDF invoice preview" className="h-full w-full border-0" />
          </div>
        ) : previewUrl && isImage ? (
          <div className="flex w-full items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50 p-2">
            <img src={previewUrl} alt="Invoice preview" className="max-h-96 w-full rounded object-contain" />
          </div>
        ) : (
          <div className="flex h-40 items-center justify-center rounded-lg bg-slate-50 text-center">
            <p className="px-4 text-sm text-slate-500">{STR.previewPlaceholder}</p>
          </div>
        )}
      </div>
    </div>
  );
}
