// All API calls use same-origin relative URLs. In development Vite proxies
// /api to the Flask backend (see vite.config.js); in Docker, nginx does.
export const ENDPOINTS = {
  UPLOAD: '/api/v1/upload',
  HEALTH: '/api/v1/health',
  STATUS: '/api/v1/system/status',
  DOCUMENTS: '/api/v1/documents',
  ANALYTICS: '/api/v1/analytics',
  WHATSAPP_SIMULATE: '/api/v1/whatsapp/simulate',
  SYNC_ERP: (id) => `/api/v1/documents/${encodeURIComponent(id)}/sync-erp`,
  EXPORT: (id, format) => `/api/v1/documents/${encodeURIComponent(id)}/export/${format}`,
  LOGIN: '/api/v1/auth/login',
  LOGOUT: '/api/v1/auth/logout',
  SESSION: '/api/v1/auth/session',
};
