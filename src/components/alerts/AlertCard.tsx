import { CheckCheck, Undo2, BellRing, Siren, Info, CheckCircle2, Stethoscope } from 'lucide-react';
import { formatTimeAgo } from '../../utils/format.ts';
import type { AlertItem, AlertSeverity } from '../../types/index.ts';
const SEV = {
  critical: { cls: 'text-white border-transparent', style: { background: 'linear-gradient(135deg,#e11d48,#f43f5e)' }, Icon: Siren },
  high: { cls: 'text-white border-transparent', style: { background: 'linear-gradient(135deg,#ea580c,#f97316)' }, Icon: BellRing },
  moderate: { cls: 'bg-amber-100 text-amber-800 border border-amber-200', style: undefined, Icon: BellRing },
  info: { cls: 'bg-cyan-50 text-cyan-800 border border-cyan-200 dark:bg-cyan-950/50 dark:text-cyan-200 dark:border-cyan-900/60', style: undefined, Icon: Info },
} as const;
export function AlertCard({ a, onAck, onReopen }: { a: AlertItem; onAck: () => void; onReopen: () => void }) {
  const sev: AlertSeverity = a.severity;
  const entry = SEV[sev];
  const { cls, Icon } = entry;
  return (
    <article className="card card-hover p-5 relative overflow-hidden">
      <span className="absolute left-0 top-0 bottom-0 w-1" style={{ background: sev === 'critical' ? '#e11d48' : sev === 'high' ? '#ea580c' : sev === 'moderate' ? '#d97706' : '#0891b2' }} aria-hidden />
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 text-[11px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-wide ${cls}`} style={entry.style}>
          <Icon size={13} aria-hidden /> {a.severity}
        </span>
        <span className="font-display font-extrabold">{a.patientId}</span>
        <span className="text-[11px] text-slate-400 tabular-nums">{formatTimeAgo(a.createdAt)}</span>
        <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wide text-slate-400">
          {a.status === 'acknowledged' ? <CheckCircle2 size={13} className="text-teal-500" aria-hidden /> : null}<span className="capitalize">{a.status}</span>
        </span>
      </div>
      <h3 className="font-display font-bold mt-2.5 text-[16px] tracking-tight">{a.title}</h3>
      <div className="mt-3 rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/50 dark:border-white/[0.06] px-4 py-3 flex items-center gap-4">
        <div><p className="eyebrow !text-[10px]">Risk change</p><p className="metric text-lg tabular-nums">{a.riskBefore ?? '—'} → {a.riskAfter ?? '—'}</p></div>
        <div className="h-8 w-px bg-slate-200 dark:bg-white/10" aria-hidden />
        <div><p className="eyebrow !text-[10px]">Status</p><p className="text-sm font-bold capitalize">{a.status}</p></div>
        <div className="ml-auto hidden sm:flex items-center gap-1.5 text-[11px] font-bold text-teal-700 dark:text-teal-300"><Stethoscope size={13} aria-hidden />Review recommended</div>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-300 mt-3 leading-relaxed">{a.description}</p>
      <p className="eyebrow !text-[10px] mt-3">Observed contributors</p>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {a.contributors.map((c: string) => <li key={c} className="px-2 py-1 rounded-lg bg-slate-900/[0.04] dark:bg-white/[0.06] text-[11px] font-semibold">{c}</li>)}
      </ul>
      <div className="mt-4 flex gap-2">
        {a.status === 'open'
          ? <button onClick={onAck} className="btn-primary !py-2"><CheckCheck size={15} aria-hidden /> Acknowledge</button>
          : <button onClick={onReopen} className="btn-secondary !py-2"><Undo2 size={15} aria-hidden /> Reopen</button>}
      </div>
    </article>
  );
}
