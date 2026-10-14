import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import type { RiskFactor } from '../../types/index.ts';

export function ExplanationPanel({ factors, patientId }: { factors: RiskFactor[]; patientId: string }) {
  const max = Math.max(...factors.map((f) => f.contribution), 0.01);
  const sum = factors.reduce((s, f) => s + (f.direction === 'increases-risk' ? f.contribution : -f.contribution), 0);
  return (
    <div aria-label="AI risk explanation">
      <div className="flex flex-wrap items-start gap-2">
        <div>
          <h3 className="font-display font-bold text-[16px] tracking-tight">Why is the AI risk signal elevated?</h3>
          <p className="text-xs text-slate-500 mt-0.5">Contributing signals for {patientId} · ranked by influence</p>
        </div>
        <span className="ml-auto text-[10px] font-bold tracking-[0.08em] px-2 py-1 rounded-md bg-teal-50 text-teal-700 border border-teal-200/70 dark:bg-teal-950/50 dark:text-teal-200 dark:border-teal-900/60">SIGNAL BREAKDOWN</span>
      </div>
      <ol className="mt-5 space-y-4">
        {factors.map((f, i) => {
          const up = f.direction === 'increases-risk';
          const pct = Math.round((f.contribution / max) * 100);
          const Icon = up ? (f.name.toLowerCase().includes('decline') || f.name.toLowerCase().includes('spo') ? TrendingDown : TrendingUp) : Minus;
          return (
            <li key={f.name} className="flex gap-3 rounded-2xl border border-slate-200/60 dark:border-white/[0.07] bg-slate-50/50 dark:bg-white/[0.02] p-3.5 hover:border-teal-300/60 hover:-translate-y-px transition-all">
              <span className="metric text-xs text-slate-300 dark:text-slate-600 mt-1 w-5 shrink-0">{String(i + 1).padStart(2, '0')}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-bold inline-flex items-center gap-1.5">
                    <Icon size={14} aria-hidden className={up ? 'text-orange-500' : 'text-teal-500'} />
                    {f.name}
                  </p>
                  <p className="text-xs font-bold tabular-nums text-slate-600 dark:text-slate-300">{pct}% influence</p>
                </div>
                <p className="text-xs text-slate-500 mt-0.5 tabular-nums">{f.currentValue} <span className="text-slate-400">· {f.trend}</span></p>
                <div className="mt-2 h-2 rounded-full bg-slate-200/70 dark:bg-white/10 overflow-hidden" role="img" aria-label={`${f.name}: relative contribution ${pct} percent`}>
                  <div className={`h-full rounded-full vg-bar-grow ${up ? '' : '!bg-teal-400'}`}
                    style={up ? { width: `${pct}%`, background: 'linear-gradient(90deg,#0d9488,#0891b2)' } : { width: `${pct}%` }} />
                </div>
                <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">{f.description}</p>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-[11px] leading-relaxed text-slate-400 border-t border-slate-100 dark:border-white/[0.07] pt-3">
        Net directional pressure {sum >= 0 ? '+' : ''}{sum.toFixed(2)} · positive contributions push the signal upward — correlation, not clinical causality.
      </p>
    </div>
  );
}
