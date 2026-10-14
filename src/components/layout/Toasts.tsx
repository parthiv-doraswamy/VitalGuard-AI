import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useSimulation } from '../../store/useSimulation.ts';
import { formatTimeAgo } from '../../utils/format.ts';

export function Toasts() {
  const { toasts, dismissToast } = useSimulation();
  const visible = toasts.slice(-3);
  return (
    <div className="fixed bottom-4 right-4 space-y-2 z-50 w-[min(370px,calc(100vw-2rem))]" aria-live="polite" aria-label="Notifications">
      {visible.map((t) => {
        const pid = t.patientId ?? null;
        const Icon = t.severity === 'critical' ? AlertTriangle : t.severity === 'info' ? Info : t.severity === 'ok' ? CheckCircle2 : AlertTriangle;
        const iconCls = t.severity === 'critical' ? 'text-rose-500 bg-rose-50 dark:bg-rose-950/60' : t.severity === 'info' ? 'text-cyan-600 bg-cyan-50 dark:bg-cyan-950/60' : t.severity === 'ok' ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-950/60' : 'text-amber-500 bg-amber-50 dark:bg-amber-950/60';
        return (
          <div key={t.id} className="toast-enter card !rounded-2xl p-3.5 flex gap-3" style={{ boxShadow: '0 12px 40px -8px rgba(8,15,36,.28)' }}>
            <span className="absolute left-0 top-3 bottom-3 w-1 rounded-full" style={{ background: t.severity === 'critical' ? '#e11d48' : t.severity === 'info' ? '#0891b2' : '#f59e0b' }} aria-hidden />
            <span className={`h-9 w-9 rounded-xl grid place-items-center shrink-0 ${iconCls}`}><Icon size={17} aria-hidden /></span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-bold">{t.title}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {pid ? <Link to={`/patients/${pid}`} className="font-bold text-blue-700 hover:underline dark:text-blue-300">{pid}</Link> : null}
                {pid ? ' · ' : ''}{t.message} · {formatTimeAgo(t.at)}
              </p>
            </div>
            <button onClick={() => dismissToast(t.id)} aria-label="Dismiss notification" className="icon-btn !p-1.5 self-start"><X size={15} /></button>
          </div>
        );
      })}
    </div>
  );
}
