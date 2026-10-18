import { ENDPOINTS } from '../config/apiConfig';
import STR from '../constants/strings';

export async function uploadDocumentApi(file) {
  const formData = new FormData();
  formData.append('image', file);

  const response = await fetch(ENDPOINTS.UPLOAD, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || STR.uploadFailed);
  }
  return data;
}

export async function fetchDocumentsApi() {
  const response = await fetch(ENDPOINTS.DOCUMENTS);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to fetch invoice history');
  }
  return data;
}

export async function fetchAnalyticsApi() {
  const response = await fetch(ENDPOINTS.ANALYTICS);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to fetch analytics');
  }
  return data;
}

export async function updateDocumentApi(id, updates) {
  const response = await fetch(`${ENDPOINTS.DOCUMENTS}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to update document');
  }
  return data;
}

export async function deleteDocumentApi(id) {
  const response = await fetch(`${ENDPOINTS.DOCUMENTS}/${id}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to delete document');
  }
  return data;
}

export async function syncErpApi(id, erpData) {
  const response = await fetch(ENDPOINTS.SYNC_ERP(id), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(erpData),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'ERP Sync failed');
  }
  return data;
}

export async function simulateWhatsAppApi(file, sender) {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('sender', sender);

  const response = await fetch(ENDPOINTS.WHATSAPP_SIMULATE, {
    method: 'POST',
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'WhatsApp simulation failed');
  }
  return data;
}

export async function downloadExportApi(id = 'latest', format = 'excel') {
  const response = await fetch(ENDPOINTS.EXPORT(id, format));
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload?.error || STR.downloadFailed);
  }
  return await response.blob();
}

export const downloadExcelApi = (id = 'latest') => downloadExportApi(id, 'excel');

