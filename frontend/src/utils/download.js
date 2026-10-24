import { downloadExportApi } from '../services/api';

export const EXPORT_FORMATS = {
  excel: { label: 'Excel (.xlsx)', ext: 'xlsx' },
  csv: { label: 'CSV (.csv)', ext: 'csv' },
  doc: { label: 'Text summary (.txt)', ext: 'txt' },
  tally: { label: 'Tally XML (.xml)', ext: 'xml' },
};

export function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export function exportFilename(doc, format) {
  const base = String(doc?.invoice_number || doc?.id || 'invoice').replace(/[^A-Za-z0-9._-]+/g, '_').slice(0, 60);
  return `${base}.${EXPORT_FORMATS[format]?.ext || format}`;
}

export async function downloadDocumentExport(doc, format) {
  const blob = await downloadExportApi(doc?.id || 'latest', format);
  saveBlob(blob, exportFilename(doc, format));
}
