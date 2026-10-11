import { APP_CONFIG } from './config.ts';
import { getOperatorAccessToken, authorizedFetch } from './authenticatedFetch.ts';
import type { ObservationHistory } from './api.ts';

export interface LiveObservationEvent {
  type: 'observation.created';
  event_id: number;
  patient_id: string;
  created_at: string;
  observation: Record<string, number>;
  prediction: { risk_score: number; risk_level: string; model_version?: string };
  demo_only: true;
}
export interface LiveAlertEvent {
  type: 'alert.created';
  event_id: number;
  alert: { id: number; patient_id: string; title: string; severity: string; status: string; created_at: string };
  demo_only: true;
}
export type LiveEvent = LiveObservationEvent | LiveAlertEvent | { type: 'connected' | 'pong'; demo_only?: true };

export function createLiveSocket(onEvent: (event: LiveEvent) => void, onStatus: (status: 'connecting' | 'connected' | 'reconnecting' | 'offline') => void) {
  let socket: WebSocket | null = null;
  let stopped = false;
  let retry = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;

  const connect = () => {
    if (stopped) return;
    onStatus(retry === 0 ? 'connecting' : 'reconnecting');
    const base = APP_CONFIG.apiBaseUrl;
    const wsBase = base.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    try {
      const token = getOperatorAccessToken();
      if (!token) {
        onStatus('offline');
        return;
      }
      socket = new WebSocket(`${wsBase}/api/v1/live?token=${encodeURIComponent(token)}`);
    } catch {
      scheduleRetry();
      return;
    }
    socket.onopen = () => {
      retry = 0;
      onStatus('connected');
      heartbeat = setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) socket.send('ping');
      }, 25000);
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as LiveEvent;
        onEvent(event);
      } catch {
        // Ignore malformed frames; the REST history remains the source of truth.
      }
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => {
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = undefined;
      if (!stopped) scheduleRetry();
    };
  };

  const scheduleRetry = () => {
    if (stopped) return;
    retry += 1;
    onStatus(retry > 5 ? 'offline' : 'reconnecting');
    const delay = Math.min(30000, 1000 * 2 ** Math.min(retry - 1, 5));
    retryTimer = setTimeout(connect, delay);
  };

  connect();
  return () => {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    if (heartbeat) clearInterval(heartbeat);
    socket?.close();
  };
}

export async function reconcileObservationHistory(): Promise<ObservationHistory> {
  const response = await authorizedFetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations?limit=100`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`History reconciliation failed (${response.status})`);
  return response.json() as Promise<ObservationHistory>;
}
