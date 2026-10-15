import { APP_CONFIG } from './config.ts';
import { authHeaders, handleUnauthorized } from './auth.ts';

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
  next_after_id?: number | null;
  demo_only: true;
  disclaimer: string;
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers({ ...authHeaders(), ...Object.fromEntries(new Headers(init?.headers)) });
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const res = await fetch(`${APP_CONFIG.apiBaseUrl}${path}`, {
    ...init,
    signal: AbortSignal.timeout(8000),
    headers,
  });
  if (res.status === 401) handleUnauthorized();
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
  listObservations: (patientId?: string, limit = 10, beforeId?: number) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (patientId) params.set('patient_id', patientId);
    if (beforeId !== undefined) params.set('before_id', String(beforeId));
    return get<ObservationHistory>(`/api/v1/observations?${params.toString()}`);
  },
  health: () => get<{ status: string; model_version: string; demo_only: boolean }>('/health'),
};

// --- Synchronized live-demo streaming (backend sessions; synthetic data only) ---

export type StreamScenario = 'stable' | 'worsening' | 'recovering';
/** "cohort" drives every existing demo patient along its own scenario; "patient" streams one fictional patient. */
export type StreamMode = 'cohort' | 'patient';
export type StreamStatus = 'running' | 'paused' | 'stopped';

export interface StreamSession {
  session_id: string;
  patient_id: string;
  scenario: StreamScenario | 'mixed';
  mode?: StreamMode;
  patient_count?: number;
  status: StreamStatus;
  interval_ms: number;
  next_sequence: number;
  events_emitted: number;
  last_observation_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  last_emit_at: string | null;
  stopped_at: string | null;
  stop_reason: string | null;
  max_sequence: number;
  demo_only: true;
}

export interface StreamAlertSummary { id: number; patient_id: string; severity: string; status: string; title: string; created_at: string | null }

/** The single backend event contract for a committed observation (WebSocket and REST catch-up). */
export interface ObservationEvent {
  type: 'observation.created';
  event_id: number;
  observation_id: number;
  session_id: string | null;
  sequence: number | null;
  patient_id: string;
  created_at: string;
  timestamp: string;
  observation: Record<string, number>;
  model_version: string;
  prediction: { risk_score: number; risk_level: string; model_probability?: number; model_version?: string };
  alert: StreamAlertSummary | null;
  server_received_at: string | null;
  published_at: string | null;
  demo_only: true;
  data_origin: 'synthetic';
}

export interface LiveDemoConfig {
  producer_key_required: boolean;
  max_sequence: number;
  min_interval_ms: number;
  max_interval_ms: number;
  idle_timeout_seconds: number;
  active_session: StreamSession | null;
}

/** API failure with the HTTP status and the backend's structured error body (if any). */
export class ApiError extends Error {
  status: number;
  code: string | null;
  body: Record<string, unknown>;
  constructor(status: number, body: Record<string, unknown>, fallback: string) {
    super(typeof body.detail === 'string' ? body.detail : fallback);
    this.status = status;
    this.code = typeof body.error === 'string' ? body.error : null;
    this.body = body;
  }
}

async function liveRequest<T>(path: string, init: RequestInit & { json?: unknown; timeoutMs?: number } = {}): Promise<T> {
  const { json, timeoutMs = 8000, ...rest } = init;
  const headers = new Headers({ ...authHeaders(), ...Object.fromEntries(new Headers(rest.headers)) });
  // Only JSON bodies need Content-Type; GETs stay "simple" and skip the CORS preflight.
  if (json !== undefined) headers.set('Content-Type', 'application/json');
  let response: Response;
  try {
    response = await fetch(`${APP_CONFIG.apiBaseUrl}${path}`, {
      ...rest, headers, body: json === undefined ? rest.body : JSON.stringify(json), signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    throw new ApiError(0, {}, error instanceof Error && error.name === 'TimeoutError' ? 'Request timed out' : 'Network unavailable');
  }
  if (response.status === 401) handleUnauthorized();
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as Record<string, unknown>;
    throw new ApiError(response.status, body, `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const producerHeaders = (token: string) => ({ 'X-Producer-Token': token });

export const liveDemoApi = {
  config: () => liveRequest<LiveDemoConfig>('/api/v1/live-demo/config'),
  currentSession: () => liveRequest<{ session: StreamSession | null }>('/api/v1/live-demo/sessions/current'),
  getSession: (sessionId: string) => liveRequest<{ session: StreamSession }>(`/api/v1/live-demo/sessions/${encodeURIComponent(sessionId)}`),
  start: (body: { scenario: StreamScenario; interval_ms: number; takeover?: boolean; mode?: StreamMode }, producerKey?: string) =>
    liveRequest<{ session: StreamSession; producer_token: string; replaced_session: StreamSession | null }>('/api/v1/live-demo/sessions', {
      method: 'POST', json: body, headers: producerKey ? { 'X-Demo-Producer-Key': producerKey } : undefined,
    }),
  control: (sessionId: string, token: string, action: 'pause' | 'resume' | 'stop') =>
    liveRequest<{ session: StreamSession; changed: boolean }>(`/api/v1/live-demo/sessions/${encodeURIComponent(sessionId)}/${action}`, {
      method: 'POST', headers: producerHeaders(token),
    }),
  emit: (sessionId: string, token: string, sequence: number) =>
    liveRequest<{ event: ObservationEvent; events?: ObservationEvent[]; duplicate: boolean }>(`/api/v1/live-demo/sessions/${encodeURIComponent(sessionId)}/observations`, {
      method: 'POST', json: { sequence }, headers: producerHeaders(token),
    }),
  /** Committed events after `afterId`, oldest first, in the same contract as the WebSocket. */
  eventsAfter: (afterId: number, limit = 100) =>
    liveRequest<{ items: ObservationEvent[]; count: number; next_after_id: number | null }>(
      `/api/v1/live-demo/events?after_id=${afterId}&limit=${limit}`),
  latestObservationId: async () => {
    const history = await liveRequest<ObservationHistory>('/api/v1/observations?limit=1');
    return history.items[0]?.id ?? 0;
  },
};
