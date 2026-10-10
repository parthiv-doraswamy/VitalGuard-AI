const defaultApiBaseUrl = import.meta.env.PROD
  ? 'https://vitalguard-risk-api.onrender.com'
  : 'http://localhost:8000';

export const APP_CONFIG = {
  demoMode: (import.meta.env.VITE_DEMO_MODE ?? 'true') !== 'false',
  apiBaseUrl: ((import.meta.env.VITE_API_BASE_URL as string) || defaultApiBaseUrl).replace(/\/$/, ''),
  version: (import.meta.env.VITE_APP_VERSION as string) || '0.2.0-demo',
  env: import.meta.env.MODE || 'development',
};
