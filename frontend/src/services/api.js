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

/**
 * Reads a JSON body without throwing on HTML/empty responses (e.g. a proxy
 * error page), returning a helpful error object instead.
 */
async function readJson(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      return { error: 'The server is not reachable right now. Check that the backend is running and try again.' };
    }
    return { error: `Unexpected server response (HTTP ${response.status}).` };
  }
}

export async function loginApi(username, password) {
  const response = await fetch(ENDPOINTS.LOGIN, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const data = await readJson(response);
  if (!response.ok) {
    if (response.status === 429) {
      throw new Error('Too many failed sign-in attempts. Wait a few minutes and try again.');
    }
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

  const data = await readJson(response);
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
    const data = await readJson(response);
    if (data?.authenticated && data?.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    return data;
  } catch (err) {
    return { authenticated: false, user: null, csrf_token: null };
  }
}

/**
 * Uploads a document with real upload progress (XMLHttpRequest exposes upload
 * progress events; fetch does not). onProgress receives 0-100.
 */
export function uploadDocumentApi(file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', ENDPOINTS.UPLOAD);
    xhr.withCredentials = true;
    if (activeCsrfToken) xhr.setRequestHeader('X-CSRF-Token', activeCsrfToken);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onerror = () => reject(new Error('Network error: could not reach the server.'));
    xhr.ontimeout = () => reject(new Error('The request timed out. Large or multi-page files can take a while; please try again.'));
    xhr.onload = () => {
      let data = {};
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        data = {
          error:
            xhr.status >= 502 && xhr.status <= 504
              ? 'The server is not reachable or took too long to respond. Try again in a moment.'
              : `Unexpected server response (HTTP ${xhr.status}).`,
        };
      }
      if (xhr.status === 401 && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { url: ENDPOINTS.UPLOAD } }));
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(new Error(data?.error || STR.uploadFailed));
      }
    };
    xhr.send(formData);
  });
}

export async function fetchSystemStatusApi() {
  const response = await authorizedFetch(ENDPOINTS.STATUS);
  const data = await readJson(response);
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to load system status');
  }
  return data;
}

export async function fetchDocumentsApi() {
  const response = await authorizedFetch(ENDPOINTS.DOCUMENTS);
  const data = await readJson(response);
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to fetch invoice history');
  }
  return data;
}

export async function fetchAnalyticsApi() {
  const response = await authorizedFetch(ENDPOINTS.ANALYTICS);
  const data = await readJson(response);
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
  const data = await readJson(response);
  if (!response.ok) {
    throw new Error(data?.error || 'Failed to update document');
  }
  return data;
}

export async function deleteDocumentApi(id) {
  const response = await authorizedFetch(`${ENDPOINTS.DOCUMENTS}/${id}`, {
    method: 'DELETE',
  });
  const data = await readJson(response);
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
  const data = await readJson(response);
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
  const data = await readJson(response);
  if (!response.ok) {
    throw new Error(data?.error || 'WhatsApp simulation failed');
  }
  return data;
}

export async function downloadExportApi(id = 'latest', format = 'excel') {
  const response = await authorizedFetch(ENDPOINTS.EXPORT(id, format));
  if (!response.ok) {
    const payload = await readJson(response);
    throw new Error(payload?.error || STR.downloadFailed);
  }
  return await response.blob();
}

export const downloadExcelApi = (id = 'latest') => downloadExportApi(id, 'excel');
