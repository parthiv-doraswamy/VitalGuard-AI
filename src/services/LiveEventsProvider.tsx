import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { liveDemoApi } from './api.ts';
import type { StreamSession } from './api.ts';
import {
  bestClockSample, createLiveSocket, deliveryLatencyMs, mergeEvents,
  type ClockSample, type LiveEvent, type LiveStatus, type LoggedEvent,
} from './liveEvents.ts';
import { useStreamProducer } from './streamProducer.ts';
import { LiveEventsContext, type LiveEventsState } from './useLiveEvents.ts';
import { useSimulation } from '../store/useSimulation.ts';
import { APP_CONFIG } from './config.ts';
import { authHeaders } from './auth.ts';
import type { BackendAlertSummary } from '../store/liveIngest.ts';

const MAX_CATCH_UP_PAGES = 10;
const LATENCY_WINDOW = 20;

/**
 * Owns this tab's connection to the backend live channel.
 *
 * Every screen (dashboard on Laptop B, Live demo on Laptop A) renders the same
 * committed backend events; nothing here computes a risk score. After any
 * reconnect, events committed while offline are fetched from the REST catch-up
 * endpoint and merged by event_id, so nothing is shown twice and nothing is
 * re-submitted to the backend.
 */
export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LiveStatus>('connecting');
  const [log, setLog] = useState<LoggedEvent[]>([]);
  const [eventCount, setEventCount] = useState(0);
  const [recoveredCount, setRecoveredCount] = useState(0);
  const [alertsReceived, setAlertsReceived] = useState(0);
  const [session, setSession] = useState<StreamSession | null>(null);
  const [clock, setClock] = useState<ClockSample | null>(null);
  const [errors, setErrors] = useState<{ count: number; last: string | null }>({ count: 0, last: null });
  const [lastCatchUpAt, setLastCatchUpAt] = useState<string | null>(null);

  const logRef = useRef<LoggedEvent[]>([]);
  const lastSeenId = useRef<number | null>(null);
  const clockSamples = useRef<ClockSample[]>([]);
  const clockRef = useRef<ClockSample | null>(null);
  const submissions = useRef(new Map<string, number>());
  const alertIds = useRef(new Set<number>());
  const catchingUp = useRef(false);
  const sessionRef = useRef<StreamSession | null>(null);

  const recordSubmission = useCallback((sessionId: string, sequence: number, submittedAt: number) => {
    // Keep only the first submission time: a retry must not shorten the measured latency.
    const key = `${sessionId}:${sequence}`;
    if (!submissions.current.has(key)) submissions.current.set(key, submittedAt);
    if (submissions.current.size > 500) submissions.current.delete(submissions.current.keys().next().value as string);
  }, []);
  const producer = useStreamProducer(recordSubmission);
  // Committed stream events drive the same patient state every page renders (charts, cards, alerts).
  const { ingestObservations, ingestAlert } = useSimulation();
  const hydrated = useRef(false);

  const reportError = useCallback((message: string) => {
    setErrors((current) => ({ count: current.count + 1, last: message }));
  }, []);

  const addEvents = useCallback((incoming: LoggedEvent[]) => {
    const { log: merged, added } = mergeEvents(logRef.current, incoming);
    if (added.length === 0) return;
    logRef.current = merged;
    setLog(merged);
    setEventCount((count) => count + added.length);
    const recovered = added.filter((item) => item.origin === 'recovered').length;
    if (recovered) setRecoveredCount((count) => count + recovered);
    ingestObservations(added.map((item) => item.event));
    const maxId = Math.max(...added.map((item) => item.event.event_id));
    lastSeenId.current = Math.max(lastSeenId.current ?? 0, maxId);
    for (const item of added) {
      if (item.event.alert && !alertIds.current.has(item.event.alert.id)) {
        alertIds.current.add(item.event.alert.id);
        setAlertsReceived((count) => count + 1);
        ingestAlert(item.event.alert as BackendAlertSummary,
          { announce: item.origin === 'live', riskAfter: item.event.prediction.risk_score });
      }
    }
  }, [ingestAlert, ingestObservations]);

  /** Latest committed vitals and alerts, so a device that opens mid-stream starts from current values. */
  const hydrate = useCallback(async () => {
    if (hydrated.current) return;
    hydrated.current = true;
    try {
      const observations = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations?limit=100`, { signal: AbortSignal.timeout(8000) });
      if (observations.ok) {
        const body = await observations.json() as { items: Array<{ id: number; patient_id: string; created_at: string; inputs: Record<string, number>; prediction: { risk_score: number; risk_level: string; model_probability?: number }; session_id?: string | null; sequence?: number | null; model_version: string }> };
        ingestObservations(body.items.map((record) => ({
          type: 'observation.created', event_id: record.id, observation_id: record.id, session_id: record.session_id ?? null,
          sequence: record.sequence ?? null, patient_id: record.patient_id, created_at: record.created_at, timestamp: record.created_at,
          observation: record.inputs, model_version: record.model_version, prediction: record.prediction, alert: null,
          server_received_at: null, published_at: null, demo_only: true, data_origin: 'synthetic',
        })));
      }
      const headers = authHeaders();
      if (headers.Authorization) {
        const alerts = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/alerts?limit=100`, { headers, signal: AbortSignal.timeout(8000) });
        if (alerts.ok) {
          const body = await alerts.json() as { items: BackendAlertSummary[] };
          for (const alert of body.items) {
            alertIds.current.add(alert.id);
            ingestAlert(alert);
          }
        }
      }
    } catch {
      hydrated.current = false; // try again on the next reconnect
    }
  }, [ingestAlert, ingestObservations]);

  const applySession = useCallback((next: StreamSession | null) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const refreshSession = useCallback(async () => {
    const { session: current } = await liveDemoApi.currentSession();
    if (current) { applySession(current); return; }
    // No active session: show the last known one as stopped instead of forgetting it.
    const known = sessionRef.current;
    if (known && known.status !== 'stopped') applySession((await liveDemoApi.getSession(known.session_id)).session);
  }, [applySession]);

  const catchUp = useCallback(async () => {
    if (catchingUp.current) return;
    catchingUp.current = true;
    try {
      if (lastSeenId.current === null) {
        // First connection: start from the newest committed event rather than replaying all history.
        lastSeenId.current = await liveDemoApi.latestObservationId();
      } else {
        for (let page = 0; page < MAX_CATCH_UP_PAGES; page += 1) {
          const result = await liveDemoApi.eventsAfter(lastSeenId.current);
          const receivedAt = Date.now();
          addEvents(result.items.map((event) => ({ event, receivedAt, origin: 'recovered' as const, latencyMs: null, localLatencyMs: null })));
          if (result.next_after_id === null) break;
        }
      }
      await hydrate();
      await refreshSession();
      setLastCatchUpAt(new Date().toISOString());
    } catch (error) {
      reportError(`Catch-up after reconnect failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    } finally {
      catchingUp.current = false;
    }
  }, [addEvents, hydrate, refreshSession, reportError]);

  const onEvent = useCallback((event: LiveEvent) => {
    if (event.type === 'observation.created') {
      const receivedAt = Date.now();
      const submittedAt = event.session_id != null && event.sequence != null
        ? submissions.current.get(`${event.session_id}:${event.sequence}`) : undefined;
      addEvents([{
        event, receivedAt, origin: 'live',
        latencyMs: deliveryLatencyMs(event, receivedAt, clockRef.current),
        localLatencyMs: submittedAt !== undefined ? receivedAt - submittedAt : null,
      }]);
    } else if (event.type === 'alert.created') {
      if (!alertIds.current.has(event.alert.id)) {
        alertIds.current.add(event.alert.id);
        setAlertsReceived((count) => count + 1);
        ingestAlert(event.alert, { announce: true });
      }
    } else if (event.type === 'alert.updated') {
      ingestAlert(event.alert);
    } else if (event.type === 'stream.state') {
      const current = sessionRef.current;
      // A stop for an older session must not hide a newer active one.
      if (!(event.action === 'stopped' && current && current.session_id !== event.session.session_id && current.status !== 'stopped')) {
        applySession(event.session);
      }
    } else if (event.type === 'error') {
      reportError(event.detail ?? 'Live channel error');
    }
  }, [addEvents, applySession, ingestAlert, reportError]);

  const onClockSample = useCallback((sample: ClockSample) => {
    clockSamples.current = [...clockSamples.current.slice(-4), sample];
    const best = bestClockSample(clockSamples.current);
    clockRef.current = best;
    setClock(best);
  }, []);

  useEffect(() => createLiveSocket(onEvent, setStatus, {
    onOpen: () => { void catchUp(); },
    onClockSample,
  }), [catchUp, onClockSample, onEvent]);

  const value = useMemo<LiveEventsState>(() => {
    const live = log.filter((item) => item.origin === 'live' && item.latencyMs !== null).slice(0, LATENCY_WINDOW);
    const averageMs = live.length ? Math.round(live.reduce((sum, item) => sum + (item.latencyMs ?? 0), 0) / live.length) : null;
    return {
      status, log, latest: log[0] ?? null, eventCount, recoveredCount, alertsReceived, session, clock,
      latency: { lastMs: live[0]?.latencyMs ?? null, averageMs, samples: live.length },
      errors, lastCatchUpAt, producer,
    };
  }, [status, log, eventCount, recoveredCount, alertsReceived, session, clock, errors, lastCatchUpAt, producer]);

  return <LiveEventsContext.Provider value={value}>{children}</LiveEventsContext.Provider>;
}
