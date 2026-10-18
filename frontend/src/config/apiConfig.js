export const API_BASE_URL = 'http://localhost:5000';

export const ENDPOINTS = {
  UPLOAD: '/api/v1/upload',
  DOWNLOAD: '/api/v1/download',
  HEALTH: '/api/v1/health',
  DOCUMENTS: '/api/v1/documents',
  ANALYTICS: '/api/v1/analytics',
  WHATSAPP_SIMULATE: '/api/v1/whatsapp/simulate',
  SYNC_ERP: (id) => `/api/v1/documents/${id}/sync-erp`,
  EXPORT: (id, format) => `/api/v1/documents/${id}/export/${format}`,
  LOGIN: '/api/v1/auth/login',
  LOGOUT: '/api/v1/auth/logout',
  SESSION: '/api/v1/auth/session',
};
