import { APP_CONFIG } from './config.ts';

export interface RiskPredictionInput {
  patient_id: string;
  age: number;
  heart_rate: number;
  spo2: number;
  systolic_bp: number;
  diastolic_bp: number;
  temperature: number;
  respiratory_rate: number;
}
export interface RiskPredictionResult {
  patient_id: string;
  observation_id: number | null;
  created_at: string | null;
  risk_score: number;
  risk_level: 'low' | 'moderate' | 'high' | 'critical';
  model_probability: number;
  factors: Array<{ feature: string; observed_value: number; direction: 'increases-risk' | 'decreases-risk'; explanation: string }>;
  model_version: string;
  demo_only: true;
  disclaimer: string;
}
export interface ObservationRecord {
  id: number;
  patient_id: string;
  created_at: string;
  inputs: Omit<RiskPredictionInput, 'patient_id'>;
  prediction: RiskPredictionResult;
  model_version: string;
}
export interface ObservationHistory {
  items: ObservationRecord[];
  count: number;
  limit: number;
  next_before_id: number | null;
  demo_only: true;
  disclaimer: string;
}
const AUTH_STORAGE_KEY = 'vitalguard.operator.session';

function getAccessToken(): string | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as { token?: string; expiresAt?: number };
    if (!session.token || !session.expiresAt || session.expiresAt <= Date.now()) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
    return session.token;
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getAccessToken();
  if (token) headers.set('Authorization', 'Bearer ' + token);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const res = await fetch(`${APP_CONFIG.apiBaseUrl}${path}`, {
    ...init,
    signal: AbortSignal.timeout(8000),
    headers,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `API request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
async function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' });
}
export const api = {
  listPatients: () => get('/api/v1/patients'),
  getPatient: (id: string) => get(`/api/v1/patients/${encodeURIComponent(id)}`),
  getVitals: (id: string) => get(`/api/v1/patients/${encodeURIComponent(id)}/vitals`),
  getLatestVitals: (id: string) => get(`/api/v1/patients/${encodeURIComponent(id)}/vitals/latest`),
  predictRisk: (input: RiskPredictionInput) =>
    request<RiskPredictionResult>('/api/v1/risk/predict', { method: 'POST', body: JSON.stringify(input) }),
  listObservations: (patientId?: string, limit = 10) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (patientId) params.set('patient_id', patientId);
    return get<ObservationHistory>(`/api/v1/observations?${params.toString()}`);
  },
  health: () => get<{ status: string; model_version: string; demo_only: boolean }>('/health'),
};
