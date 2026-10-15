import { APP_CONFIG } from './config.ts';
import type { ObservationEvent, ObservationHistory, StreamSession } from './api.ts';

export type LiveObservationEvent = ObservationEvent;
export interface LiveAlertEvent {
  type: 'alert.created';
  event_id: number;
  observation_id?: number;
  session_id?: string | null;
  alert: { id: number; patient_id: string; title: string; severity: string; status: string; created_at: string };
  demo_only: true;
}
export interface LiveAlertUpdatedEvent {
  type: 'alert.updated';
  event_id: number;
  action: 'acknowledge' | 'resolve';
  actor: string;
  alert: { id: number; patient_id: string; title: string; severity: string; status: string; created_at: string };
  demo_only: true;
}
export interface StreamStateEvent {
  type: 'stream.state';
  action: 'started' | 'paused' | 'resumed' | 'stopped';
  session: StreamSession;
  demo_only: true;
}
export interface PongEvent { type: 'pong'; client_time?: number | null; server_time?: string }
export type LiveEvent =
  | LiveObservationEvent | LiveAlertEvent | LiveAlertUpdatedEvent | StreamStateEvent | PongEvent
  | { type: 'connected'; server_time?: string; demo_only?: true }
  | { type: 'error'; detail?: string };
export type LiveStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline';

/** One clock-offset sample: serverTime ≈ localTime + offsetMs, accurate to about ±rttMs/2. */
export interface ClockSample { offsetMs: number; rttMs: number }

export function clockSampleFromPong(pong: PongEvent, receivedAt: number): ClockSample | null {
  if (typeof pong.client_time !== 'number' || !pong.server_time) return null;
  const serverTime = Date.parse(pong.server_time);
  if (Number.isNaN(serverTime)) return null;
  const rttMs = Math.max(0, receivedAt - pong.client_time);
  return { offsetMs: serverTime - (pong.client_time + rttMs / 2), rttMs };
}

/** Prefer the lowest-RTT sample: it bounds the offset error most tightly. */
export function bestClockSample(samples: ClockSample[]): ClockSample | null {
  return samples.reduce<ClockSample | null>((best, sample) => (!best || sample.rttMs < best.rttMs ? sample : best), null);
}

/**
 * Server receipt → delivered on this device, in ms, corrected for clock offset.
 * Null when the event has no server timestamp (e.g. recovered through REST) or no clock sample exists yet.
 */
export function deliveryLatencyMs(event: ObservationEvent, receivedAt: number, clock: ClockSample | null): number | null {
  if (!clock || !event.server_received_at) return null;
  const serverReceived = Date.parse(event.server_received_at);
  if (Number.isNaN(serverReceived)) return null;
  return Math.max(0, Math.round(receivedAt + clock.offsetMs - serverReceived));
}

export interface LoggedEvent {
  event: ObservationEvent;
  receivedAt: number;
  origin: 'live' | 'recovered';
  latencyMs: number | null;
  /** Exact submit → receipt time, only known on the producing device. */
  localLatencyMs: number | null;
}

/**
 * Merge newly received events into a newest-first log, keyed by event_id.
 * An event seen live and again during catch-up is kept once (the first copy wins).
 */
export function mergeEvents(log: LoggedEvent[], incoming: LoggedEvent[], max = 200): { log: LoggedEvent[]; added: LoggedEvent[] } {
  const seen = new Set(log.map((item) => item.event.event_id));
  const added: LoggedEvent[] = [];
  for (const item of incoming) {
    if (seen.has(item.event.event_id)) continue;
    seen.add(item.event.event_id);
    added.push(item);
  }
  if (added.length === 0) return { log, added };
  const merged = [...added, ...log].sort((a, b) => b.event.event_id - a.event.event_id).slice(0, max);
  return { log: merged, added };
}

interface SocketOptions {
  /** Called on every successful (re)connect; `reconnect` is false only for the first connection. */
  onOpen?: (info: { reconnect: boolean }) => void;
  onClockSample?: (sample: ClockSample) => void;
  heartbeatMs?: number;
  /** Close a connection that has not answered a ping within this time (half-open sockets). */
  pongTimeoutMs?: number;
}

export function createLiveSocket(onEvent: (event: LiveEvent) => void, onStatus: (status: LiveStatus) => void, options: SocketOptions = {}) {
  let socket: WebSocket | null = null;
  let stopped = false;
  let retry = 0;
  let opened = false;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let pongWatchdog: ReturnType<typeof setTimeout> | undefined;

  const sendPing = () => {
    if (socket?.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: 'ping', client_time: Date.now() }));
    if (!pongWatchdog) {
      // A network drop can leave a socket that never errors; without a pong it is not "connected".
      pongWatchdog = setTimeout(() => { pongWatchdog = undefined; socket?.close(); }, options.pongTimeoutMs ?? 10000);
    }
  };
  const clearWatchdog = () => { if (pongWatchdog) clearTimeout(pongWatchdog); pongWatchdog = undefined; };

  const connect = () => {
    if (stopped) return;
    onStatus(retry === 0 ? 'connecting' : 'reconnecting');
    const base = APP_CONFIG.apiBaseUrl;
    const wsBase = base.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    try {
      socket = new WebSocket(`${wsBase}/api/v1/live`);
    } catch {
      scheduleRetry();
      return;
    }
    socket.onopen = () => {
      retry = 0;
      onStatus('connected');
      options.onOpen?.({ reconnect: opened });
      opened = true;
      sendPing();
      heartbeat = setInterval(sendPing, options.heartbeatMs ?? 15000);
    };
    socket.onmessage = (message) => {
      const receivedAt = Date.now();
      let event: LiveEvent;
      try {
        event = JSON.parse(String(message.data)) as LiveEvent;
      } catch {
        // Ignore malformed frames; the REST history remains the source of truth.
        return;
      }
      if (event.type === 'pong') {
        clearWatchdog();
        const sample = clockSampleFromPong(event, receivedAt);
        if (sample) options.onClockSample?.(sample);
      }
      onEvent(event);
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => {
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = undefined;
      clearWatchdog();
      if (!stopped) scheduleRetry();
    };
  };

  const browserOffline = () => typeof navigator !== 'undefined' && navigator.onLine === false;

  const scheduleRetry = () => {
    if (stopped) return;
    if (browserOffline()) {
      // No point retrying until the browser reports a network again (see onOnline).
      onStatus('offline');
      return;
    }
    retry += 1;
    onStatus(retry > 5 ? 'offline' : 'reconnecting');
    const delay = Math.min(30000, 1000 * 2 ** Math.min(retry - 1, 5));
    retryTimer = setTimeout(connect, delay);
  };

  const onOffline = () => {
    onStatus('offline');
    if (retryTimer) clearTimeout(retryTimer);
    socket?.close();
  };
  const onOnline = () => {
    if (stopped) return;
    if (retryTimer) clearTimeout(retryTimer);
    if (socket && socket.readyState === WebSocket.OPEN) return;
    retry = 1; // reconnect now; catch-up runs on open
    connect();
  };
  if (typeof window !== 'undefined') {
    window.addEventListener('offline', onOffline);
    window.addEventListener('online', onOnline);
  }

  connect();
  return () => {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    if (heartbeat) clearInterval(heartbeat);
    clearWatchdog();
    if (typeof window !== 'undefined') {
      window.removeEventListener('offline', onOffline);
      window.removeEventListener('online', onOnline);
    }
    socket?.close();
  };
}

export async function reconcileObservationHistory(): Promise<ObservationHistory> {
  const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations?limit=100`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`History reconciliation failed (${response.status})`);
  return response.json() as Promise<ObservationHistory>;
}
