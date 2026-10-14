import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import type { Patient, RiskSignal, VitalReading } from '../../types/index.ts';
import { RiskBadge, TrendPill } from '../ui/Badges.tsx';
import { Sparkline } from '../ui/premium.tsx';
import { RISK_STYLES } from '../../theme/tokens.ts';
import { formatTimeAgo } from '../../utils/format.ts';

export function PatientRows({ slice, risks, latest }: {
  slice: Patient[]; risks: Record<string, RiskSignal>; latest: Record<string, VitalReading>;
}) {
  return (
    <tbody>
      {slice.map((p) => {
        const r = risks[p.id]; const v = latest[p.id];
        if (!r || !v) return null;
        const s = RISK_STYLES[r.level];
        return (
          <tr key={p.id} className="table-row group">
            <td className="pl-5 pr-2 py-3.5"><Link to={`/patients/${p.id}`} className="font-bold text-slate-900 hover:text-teal-700 hover:underline dark:text-slate-100 dark:hover:text-teal-300" aria-label={`Open patient ${p.id}`}>{p.id}</Link>
              <span className="block text-[11px] text-slate-400 mt-0.5">{p.ward} · {p.bed}</span></td>
            <td className="px-3 py-3.5 text-slate-500 tabular-nums whitespace-nowrap">{p.age} / {p.sex}</td>
            <td className="px-3 py-3.5 whitespace-nowrap text-slate-600 dark:text-slate-300">{p.ward} <span className="text-slate-400">· {p.bed}</span></td>
            <td className="px-3 py-3.5">
              <RiskBadge level={r.level} score={r.score} />
              <div className="mt-1.5 h-1 w-20 rounded-full bg-slate-100 dark:bg-white/10 overflow-hidden" aria-hidden>
                <div className="h-full rounded-full vg-bar-grow" style={{ width: `${r.score}%`, background: s.hex }} />
              </div>
            </td>
            <td className="px-3 py-3.5 text-right font-bold tabular-nums">{r.news2}</td>
            <td className="px-3 py-3.5 text-right tabular-nums">{Math.round(v.spo2)}<span className="text-slate-400 text-xs">%</span></td>
            <td className="px-3 py-3.5 text-right tabular-nums whitespace-nowrap">{Math.round(v.heartRate)} <span className="text-slate-400 text-xs">bpm</span></td>
            <td className="px-3 py-3.5"><TrendPill trend={r.trend} /></td>
            <td className="px-3 py-3.5">
              <div className="w-20"><Sparkline data={r.trajectory} color={s.hex} height={24} /></div>
              <p className="text-[10px] text-slate-400 tabular-nums mt-0.5 whitespace-nowrap">{formatTimeAgo(p.updatedAt)}</p>
            </td>
            <td className="pl-1 pr-4 py-3.5 text-right"><Link to={`/patients/${p.id}`} aria-label={`View details for ${p.id}`} className="icon-btn inline-flex opacity-60 group-hover:opacity-100 transition-all"><ChevronRight size={17} aria-hidden /></Link></td>
          </tr>
        );
      })}
    </tbody>
  );
}

export function PatientCards({ slice, risks, latest }: {
  slice: Patient[]; risks: Record<string, RiskSignal>; latest: Record<string, VitalReading>;
}) {
  return (
    <div className="mt-4 grid md:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4 stagger">
      {slice.map((p) => {
        const r = risks[p.id]; const v = latest[p.id];
        if (!r || !v) return null;
        const s = RISK_STYLES[r.level];
        return (
          <Link key={p.id} to={`/patients/${p.id}`} className="card card-hover p-5 relative overflow-hidden" aria-label={`Open ${p.id}`}>
            <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: `linear-gradient(90deg, ${s.hex}, transparent)` }} aria-hidden />
            <div className="flex items-center justify-between gap-2">
              <p className="font-display font-extrabold tracking-tight text-[15px]">{p.id}</p>
              <RiskBadge level={r.level} score={r.score} />
            </div>
            <p className="text-xs text-slate-500 mt-1">{p.ward} · Bed {p.bed} · Age {p.age} · {p.sex}</p>
            <div className="mt-3"><Sparkline data={r.trajectory} color={s.hex} height={44} /></div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              {[['HR', `${Math.round(v.heartRate)}`], ['SpO₂', `${Math.round(v.spo2)}%`], ['NEWS2', `${r.news2}`]].map(([l, val]) => (
                <div key={l} className="rounded-xl bg-slate-50 dark:bg-white/[0.04] border border-slate-200/50 dark:border-white/[0.06] p-2"><p className="eyebrow !text-[10px]">{l}</p><p className="metric text-base mt-0.5">{val}</p></div>
              ))}
            </div>
            <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-2"><TrendPill trend={r.trend} /> Updated {formatTimeAgo(p.updatedAt)}</p>
          </Link>
        );
      })}
    </div>
  );
}
