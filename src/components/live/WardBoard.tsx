import { Link } from 'react-router-dom';
import { HeartPulse, Wind } from 'lucide-react';
import { RiskBadge } from '../ui/Badges.tsx';
import { Sparkline } from '../ui/premium.tsx';
import { useSimulation } from '../../store/useSimulation.ts';
import { useScope } from '../../store/useScope.ts';

const RISK_COLOR = { critical: '#e11d48', high: '#f59e0b', moderate: '#0891b2', low: '#0d9488' } as const;

/** Every visible patient's latest vitals and risk trajectory, highest risk first; updates on each stream tick. */
export function WardBoard() {
  const { latest, risks, histories } = useSimulation();
  const { patients } = useScope();
  const rows = [...patients].sort((a, b) => (risks[b.id]?.score ?? 0) - (risks[a.id]?.score ?? 0));
  return (
    <ul className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4" aria-label="Live ward board" data-testid="ward-board">
      {rows.map((patient) => {
        const vitals = latest[patient.id];
        const risk = risks[patient.id];
        const color = RISK_COLOR[risk?.level ?? 'low'];
        const spo2 = (histories[patient.id] ?? []).map((reading) => reading.spo2);
        return (
          <li key={patient.id}>
            <Link to={`/patients/${patient.id}`} data-testid={`ward-tile-${patient.id}`}
              className="block rounded-2xl border border-slate-200/80 bg-white p-3 transition hover:border-teal-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
              style={{ borderLeft: `4px solid ${color}` }}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[13px] font-bold truncate">{patient.name}</p>
                  <p className="text-[11px] text-slate-500 truncate">{patient.id} · {patient.ward} · {patient.bed}</p>
                </div>
                {risk && <RiskBadge level={risk.level} score={risk.score} />}
              </div>
              {vitals && (
                <dl className="mt-2 grid grid-cols-3 gap-1 text-[11px] tabular-nums">
                  <div><dt className="text-slate-400 flex items-center gap-0.5"><HeartPulse size={11} aria-hidden />HR</dt><dd className="font-bold">{Math.round(vitals.heartRate)}</dd></div>
                  <div><dt className="text-slate-400">SpO₂</dt><dd className="font-bold">{vitals.spo2.toFixed(0)}%</dd></div>
                  <div><dt className="text-slate-400 flex items-center gap-0.5"><Wind size={11} aria-hidden />RR</dt><dd className="font-bold">{Math.round(vitals.respiratoryRate)}</dd></div>
                  <div><dt className="text-slate-400">BP</dt><dd className="font-bold">{vitals.systolicBp}/{vitals.diastolicBp}</dd></div>
                  <div><dt className="text-slate-400">Temp</dt><dd className="font-bold">{vitals.temperature.toFixed(1)}°</dd></div>
                  <div><dt className="text-slate-400">NEWS2</dt><dd className="font-bold">{risk?.news2 ?? '–'}</dd></div>
                </dl>
              )}
              <div className="mt-2 grid grid-cols-2 gap-2 items-end">
                <div><p className="text-[9px] uppercase tracking-wider text-slate-400 font-bold">Risk</p><Sparkline data={risk?.trajectory ?? []} color={color} height={26} width={110} id={`risk-${patient.id}`} /></div>
                <div><p className="text-[9px] uppercase tracking-wider text-slate-400 font-bold">SpO₂</p><Sparkline data={spo2.slice(-12)} color="#0891b2" height={26} width={110} id={`spo2-${patient.id}`} /></div>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
