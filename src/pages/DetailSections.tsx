import { Link } from 'react-router-dom';
import { SectionCard } from '../components/ui/Primitives.tsx';
import { ExplanationPanel } from '../components/risk/ExplanationPanel.tsx';
import { VitalLine } from '../components/charts/Vitals.tsx';
import { EventTimeline, buildTimeline } from '../components/patients/Timeline.tsx';
import { CHART_COLORS } from '../theme/tokens.ts';
import { demoDataService } from '../services/demoDataService.ts';
import { useSimulation } from '../store/useSimulation.ts';
import { formatTimeAgo } from '../utils/format.ts';
export function ExplainCard({ patientId }: { patientId: string }) {
  const { latest } = useSimulation();
  const v = latest[patientId];
  if (!v) return null;
  const factors = demoDataService.factors(patientId).map((f, i) => {
    if (i === 0) return { ...f, currentValue: `${Math.round(v.spo2)}%`, trend: 'Downward in window' };
    if (i === 1) return { ...f, currentValue: `${Math.round(v.heartRate)} bpm`, trend: 'Upward in window' };
    return f;
  });
  return (
    <div className="mt-4">
      <SectionCard eyebrow="Explainability" title="Why is the AI risk signal elevated?" hint="Ranked signal contributions" label="AI explanation">
        <ExplanationPanel factors={factors} patientId={patientId} />
      </SectionCard>
    </div>
  );
}
export function VitalCharts({ patientId }: { patientId: string }) {
  const { latest, histories } = useSimulation();
  const v = latest[patientId];
  const h = histories[patientId] ?? [];
  if (!v) return null;
  const rows = h.map((x) => ({ t: formatTimeAgo(x.timestamp), hr: x.heartRate, spo2: x.spo2, sys: x.systolicBp, dia: x.diastolicBp, temp: x.temperature, rr: x.respiratoryRate }));
  const C = (t: string, hint: string, l: string, val: string, u: string, lines: { key: string; color: string; name: string }[], unit: string) => (
    <SectionCard key={l} title={t} hint={hint} label={`${l} trend`}>
      <div className="flex items-baseline gap-2"><p className="metric text-2xl">{val}</p><p className="text-xs text-slate-400">{u}</p></div>
      <div className="mt-2"><VitalLine data={rows} lines={lines} unit={unit} /></div>
    </SectionCard>
  );
  return (
    <div className="mt-4 grid lg:grid-cols-2 gap-4 items-start">
      {C('Heart rate', 'Beats per minute', 'hr', String(Math.round(v.heartRate)), 'bpm', [{ key: 'hr', color: CHART_COLORS.heartRate, name: 'HR' }], 'bpm')}
      {C('SpO₂', 'Oxygen saturation', 'spo2', String(Math.round(v.spo2)), '%', [{ key: 'spo2', color: CHART_COLORS.spo2, name: 'SpO₂' }], '%')}
      {C('Blood pressure', 'Systolic + diastolic pair', 'bp', `${v.systolicBp}/${v.diastolicBp}`, 'mmHg', [{ key: 'sys', color: CHART_COLORS.systolic, name: 'Systolic' }, { key: 'dia', color: CHART_COLORS.diastolic, name: 'Diastolic' }], 'mmHg')}
      {C('Temperature', 'Degrees Celsius', 'temp', v.temperature.toFixed(1), '°C', [{ key: 'temp', color: CHART_COLORS.temperature, name: 'Temp' }], '°C')}
      {C('Respiratory rate', 'Breaths per minute', 'rr', String(Math.round(v.respiratoryRate)), '/min', [{ key: 'rr', color: CHART_COLORS.respiratoryRate, name: 'RR' }], '/min')}
      <TimelineCard patientId={patientId} />
    </div>
  );
}
export function TimelineCard({ patientId }: { patientId: string }) {
  const { histories, risks } = useSimulation();
  const h = histories[patientId] ?? [];
  const r = risks[patientId];
  if (!r) return null;
  const events = buildTimeline(h, r.trajectory);
  return (
    <SectionCard eyebrow="Timeline" title="Event timeline" hint="Signal and observation history" label="Demo event timeline">
      <span className="sr-only">Demo event timeline</span>
      <EventTimeline events={events} />
    </SectionCard>
  );
}
export function AlertList({ patientId }: { patientId: string }) {
  const { alerts } = useSimulation();
  const list = alerts.filter((a) => a.patientId === patientId).slice(0, 3);
  return (
    <div className="mt-4">
      <SectionCard eyebrow="Signals" title="Recent alerts" hint="Signals for this patient" label="Recent alerts"
        action={<Link to="/alerts" className="btn-ghost !text-[13px] !py-1.5">Alert center</Link>}>
        {list.length === 0 ? <p className="text-sm text-slate-500">No alerts for this patient yet.</p> : (
          <ul className="space-y-2.5">
            {list.map((a) => (
              <li key={a.id} className="rounded-2xl border border-slate-200/70 dark:border-white/[0.07] px-3.5 py-3 text-sm hover:border-teal-300/60 transition-colors">
                <p className="font-bold">{a.title} <span className="font-normal text-slate-400 tabular-nums">· {a.riskBefore} → {a.riskAfter}</span></p>
                <p className="text-xs text-slate-500 mt-0.5 capitalize">{formatTimeAgo(a.createdAt)} · {a.status} · Review recommended</p>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
