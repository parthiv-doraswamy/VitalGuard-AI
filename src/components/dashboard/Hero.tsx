import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, MapPin } from 'lucide-react';
import type { Patient, RiskSignal, VitalReading, AlertItem } from '../../types/index.ts';
import { RiskBadge, TrendPill } from '../ui/Badges.tsx';
import { RiskTrajectoryChart } from '../charts/Trajectory.tsx';
import { LiveEcg } from '../ui/premium.tsx';
import { formatTimeAgo } from '../../utils/format.ts';
import { RISK_STYLES } from '../../theme/tokens.ts';

export function HeroPatient({ hero, vitals, patient }: { hero: RiskSignal; vitals: VitalReading; patient: Patient }) {
  const delta = hero.trajectory[hero.trajectory.length - 1] - hero.trajectory[0];
  return (
    <Link to="/patients/P-SIM-003" aria-label="Open priority patient P-SIM-003"
      className="card card-hover mt-5 p-0 block relative overflow-hidden text-left !border-0 text-white"
      style={{ background: 'linear-gradient(115deg,#0a1128 0%,#10233f 40%,#0c3542 72%,#0b4a4a 100%)' }}>
      <div className="absolute inset-0 vg-grid-bg opacity-50" aria-hidden />
      <div className="absolute -left-16 -top-20 h-64 w-64 rounded-full blur-3xl opacity-25 animate-vg-drift" style={{ background: 'radial-gradient(circle,rgba(45,212,191,.9),transparent 70%)' }} aria-hidden />
      <div className="absolute right-0 top-0 h-full w-[46%] opacity-[0.16] hidden md:block" aria-hidden>
        <LiveEcg className="h-full w-full text-teal-300" />
      </div>
      <div className="relative p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow !text-teal-300 inline-flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-400 pulse-dot" aria-hidden />
            Priority patient
          </span>
          <span className="ml-auto flex items-center gap-2">
            <TrendPill trend={hero.trend} />
            <span className="text-xs font-bold text-teal-200 inline-flex items-center gap-1">Open <ArrowRight size={14} aria-hidden /></span>
          </span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <p className="font-display text-2xl sm:text-[28px] font-extrabold tracking-tight">P-SIM-003</p>
          <p className="text-sm text-slate-300 inline-flex items-center gap-1.5"><MapPin size={14} aria-hidden className="text-teal-300" />{patient.ward} · Bed {patient.bed} · Age {patient.age}</p>
          <RiskBadge level={hero.level} score={hero.score} />
        </div>
        <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2.5">
          {[
            { l: 'Risk signal', v: `${hero.score} / 100` },
            { l: 'NEWS2 reference', v: String(hero.news2) },
            { l: 'Heart rate', v: `${Math.round(vitals.heartRate)} bpm` },
            { l: 'SpO₂', v: `${Math.round(vitals.spo2)}%` },
            { l: 'Blood pressure', v: `${vitals.systolicBp}/${vitals.diastolicBp}` },
            { l: 'Updated', v: formatTimeAgo(patient.updatedAt) },
          ].map((m) => (
            <div key={m.l} className="rounded-2xl bg-white/[0.06] border border-white/10 backdrop-blur px-3 py-2.5">
              <p className="eyebrow !text-[10px] !text-slate-400">{m.l}</p>
              <p className="metric text-lg mt-0.5 text-white">{m.v}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 grid lg:grid-cols-[minmax(0,1fr)_250px] gap-4 items-stretch">
          <div className="min-w-0 rounded-2xl bg-white/[0.05] border border-white/10 p-3">
            <div className="flex items-center justify-between px-1 pb-1">
              <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-slate-400">Trajectory · 2h window</p>
              <p className="text-[11px] font-bold text-teal-300 tabular-nums inline-flex items-center gap-1"><ArrowUpRight size={13} aria-hidden />+{delta} pts</p>
            </div>
            <RiskTrajectoryChart data={hero.trajectory} labels={hero.trajectoryLabels} height={180} id="vg-hero-fill" />
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur p-4 text-sm">
            <p className="eyebrow !text-[10px] !text-slate-400">Trajectory summary</p>
            <p className="metric text-3xl mt-1 text-white">+{delta} <span className="text-sm font-bold text-slate-400">pts</span></p>
            <p className="text-xs mt-1 text-slate-300">Direction: <strong className="capitalize">{hero.trend}</strong> · Window: 2h</p>
            <p className={`text-xs mt-2 font-bold ${RISK_STYLES[hero.level].text} brightness-150`}>Review recommended.</p>
          </div>
        </div>
      </div>
    </Link>
  );
}

export function RecentAlerts({ alerts }: { alerts: AlertItem[] }) {
  const rows = [...alerts].sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)).slice(0, 3);
  if (rows.length === 0) return null;
  return (
    <ul className="space-y-2.5">
      {rows.map((a) => (
        <li key={a.id}>
          <Link to="/alerts" className="flex items-center gap-3 rounded-2xl border border-slate-200/70 dark:border-white/[0.07] px-3.5 py-3 hover:border-teal-300 hover:bg-teal-50/40 dark:hover:bg-teal-400/[0.06] hover:-translate-y-px transition-all group">
            <span className="h-8 w-1 rounded-full shrink-0" style={{ background: a.severity === 'critical' ? '#e11d48' : a.severity === 'high' ? '#ea580c' : '#0d9488' }} aria-hidden />
            <div className="min-w-0">
              <p className="text-[13px] font-bold truncate">{a.title} · {a.patientId}</p>
              <p className="text-[11px] text-slate-400 tabular-nums">{formatTimeAgo(a.createdAt)}{a.riskBefore !== undefined ? ` · ${a.riskBefore} → ${a.riskAfter}` : ''} · <span className="capitalize">{a.status}</span></p>
            </div>
            <ArrowRight size={15} aria-hidden className="ml-auto text-slate-300 group-hover:text-teal-600 group-hover:translate-x-0.5 transition-all shrink-0" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function filterCohort(patients: Patient[], risks: Record<string, RiskSignal>, f: { q: string; ward: string; level: string }) {
  return patients
    .filter((p) => !f.q || p.id.toLowerCase().includes(f.q.toLowerCase()))
    .filter((p) => f.ward === 'All' || p.ward === f.ward)
    .filter((p) => f.level === 'All' || risks[p.id]?.level === f.level.toLowerCase())
    .sort((a, b) => (risks[b.id]?.score ?? 0) - (risks[a.id]?.score ?? 0));
}
