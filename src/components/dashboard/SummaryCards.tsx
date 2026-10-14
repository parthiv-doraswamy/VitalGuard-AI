import { Users, Siren, TrendingUp, BellRing } from 'lucide-react';
import type { Patient, RiskSignal } from '../../types/index.ts';
import { Sparkline } from '../ui/premium.tsx';

export function SummaryCards({ patients, risks, openAlerts }: {
  patients: Patient[]; risks: Record<string, RiskSignal>; openAlerts: number;
}) {
  const vals = Object.values(risks);
  const hi = vals.filter((r) => r.score >= 65).length;
  const wors = vals.filter((r) => r.trend === 'worsening').length;
  const avg = vals.length ? Math.round(vals.reduce((s, r) => s + r.score, 0) / vals.length) : 0;
  const sparkOf = (fn: (r: RiskSignal) => number[]) => vals.slice(0, 8).flatMap(fn).slice(-14);
  const cards = [
    { eyebrow: 'Patients monitored', value: String(patients.length), hint: `${avg} avg risk score`, icon: Users, iconCls: 'text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-300', spark: sparkOf((r) => r.trajectory), color: '#0d9488', ring: false },
    { eyebrow: 'High-risk signals', value: String(hi), hint: 'Score ≥ 65 · needs review', icon: Siren, iconCls: 'text-orange-600 bg-orange-50 dark:bg-orange-950/60 dark:text-orange-300', spark: vals.map((r) => r.score).slice(-12), color: '#ea580c', ring: false },
    { eyebrow: 'Worsening trajectories', value: String(wors), hint: 'Deteriorating trend', icon: TrendingUp, iconCls: 'text-rose-600 bg-rose-50 dark:bg-rose-950/60 dark:text-rose-300', spark: sparkOf((r) => r.trajectory), color: '#e11d48', ring: false },
    { eyebrow: 'Active alerts', value: String(openAlerts), hint: 'Awaiting acknowledgement', icon: BellRing, iconCls: 'text-amber-600 bg-amber-50 dark:bg-amber-950/60 dark:text-amber-300', spark: [2, 3, 2, 4, 3, 5, 4, openAlerts, openAlerts], color: '#d97706', ring: true },
  ];
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 md:gap-4 stagger">
      {cards.map(({ eyebrow, value, hint, icon: Icon, iconCls, spark, color, ring }) => (
        <div key={eyebrow} className="card card-hover p-4 sm:p-5 relative overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-[3px] opacity-70" style={{ background: `linear-gradient(90deg, ${color}, transparent)` }} aria-hidden />
          <div className="flex items-center gap-2.5">
            <span className={`h-9 w-9 rounded-xl grid place-items-center shrink-0 ${iconCls}`}><Icon size={18} aria-hidden /></span>
            <p className="eyebrow leading-tight">{eyebrow}</p>
          </div>
          <div className="flex items-end justify-between gap-2 mt-3">
            <div>
              <p className="metric text-[34px] leading-none">{value}</p>
              <p className="text-xs text-slate-400 mt-1.5">{hint}</p>
            </div>
            {ring ? (
              <span className="relative grid place-items-center h-12 w-12 shrink-0" role="img" aria-label={`${value} active alerts`}>
                <svg viewBox="0 0 48 48" className="h-12 w-12 -rotate-90" aria-hidden>
                  <circle cx="24" cy="24" r="19" fill="none" className="stroke-slate-100 dark:stroke-slate-800" strokeWidth="6" />
                  <circle cx="24" cy="24" r="19" fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
                    strokeDasharray={`${(Math.min(12, Number(value)) / 12) * 2 * Math.PI * 19} ${2 * Math.PI * 19}`} />
                </svg>
                <span className={`absolute h-2 w-2 rounded-full ${Number(value) > 0 ? 'bg-amber-400 pulse-dot' : 'bg-slate-300'}`} aria-hidden />
              </span>
            ) : (
              <div className="w-24 shrink-0 opacity-90"><Sparkline data={spark} color={color} height={38} /></div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
