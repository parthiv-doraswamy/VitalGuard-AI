import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { SimCtx } from './simInit.ts';
import type { AlertItem } from '../types/index.ts';
import type { ToastMsg, ToastSeverity } from './simInit.ts';
import { freshSnapshot } from './snapshot.ts';

import { demoDataService } from '../services/demoDataService.ts';
import { nextReading, nextRisk, news2For, riskLevelFor } from '../services/simulation.ts';
import type { ObservationEvent } from '../services/api.ts';
import { APP_CONFIG } from '../services/config.ts';
import { authHeaders, getSession } from '../services/auth.ts';
import { showAlertNotification } from '../services/alertNotifier.ts';
import { alertFromBackend, applyObservations, backendAlertId, parseBackendAlertId, type BackendAlertSummary } from './liveIngest.ts';

const FLUSH_MS = 120;
const GAP = { slow: 4000, normal: 2000, fast: 1000 };
export function SimulationProvider({ children }: { children: ReactNode }) {
  const base = useMemo(freshSnapshot, []);

  const [patients, setPatients] = useState(base.patients);
  const [latest, setLatest] = useState(base.latest);
  const [risks, setRisks] = useState(base.risks);
  const [histories, setHistories] = useState(base.histories);
  const [alerts, setAlerts] = useState<AlertItem[]>(() => {
    try { const s = localStorage.getItem('vg-alerts'); if (s) return JSON.parse(s); } catch { /*noop*/ }
    return demoDataService.alerts();
  });
  const [toasts, setToasts] = useState<ToastMsg[]>([]);

  const [running, setRunning] = useState(false);
  const [tick, setTick] = useState(0);
  const [speed, setSpeed] = useState<'slow'|'normal'|'fast'>('normal');
  const [multiplier, setMultiplier] = useState<1|2>(1);
  const [dataSource, setDataSource] = useState<'demo'|'api'>('demo');
  const [theme, setThemeState] = useState<'light'|'dark'>(() => (localStorage.getItem('vg-theme') as 'light'|'dark') || 'light');
  const [lastRefresh, setLastRefresh] = useState(() => new Date().toISOString());

  const timer = useRef<number | null>(null);
  const idRef = useRef(1);
  const [streamTick, setStreamTick] = useState<number | null>(null);
  const [alertActionError, setAlertActionError] = useState<string | null>(null);
  // Mirror of the patient state so batched stream updates apply to the latest values.
  const stateRef = useRef({ patients, latest, risks, histories });
  stateRef.current = { patients, latest, risks, histories };
  const pending = useRef<ObservationEvent[]>([]);
  const flushTimer = useRef<number | null>(null);
  const seenAlerts = useRef(new Set<string>());
  const setTheme = useCallback((t: 'light'|'dark') => {

    setThemeState(t); localStorage.setItem('vg-theme', t);
    document.documentElement.classList.toggle('dark', t === 'dark');
  }, []);
  useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark'); }, [theme]);
  useEffect(() => { try { localStorage.setItem('vg-alerts', JSON.stringify(alerts)); } catch { /*noop*/ } }, [alerts]);
  const push = useCallback((title: string, message: string, severity: ToastSeverity = 'high', patientId?: string) => {
    const id = idRef.current++;
    setToasts((t) => [...t.slice(-4), { id, title, message, severity, at: new Date().toISOString(), patientId }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 8000);
  }, []);
  const flushObservations = useCallback(() => {
    flushTimer.current = null;
    const batch = pending.current;
    pending.current = [];
    if (batch.length === 0) return;
    const next = applyObservations(stateRef.current, batch);
    stateRef.current = next;
    setPatients(next.patients); setLatest(next.latest); setRisks(next.risks); setHistories(next.histories);
    const sequences = batch.map((event) => event.sequence).filter((value): value is number => typeof value === 'number');
    if (sequences.length) setStreamTick(Math.max(...sequences));
    setLastRefresh(new Date().toISOString());
  }, []);
  const ingestObservations = useCallback((events: ObservationEvent[]) => {
    if (events.length === 0) return;
    pending.current.push(...events);
    // A cohort tick arrives as one WebSocket frame per patient; render them together.
    if (flushTimer.current === null) flushTimer.current = window.setTimeout(flushObservations, FLUSH_MS);
  }, [flushObservations]);
  useEffect(() => () => { if (flushTimer.current !== null) window.clearTimeout(flushTimer.current); }, []);

  const ingestAlert = useCallback((summary: BackendAlertSummary, options: { announce?: boolean; riskAfter?: number } = {}) => {
    const item = alertFromBackend(summary, options.riskAfter);
    const isNew = !seenAlerts.current.has(item.id);
    seenAlerts.current.add(item.id);
    setAlerts((current) => {
      const index = current.findIndex((alert) => alert.id === item.id);
      if (index === -1) return [item, ...current];
      const copy = [...current];
      copy[index] = { ...copy[index], status: item.status };
      return copy;
    });
    if (!isNew || !options.announce || summary.status !== 'open') return;
    const session = getSession();
    const patient = stateRef.current.patients.find((p) => p.id === summary.patient_id);
    const mine = session?.role === 'doctor' && patient?.assignedDoctor === session.username;
    // Doctors are told only about their own patients; nurses and admins about every patient.
    if (session?.role === 'doctor' && !mine) return;
    push(mine ? 'Your patient needs review' : 'High-risk signal', `${patient?.name ?? summary.patient_id} · ${summary.title}`,
      item.severity === 'critical' ? 'critical' : 'high', summary.patient_id);
    if (mine) void showAlertNotification(item, patient);
  }, [push]);
  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const refresh = useCallback(() => {
    setLastRefresh(new Date().toISOString());
    setPatients((ps) => ps.map((p) => ({ ...p, updatedAt: new Date().toISOString() })));
  }, []);

  const step = useCallback(() => {
    const eff = (speed === 'slow' ? 0.6 : speed === 'fast' ? 1.8 : 1) * multiplier;
    const t = tick + 1; setTick(t);
    setLatest((prev) => {
      const n = { ...prev };
      patients.forEach((p, i) => { n[p.id] = nextReading(prev[p.id], p.scenario, t, i * 3.7 + 1, eff); });
      setHistories((h) => { const c = { ...h }; Object.keys(c).forEach((k) => { c[k] = [...c[k], n[k]].slice(-40); }); return c; });
      return n;
    });
    setRisks((prev) => {
      const n = { ...prev };
      patients.forEach((p, i) => {
        const old = prev[p.id];
        const score = nextRisk(old.score, p.scenario, t, i * 5.3 + 2, eff);
        if (old.score < 65 && score >= 65) {
          push('High-risk signal', `Demo risk increased · ${old.score} → ${score}`, score >= 85 ? 'critical' : 'high', p.id);

          setAlerts((a) => [{ id: `AL-SIM-${t}-${p.id}`, patientId: p.id, severity: score >= 85 ? 'critical' : 'high', title: 'Simulated high-risk signal', description: `Simulated risk signal increased ${old.score} to ${score}. Review recommended.`, contributors: ['simulated vital trajectory change'], status: 'open', createdAt: new Date().toISOString(), riskBefore: old.score, riskAfter: score }, ...a]);
        }
        n[p.id] = { ...old, score, level: riskLevelFor(score), probability: score/100, news2: news2For(score, p.scenario==='stable'?1:p.scenario==='recovering'?3:5), trajectory: [...old.trajectory.slice(-11), score], updatedAt: new Date().toISOString() };
      });
      return n;
    });
    setPatients((ps) => ps.map((p) => ({ ...p, updatedAt: new Date().toISOString() })));
  }, [tick, speed, multiplier, patients, push]);
  useEffect(() => {
    if (!running) return;
    const ms = GAP[speed] / multiplier;
    timer.current = window.setInterval(step, ms);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [running, speed, multiplier, step]);
  const start = useCallback(() => setRunning(true), []);
  const pause = useCallback(() => { setRunning(false); if (timer.current) window.clearInterval(timer.current); }, []);
  const reset = useCallback(() => {
    pause(); setTick(0); setLastRefresh(new Date().toISOString());

    const b = freshSnapshot(); setPatients(b.patients); setLatest(b.latest); setRisks(b.risks); setHistories(b.histories);

    setAlerts(demoDataService.alerts());
    try { localStorage.removeItem('vg-alerts'); } catch { /*noop*/ }
  }, [pause]);
  const setStatus = useCallback((id: string, status: AlertItem['status']) =>
    setAlerts((a) => a.map((x) => (x.id === id ? { ...x, status } : x))), []);
  const acknowledge = useCallback((id: string) => {
    const backendId = parseBackendAlertId(id);
    if (backendId === null || !getSession()?.token) { setStatus(id, 'acknowledged'); return; }
    // Backend alerts change state on the server, which checks the role and patient assignment.
    setAlertActionError(null);
    fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/alerts/${backendId}/acknowledge`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: '{}', signal: AbortSignal.timeout(8000),
    }).then((response) => {
      if (response.ok) setStatus(id, 'acknowledged');
      else setAlertActionError(response.status === 403 ? 'Your role cannot acknowledge this alert.' : `Acknowledge failed (${response.status}).`);
    }).catch(() => setAlertActionError('Backend unavailable; the alert was not acknowledged.'));
  }, [setStatus]);
  // Backend alerts cannot be re-opened (the server lifecycle only moves forward).
  const undoAcknowledge = useCallback((id: string) => { if (parseBackendAlertId(id) === null) setStatus(id, 'open'); }, [setStatus]);
  return <SimCtx.Provider value={{ patients, latest, risks, histories, alerts, toasts, running, tick, speed, multiplier, lastRefresh, start, pause, reset, refresh, dismissToast, setSpeed, setMultiplier, acknowledge, undoAcknowledge, dataSource, setDataSource, theme, setTheme, ingestObservations, ingestAlert, streamTick, alertActionError }}>{children}</SimCtx.Provider>;

}
