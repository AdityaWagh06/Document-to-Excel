import { useState, useRef } from 'react';
import { uploadDocumentApi, updateDocumentApi } from '../services/api';
import { buildTableRows, rowsToPayload } from '../utils/gridHelpers';
import { downloadDocumentExport } from '../utils/download';
import STR from '../constants/strings';

const ALLOWED = /\.(pdf|png|jpe?g|webp)$/i;
const MAX_BYTES = 16 * 1024 * 1024;

const EMPTY_DOC = {
  id: '',
  vendor: '',
  gstin: '',
  invoice_number: '',
  date: '',
  due_date: '',
  subtotal: '0.00',
  cgst: '0.00',
  sgst: '0.00',
  igst: '0.00',
  tax_total: '0.00',
  total: '',
  confidence: 0,
  ocr_confidence: 0,
  items: [],
  status: 'Pending Verification',
  validation_warnings: [],
};

function toCanonical(data) {
  return {
    ...EMPTY_DOC,
    ...data,
    items: data?.items || [],
    validation_warnings: data?.validation_warnings || [],
    confidence: data?.confidence ?? 0,
    ocr_confidence: data?.ocr_confidence ?? 0,
  };
}

function buildSavePayload(doc, extra = {}) {
  return {
    vendor: doc.vendor || '',
    gstin: doc.gstin || '',
    invoice_number: doc.invoice_number || '',
    date: doc.date || '',
    due_date: doc.due_date || '',
    subtotal: doc.subtotal || '0.00',
    cgst: doc.cgst || '0.00',
    sgst: doc.sgst || '0.00',
    igst: doc.igst || '0.00',
    tax_total: doc.tax_total || '0.00',
    total: doc.total || '0.00',
    items: (doc.items || []).map((it) => ({
      description: String(it.description || ''),
      hsn_sac: String(it.hsn_sac || ''),
      qty: String(it.qty || '1'),
      unit_price: String(it.unit_price || '0.00'),
      tax_rate: String(it.tax_rate || '0%'),
      tax_amount: String(it.tax_amount || '0.00'),
      amount: String(it.amount || '0.00'),
    })),
    ...extra,
  };
}

/**
 * phase: 'idle' | 'uploading' | 'processing' | 'done' | 'error'
 */
export function useDocumentProcessor(toast) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [phase, setPhase] = useState('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');
  const [rawText, setRawText] = useState('');
  const [documentState, setDocumentState] = useState(EMPTY_DOC);
  const [rowData, setRowData] = useState([]);
  const [processedCount, setProcessedCount] = useState(0);

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState('');

  const isSavingRef = useRef(false);
  const saveSeqRef = useRef(0);

  const isProcessing = phase === 'uploading' || phase === 'processing';

  function resetError() {
    setError('');
  }

  function handleFiles(files) {
    const nextFile = files && files[0];
    if (!nextFile) return;
    if (!ALLOWED.test(nextFile.name)) {
      setError('Unsupported file type. Upload a PDF, PNG, JPG or WEBP file.');
      return;
    }
    if (nextFile.size > MAX_BYTES) {
      setError('File is larger than 16 MB. Compress it or split the PDF and try again.');
      return;
    }
    setSelectedFile(nextFile);
    setPhase('idle');
    resetError();
  }

  function applyDocument(doc) {
    const canonical = toCanonical(doc);
    setDocumentState(canonical);
    setRowData(buildTableRows(canonical));
    setRawText(canonical.raw_text || '');
    setHasUnsavedChanges(false);
    return canonical;
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError(STR.chooseImagePrompt);
      return;
    }

    setPhase('uploading');
    setUploadProgress(0);
    resetError();
    setSaveError('');
    setSaveSuccess(false);

    try {
      const data = await uploadDocumentApi(selectedFile, (pct) => {
        setUploadProgress(pct);
        if (pct >= 100) setPhase('processing');
      });
      const doc = applyDocument(data);
      setProcessedCount((prev) => prev + 1);
      setPhase('done');
      const errors = (doc.validation_warnings || []).filter((w) => w.type === 'error').length;
      if (errors > 0) {
        toast?.warning(`Extracted with ${errors} issue${errors > 1 ? 's' : ''} to review.`, { title: 'Review needed' });
      } else {
        toast?.success('Invoice extracted. Review the fields, then mark it as verified.', { title: 'Extraction complete' });
      }
    } catch (uploadError) {
      setPhase('error');
      setError(uploadError.message || STR.genericProcessError);
    }
  }

  function handleGridChange(params) {
    const nextRows = [];
    params.api.forEachNode((node) => {
      nextRows.push({ ...node.data });
    });
    setRowData(nextRows);
    setDocumentState((current) => rowsToPayload(nextRows, current));
    setHasUnsavedChanges(true);
    setSaveError('');
    setSaveSuccess(false);
  }

  async function persist(extra = {}, successMessage = 'Changes saved and re-validated.') {
    const docId = documentState?.id;
    if (!docId) {
      setSaveError('Upload or open an invoice first.');
      return null;
    }
    if (isSavingRef.current) return null;

    isSavingRef.current = true;
    setIsSaving(true);
    setSaveError('');
    setSaveSuccess(false);
    const currentSeq = ++saveSeqRef.current;

    try {
      const savedDoc = await updateDocumentApi(docId, buildSavePayload(documentState, extra));
      if (currentSeq === saveSeqRef.current) {
        applyDocument(savedDoc);
        setSaveSuccess(true);
        if (extra.status === 'Verified' && savedDoc.status !== 'Verified') {
          toast?.warning('Saved, but the invoice still has errors so it cannot be marked as verified.');
        } else {
          toast?.success(successMessage);
        }
      }
      return savedDoc;
    } catch (saveErr) {
      if (currentSeq === saveSeqRef.current) {
        setSaveError(saveErr.message || 'Failed to save changes to the server.');
        toast?.error(saveErr.message || 'Failed to save changes.');
      }
      return null;
    } finally {
      if (currentSeq === saveSeqRef.current) {
        isSavingRef.current = false;
        setIsSaving(false);
      }
    }
  }

  const handleSaveChanges = () => persist();
  const handleVerify = () => persist({ status: 'Verified' }, 'Invoice marked as verified.');

  function loadDocument(doc) {
    if (!doc) return;
    applyDocument(doc);
    setSaveSuccess(false);
    setSaveError('');
    setSelectedFile(null);
    setPhase('done');
  }

  async function handleDownload(format = 'excel') {
    if (hasUnsavedChanges) {
      toast?.warning('You have unsaved edits. Save first so the export includes them.');
      return;
    }
    try {
      await downloadDocumentExport(documentState, format);
    } catch (downloadError) {
      toast?.error(downloadError.message || STR.couldNotDownload);
    }
  }

  return {
    selectedFile,
    setSelectedFile,
    isDragging,
    setIsDragging,
    isProcessing,
    phase,
    uploadProgress,
    error,
    setError,
    rawText,
    documentState,
    rowData,
    processedCount,
    isSaving,
    hasUnsavedChanges,
    saveSuccess,
    saveError,
    handleFiles,
    handleUpload,
    handleDownload,
    handleGridChange,
    handleSaveChanges,
    handleVerify,
    loadDocument,
    resetError,
  };
}
