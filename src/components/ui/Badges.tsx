import type { RiskLevel } from '../../types/index.ts';
import { RISK_STYLES } from '../../theme/tokens.ts';

export function RiskBadge({ level, score }: { level: RiskLevel; score?: number }) {
  const s = RISK_STYLES[level];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border tabular-nums ${s.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      <span className="capitalize">{level}</span>{score !== undefined ? <span className="opacity-80">· {score}</span> : null}
    </span>
  );
}

export function DemoPill({ label = 'SYNTHETIC' }: { label?: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-[0.08em] bg-slate-900/[0.04] text-slate-500 border border-slate-200/80 dark:bg-white/[0.06] dark:text-slate-400 dark:border-white/10">
      {label}
    </span>
  );
}

export function TrendPill({ trend }: { trend: 'worsening' | 'stable' | 'recovering' }) {
  const map = {
    worsening: { arrow: '↗', cls: 'bg-rose-50 text-rose-700 border-rose-200/70 dark:bg-rose-950/50 dark:text-rose-200 dark:border-rose-900/60' },
    stable: { arrow: '→', cls: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-white/[0.06] dark:text-slate-300 dark:border-white/10' },
    recovering: { arrow: '↘', cls: 'bg-teal-50 text-teal-700 border-teal-200/70 dark:bg-teal-950/50 dark:text-teal-200 dark:border-teal-900/60' },
  } as const;
  const m = map[trend];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border capitalize ${m.cls}`}>
      <span aria-hidden>{m.arrow}</span> {trend}
    </span>
  );
}
