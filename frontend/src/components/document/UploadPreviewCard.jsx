import { Upload, Zap, AlertCircle, FileText, Image as ImageIcon } from 'lucide-react';
import STR from '../../constants/strings';

export default function UploadPreviewCard({
  selectedFile,
  previewUrl,
  isDragging,
  isProcessing,
  error,
  handleFiles,
  handleUpload,
  fileInputRef,
  setIsDragging,
}) {
  const isPdf =
    selectedFile?.type === 'application/pdf' ||
    selectedFile?.name?.toLowerCase().endsWith('.pdf');

  const isImage =
    selectedFile?.type?.startsWith('image/') ||
    /\.(png|jpe?g|webp)$/i.test(selectedFile?.name || '');

  return (
    <div className="mb-6 rounded-2xl bg-white shadow-sm border border-slate-100">
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
          handleFiles(e.dataTransfer.files);
        }}
        className={`p-8 rounded-2xl border-2 border-dashed transition cursor-pointer ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-slate-200 bg-slate-50 hover:border-slate-300'
        }`}
      >
        <div className="text-center">
          <Upload
            className={`h-12 w-12 mx-auto mb-4 ${
              isDragging ? 'text-blue-600' : 'text-slate-400'
            }`}
          />
          <h3 className="text-lg font-semibold text-slate-900">{STR.uploadTitle}</h3>
          <p className="mt-1 text-sm text-slate-600">{STR.uploadSubtitle}</p>
          <p className="mt-1 text-xs text-slate-500">{STR.uploadSupport}</p>

          {selectedFile && (
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg shadow-xs text-xs font-medium text-slate-700">
              {isPdf ? (
                <FileText className="h-4 w-4 text-rose-500" />
              ) : (
                <ImageIcon className="h-4 w-4 text-blue-500" />
              )}
              <span className="font-semibold text-slate-800">{selectedFile.name}</span>
              <span className="text-slate-400">
                ({(selectedFile.size / 1024).toFixed(1)} KB)
              </span>
            </div>
          )}

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
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp,application/pdf"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mx-4 mb-4 mt-4 rounded-xl border border-red-200 bg-red-50 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-red-900">{STR.errorTitle}</p>
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* Preview Section */}
      <div className="p-4 border-t border-slate-100">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-slate-900">{STR.previewSectionTitle}</h4>
          {selectedFile && (
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
              {isPdf ? 'PDF Invoice' : isImage ? 'Image Invoice' : 'Document'}
            </span>
          )}
        </div>

        {previewUrl && isPdf ? (
          <div className="w-full rounded-lg shadow-sm border border-slate-200 overflow-hidden bg-slate-100 h-96">
            <iframe
              src={previewUrl}
              title="PDF Invoice Preview"
              className="w-full h-full border-0"
            />
          </div>
        ) : previewUrl && isImage ? (
          <div className="w-full rounded-lg shadow-sm border border-slate-100 overflow-hidden bg-slate-50 p-2 flex items-center justify-center">
            <img
              src={previewUrl}
              alt="Invoice Preview"
              className="w-full rounded shadow-xs max-h-96 object-contain"
            />
          </div>
        ) : selectedFile ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-6 text-center">
            <p className="text-sm font-medium text-amber-800">
              Preview not available for this file type.
            </p>
            <p className="text-xs text-amber-600 mt-1">{selectedFile.name}</p>
          </div>
        ) : (
          <div className="rounded-lg bg-slate-100 h-48 flex items-center justify-center">
            <p className="text-sm text-slate-500">{STR.previewPlaceholder}</p>
          </div>
        )}
      </div>
    </div>
  );
}
