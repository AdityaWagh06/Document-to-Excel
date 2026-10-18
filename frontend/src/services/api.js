import { ENDPOINTS } from '../config/apiConfig';
import STR from '../constants/strings';

// In-memory CSRF token storage (never written to localStorage or cookies directly)
let activeCsrfToken = '';

export function setCsrfToken(token) {
  activeCsrfToken = token || '';
}

export function getCsrfToken() {
  return activeCsrfToken;
}

/**
 * Standardized fetch wrapper that:
 * 1. Enforces credentials: 'include' for secure HttpOnly cookie transmission.
 * 2. Attaches the current X-CSRF-Token for state-changing HTTP methods.
 * 3. Catches 401 responses to trigger graceful re-authentication without losing form state.
 */
async function authorizedFetch(url, options = {}) {
  const reqOptions = {
    ...options,
    credentials: 'include',
  };

  const method = (reqOptions.method || 'GET').toUpperCase();
  const isStateChanging = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);

  if (isStateChanging) {
    reqOptions.headers = {
      ...(reqOptions.headers || {}),
    };
    if (activeCsrfToken) {
      reqOptions.headers['X-CSRF-Token'] = activeCsrfToken;
    }
  }

  const response = await fetch(url, reqOptions);

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { url } }));
    }
  }

  return response;
}

export async function loginApi(username, password) {
  const response = await fetch(ENDPOINTS.LOGIN, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Login failed. Please check your credentials.');
  }

  if (data?.csrf_token) {
    setCsrfToken(data.csrf_token);
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:login_success', { detail: data }));
  }

  return data;
}

export async function logoutApi() {
  const response = await authorizedFetch(ENDPOINTS.LOGOUT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  const data = await response.json();
  setCsrfToken('');

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:logout_success'));
  }

  return data;
}

export async function checkSessionApi() {
  try {
    const response = await fetch(ENDPOINTS.SESSION, {
      method: 'GET',
      credentials: 'include',
    });
    const data = await response.json();
    if (data?.authenticated && data?.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    return data;
  } catch (err) {
    return { authenticated: false, user: null, csrf_token: null };
  }
}

export async function uploadDocumentApi(file) {
  const formData = new FormData();
  formData.append('image', file);

  const response = await authorizedFetch(ENDPOINTS.UPLOAD, {
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
  const response = await authorizedFetch(ENDPOINTS.DOCUMENTS);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to fetch invoice history');
  }
  return data;
}

export async function fetchAnalyticsApi() {
  const response = await authorizedFetch(ENDPOINTS.ANALYTICS);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to fetch analytics');
  }
  return data;
}

export async function updateDocumentApi(id, updates) {
  const response = await authorizedFetch(`${ENDPOINTS.DOCUMENTS}/${id}`, {
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
  const response = await authorizedFetch(`${ENDPOINTS.DOCUMENTS}/${id}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to delete document');
  }
  return data;
}

export async function syncErpApi(id, erpData) {
  const response = await authorizedFetch(ENDPOINTS.SYNC_ERP(id), {
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

  const response = await authorizedFetch(ENDPOINTS.WHATSAPP_SIMULATE, {
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
  const response = await authorizedFetch(ENDPOINTS.EXPORT(id, format));
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload?.error || STR.downloadFailed);
  }
  return await response.blob();
}

export const downloadExcelApi = (id = 'latest') => downloadExportApi(id, 'excel');
