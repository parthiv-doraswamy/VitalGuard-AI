import { APP_CONFIG } from './config.ts';
import { api } from './api.ts';
import { demoDataService } from './demoDataService.ts';

// Data Provider: Demo Provider OR API Provider.
// Defaults to DEMO MODE unless backend API is available/configured.
// In demo mode no network requests are issued (avoids failed-request spam).
export type DataSource = 'demo' | 'api';
let cachedSource: DataSource | null = null;

export function resolveDataSource(override?: DataSource): DataSource {
  if (override) { cachedSource = override; return override; }
  if (cachedSource) return cachedSource;
  cachedSource = APP_CONFIG.demoMode ? 'demo' : 'api';
  return cachedSource;
}

export function isDemoMode(override?: DataSource): boolean {
  return resolveDataSource(override) === 'demo';
}

// Thin wrappers: try API, fall back to demo on any failure.
export async function fetchPatients(override?: DataSource) {
  if (isDemoMode(override)) return demoDataService.listPatients();
  try { return (await api.listPatients()) as ReturnType<typeof demoDataService.listPatients>; }
  catch { cachedSource = 'demo'; return demoDataService.listPatients(); }
}
export const dataProvider = { fetchPatients, demo: demoDataService, api };
