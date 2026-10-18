import { useState, useRef } from 'react';
import { uploadDocumentApi, updateDocumentApi, downloadExportApi } from '../services/api';
import { buildTableRows, rowsToPayload } from '../utils/gridHelpers';
import STR from '../constants/strings';

export function useDocumentProcessor() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const [rawText, setRawText] = useState('');
  const [documentState, setDocumentState] = useState({
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
  });
  const [rowData, setRowData] = useState([]);
  const [processedCount, setProcessedCount] = useState(0);

  // Persistence States
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState('');

  const isSavingRef = useRef(false);
  const saveSeqRef = useRef(0);

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

    setIsProcessing(true);
    resetError();
    setSaveError('');
    setSaveSuccess(false);

    try {
      const data = await uploadDocumentApi(selectedFile);

      const canonicalDoc = {
        ...data,
        id: data.id || '',
        vendor: data.vendor || '',
        gstin: data.gstin || '',
        invoice_number: data.invoice_number || '',
        date: data.date || '',
        due_date: data.due_date || '',
        subtotal: data.subtotal || '0.00',
        cgst: data.cgst || '0.00',
        sgst: data.sgst || '0.00',
        igst: data.igst || '0.00',
        tax_total: data.tax_total || '0.00',
        total: data.total || '',
        confidence: data.confidence ?? 0,
        ocr_confidence: data.ocr_confidence ?? 0,
        items: data.items || [],
        status: data.status || 'Pending Verification',
        validation_warnings: data.validation_warnings || [],
      };

      setDocumentState(canonicalDoc);
      setRowData(buildTableRows(canonicalDoc));
      setRawText(data.raw_text || '');
      setProcessedCount((prev) => prev + 1);
      setHasUnsavedChanges(false);
    } catch (uploadError) {
      setError(uploadError.message || STR.genericProcessError);
    } finally {
      setIsProcessing(false);
    }
  }

  function handleGridChange(params) {
    const nextRows = [];
    params.api.forEachNode((node) => {
      nextRows.push({ ...node.data });
    });
    setRowData(nextRows);
    setDocumentState((current) => {
      const updated = rowsToPayload(nextRows, current);
      return updated;
    });
    setHasUnsavedChanges(true);
    setSaveError('');
    setSaveSuccess(false);
  }

  async function handleSaveChanges() {
    const docId = documentState?.id;
    if (!docId) {
      setSaveError('Cannot save: No active document ID found. Please upload or select an invoice first.');
      return;
    }

    if (isSavingRef.current) {
      return;
    }

    isSavingRef.current = true;
    setIsSaving(true);
    setSaveError('');
    setSaveSuccess(false);
    const currentSeq = ++saveSeqRef.current;

    try {
      const payload = {
        vendor: documentState.vendor || '',
        gstin: documentState.gstin || '',
        invoice_number: documentState.invoice_number || '',
        date: documentState.date || '',
        due_date: documentState.due_date || '',
        subtotal: documentState.subtotal || '0.00',
        cgst: documentState.cgst || '0.00',
        sgst: documentState.sgst || '0.00',
        igst: documentState.igst || '0.00',
        tax_total: documentState.tax_total || '0.00',
        total: documentState.total || '0.00',
        items: (documentState.items || []).map((it) => ({
          description: String(it.description || ''),
          hsn_sac: String(it.hsn_sac || ''),
          qty: String(it.qty || '1'),
          unit_price: String(it.unit_price || '0.00'),
          tax_rate: String(it.tax_rate || '0%'),
          tax_amount: String(it.tax_amount || '0.00'),
          amount: String(it.amount || '0.00'),
        })),
      };

      const savedDoc = await updateDocumentApi(docId, payload);

      if (currentSeq === saveSeqRef.current) {
        setDocumentState(savedDoc);
        setRowData(buildTableRows(savedDoc));
        setHasUnsavedChanges(false);
        setSaveSuccess(true);
      }
    } catch (saveErr) {
      if (currentSeq === saveSeqRef.current) {
        setSaveError(saveErr.message || 'Failed to persist changes to the server.');
      }
    } finally {
      if (currentSeq === saveSeqRef.current) {
        isSavingRef.current = false;
        setIsSaving(false);
      }
    }
  }

  function loadDocument(doc) {
    if (!doc) return;
    setDocumentState({ ...doc });
    setRowData(buildTableRows(doc));
    setRawText(doc.raw_text || '');
    setHasUnsavedChanges(false);
    setSaveSuccess(false);
    setSaveError('');
    setSelectedFile(null);
  }

  async function handleDownload(format = 'excel') {
    setError('');
    const docId = documentState?.id || 'latest';
    try {
      const blob = await downloadExportApi(docId, format);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const ext = format === 'tally' ? 'xml' : format === 'doc' ? 'txt' : format;
      anchor.download = `extracted_invoice.${ext}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError.message || STR.couldNotDownload);
    }
  }

  return {
    selectedFile,
    setSelectedFile,
    isDragging,
    setIsDragging,
    isProcessing,
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
    loadDocument,
    resetError,
  };
}
