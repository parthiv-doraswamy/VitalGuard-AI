import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { SimCtx } from './simInit.ts';
import type { AlertItem } from '../types/index.ts';
import type { ToastMsg, ToastSeverity } from './simInit.ts';
import { freshSnapshot } from './snapshot.ts';
import { demoDataService } from '../services/demoDataService.ts';
import { nextReading, nextRisk, news2For, riskLevelFor } from '../services/simulation.ts';
import { showSafetyNotification } from '../services/pwa.ts';

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
          const severity = score >= 85 ? 'critical' : 'high';
          const message = `Demo risk increased · ${old.score} → ${score}. Review recommended.`;
          push('High-risk signal', message, severity, p.id);
          void showSafetyNotification('VitalGuard AI · High-risk signal', `${p.id}: ${message}`, `vg-risk-${p.id}-${t}`);
          setAlerts((a) => [{ id: `AL-SIM-${t}-${p.id}`, patientId: p.id, severity, title: 'Simulated high-risk signal', description: `Simulated risk signal increased ${old.score} to ${score}. Review recommended.`, contributors: ['simulated vital trajectory change'], status: 'open', createdAt: new Date().toISOString(), riskBefore: old.score, riskAfter: score }, ...a]);
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
  const acknowledge = useCallback((id: string) => setAlerts((a) => a.map((x) => (x.id===id ? { ...x, status: 'acknowledged' as const } : x))), []);
  const undoAcknowledge = useCallback((id: string) => setAlerts((a) => a.map((x) => (x.id===id ? { ...x, status: 'open' as const } : x))), []);
  return <SimCtx.Provider value={{ patients, latest, risks, histories, alerts, toasts, running, tick, speed, multiplier, lastRefresh, start, pause, reset, refresh, dismissToast, setSpeed, setMultiplier, acknowledge, undoAcknowledge, dataSource, setDataSource, theme, setTheme }}>{children}</SimCtx.Provider>;
}
