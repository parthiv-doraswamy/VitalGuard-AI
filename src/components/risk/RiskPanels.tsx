import type { RiskSignal } from '../../types/index.ts';
import { RISK_STYLES, TREND_META } from '../../theme/tokens.ts';
import { formatTimeAgo } from '../../utils/format.ts';

export function RiskPanel({ risk, delta }: { risk: RiskSignal; delta?: number }) {
  const s = RISK_STYLES[risk.level];
  const C = 2 * Math.PI * 60;
  const trend = TREND_META[risk.trend];
  return (
    <div aria-label="AI-assisted risk signal">
      <p className="eyebrow">Risk signal</p>
      <div className="flex flex-wrap items-center gap-6 mt-4">
        <div className="relative h-36 w-36 shrink-0" role="img" aria-label={`Risk ${risk.score} of 100, level ${risk.level}`}>
          <svg viewBox="0 0 140 140" className="h-36 w-36 -rotate-90" aria-hidden>
            <circle cx="70" cy="70" r="60" fill="none" className="stroke-slate-100 dark:stroke-slate-800" strokeWidth="11" />
            <circle cx="70" cy="70" r="60" fill="none" strokeWidth="11" strokeLinecap="round" className={s.ring}
              strokeDasharray={`${(risk.score / 100) * C} ${C}`} style={{ transition: 'stroke-dasharray 0.6s ease', filter: `drop-shadow(0 0 6px ${s.hex}66)` }} />
          </svg>
          <div className="absolute inset-0 grid place-items-center text-center">
            <div>
              <p className={`metric text-[36px] leading-none ${s.text}`}>{risk.score}</p>
              <p className="text-[11px] text-slate-400 font-semibold mt-0.5">/ 100</p>
            </div>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <p className={`font-display font-extrabold uppercase tracking-[0.14em] text-sm inline-flex items-center gap-2 ${s.text}`}>
            <span className={`h-2 w-2 rounded-full ${s.dot}`} aria-hidden />{risk.level}
          </p>
          <p className="text-sm mt-2">Signal probability <strong className="tabular-nums">{Math.round(risk.probability * 100)}%</strong></p>
          <p className={`text-xs font-bold mt-1 ${trend.cls}`}>{trend.arrow} {trend.label}{delta !== undefined && delta !== 0 ? ` · ${delta > 0 ? '+' : ''}${delta} in window` : ''}</p>
          <p className="text-[11px] text-slate-400 mt-1 tabular-nums">Updated {formatTimeAgo(risk.updatedAt)}</p>
          <p className="mt-2.5 inline-block text-[10px] font-bold tracking-[0.08em] px-2 py-1 rounded-md bg-slate-900/[0.04] text-slate-500 border border-slate-200/80 dark:bg-white/[0.06] dark:text-slate-300 dark:border-white/10">
            PROTOTYPE SIGNAL · REVIEW RECOMMENDED
          </p>
        </div>
      </div>
    </div>
  );
}

export function News2Panel({ score, compact }: { score: number; compact?: boolean }) {
  const band = score >= 7 ? 'High' : score >= 5 ? 'Medium' : score >= 1 ? 'Low' : 'No alert';
  const cls = score >= 7 ? 'text-rose-600 dark:text-rose-400' : score >= 5 ? 'text-orange-600 dark:text-orange-400' : 'text-teal-700 dark:text-teal-300';
  return (
    <div aria-label="NEWS2 clinical reference score">
      <p className="eyebrow">NEWS2 · Clinical reference</p>
      <div className="flex items-baseline gap-2 mt-2">
        <p className={`metric leading-none ${compact ? 'text-4xl' : 'text-5xl'} ${cls}`}>{score}</p>
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">{band}</span>
      </div>
      <div className="mt-3 flex gap-1.5" aria-hidden>
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full ${i < score ? (score >= 7 ? 'bg-rose-400' : score >= 5 ? 'bg-orange-400' : 'bg-teal-400') : 'bg-slate-100 dark:bg-white/10'}`} />
        ))}
      </div>
      <p className="text-xs text-slate-500 mt-3 leading-relaxed">Displayed as a clinical reference alongside the prototype signal. The prototype does not replace NEWS2.</p>
    </div>
  );
}
