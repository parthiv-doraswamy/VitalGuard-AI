import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import type { Patient, RiskSignal, VitalReading } from '../../types/index.ts';
import { RiskBadge, TrendPill } from '../ui/Badges.tsx';
import { Sparkline } from '../ui/premium.tsx';
import { RISK_STYLES } from '../../theme/tokens.ts';
import { formatTimeAgo } from '../../utils/format.ts';

export function PriorityTable({ patients, risks, latest, compact }: {
  patients: Patient[]; risks: Record<string, RiskSignal>; latest: Record<string, VitalReading>; compact?: boolean;
}) {
  const rows = [...patients].sort((a, b) => (risks[b.id]?.score ?? 0) - (risks[a.id]?.score ?? 0));
  return (
    <div className="overflow-hidden -m-1 p-1">
      <div className="overflow-x-auto rounded-2xl border border-slate-200/60 dark:border-white/[0.07]">
        <table className="w-full text-sm min-w-[860px] bg-white dark:bg-transparent">
          <thead className="table-head sticky top-0">
            <tr>
              <th scope="col" className="!pl-5">#</th>
              <th scope="col">Patient</th>
              <th scope="col">Ward / Bed</th>
              <th scope="col">Risk</th>
              <th scope="col" className="text-right">NEWS2</th>
              <th scope="col" className="text-right">SpO₂</th>
              <th scope="col" className="text-right">HR</th>
              {!compact && <th scope="col">Trend</th>}
              <th scope="col">Updated</th>
              <th scope="col"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p, i) => {
              const r = risks[p.id];
              const v = latest[p.id];
              if (!r || !v) return null;
              const s = RISK_STYLES[r.level];
              return (
                <tr key={p.id} className="table-row group">
                  <td className="pl-5 pr-2 py-3 font-bold text-slate-400 tabular-nums text-xs w-8">{String(i + 1).padStart(2, '0')}</td>
                  <td className="px-3 py-3">
                    <Link to={`/patients/${p.id}`} className="font-bold text-slate-900 hover:text-teal-700 hover:underline dark:text-slate-100 dark:hover:text-teal-300 rounded" aria-label={`Open patient ${p.id}`}>
                      {p.id}
                    </Link>
                    <span className="block text-[11px] text-slate-400">Age {p.age} · {p.sex === 'M' ? 'Male' : 'Female'}</span>
                  </td>
                  <td className="px-3 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{p.ward} <span className="text-slate-400">· {p.bed}</span></td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <RiskBadge level={r.level} score={r.score} />
                    </div>
                    <div className="mt-1.5 h-1 w-24 rounded-full bg-slate-100 dark:bg-white/10 overflow-hidden" aria-hidden>
                      <div className="h-full rounded-full vg-bar-grow" style={{ width: `${r.score}%`, background: s.hex }} />
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right font-bold tabular-nums">{r.news2}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{Math.round(v.spo2)}<span className="text-slate-400 text-xs">%</span></td>
                  <td className="px-3 py-3 text-right tabular-nums whitespace-nowrap">{Math.round(v.heartRate)} <span className="text-slate-400 text-xs">bpm</span></td>
                  {!compact && <td className="px-3 py-3"><TrendPill trend={r.trend} /></td>}
                  <td className="px-3 py-3">
                    <div className="w-20"><Sparkline data={r.trajectory} color={s.hex} height={26} /></div>
                    <p className="text-[10px] text-slate-400 tabular-nums mt-0.5">{formatTimeAgo(p.updatedAt)}</p>
                  </td>
                  <td className="pl-1 pr-4 py-3 text-right">
                    <Link to={`/patients/${p.id}`} aria-label={`View details for ${p.id}`} className="icon-btn inline-flex opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all"><ChevronRight size={17} aria-hidden /></Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function TriageMatrix({ patients, risks }: { patients: Patient[]; risks: Record<string, RiskSignal> }) {
  const hiW = patients.filter((p) => risks[p.id] && risks[p.id].score >= 65 && risks[p.id].trend === 'worsening');
  const hiS = patients.filter((p) => risks[p.id] && risks[p.id].score >= 65 && risks[p.id].trend !== 'worsening');
  const loW = patients.filter((p) => risks[p.id] && risks[p.id].score < 65 && risks[p.id].trend === 'worsening');
  const loS = patients.filter((p) => risks[p.id] && risks[p.id].score < 65 && risks[p.id].trend !== 'worsening');
  const Cell = ({ title, sub, list, hot }: { title: string; sub: string; list: Patient[]; hot?: boolean }) => (
    <div className={`rounded-2xl border p-3.5 min-h-[118px] transition-all duration-200 hover:-translate-y-0.5 ${hot ? 'border-rose-300/70 bg-gradient-to-br from-rose-50 to-orange-50/60 dark:from-rose-950/40 dark:to-orange-950/20 dark:border-rose-900/60' : 'border-slate-200/70 dark:border-white/[0.07] bg-slate-50/60 dark:bg-white/[0.02] hover:border-teal-300/60'}`}>
      <p className={`text-[11px] font-extrabold uppercase tracking-[0.1em] ${hot ? 'text-rose-700 dark:text-rose-300' : 'text-slate-500'}`}>{title}</p>
      <p className="text-[11px] text-slate-400">{sub}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {list.length === 0 && <span className="text-xs text-slate-400">—</span>}
        {list.map((p) => (
          <Link key={p.id} to={`/patients/${p.id}`}
            className={`text-[11px] font-bold px-2 py-1 rounded-lg border tabular-nums transition-all hover:-translate-y-px ${hot ? 'text-white border-transparent shadow-sm' : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 hover:border-teal-400'}`}
            style={hot ? { background: 'linear-gradient(135deg,#e11d48,#f43f5e)' } : undefined}>
            {p.id} · {risks[p.id].score}
          </Link>
        ))}
      </div>
    </div>
  );
  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2 grid grid-cols-2 text-center">
          <span className="eyebrow">→ Stable / recovering</span><span className="eyebrow">↗ Worsening</span>
        </div>
        <Cell title="Review" sub="High signal · stable" list={hiS} />
        <Cell title="Priority" sub="High signal · worsening" list={hiW} hot />
        <Cell title="Routine" sub="Low signal · stable" list={loS} />
        <Cell title="Monitor" sub="Low signal · worsening" list={loW} />
      </div>
      <p className="text-[11px] text-slate-400 mt-3">Decision-support visualization — review recommended. Bands are not clinically validated.</p>
    </div>
  );
}
