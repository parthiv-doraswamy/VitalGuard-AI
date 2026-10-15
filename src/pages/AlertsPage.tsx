import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { reconcilePush, type PushState } from '../services/notifications.ts';
import { ArrowRight, BellRing, CheckCircle2, ShieldCheck } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader } from '../components/ui/Primitives.tsx';
import { EmptyState } from '../components/ui/States.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { useScope } from '../store/useScope.ts';
import { useMonitoring } from '../store/useMonitoring.ts';
import { AlertCard } from '../components/alerts/AlertCard.tsx';
import { BackendAlertInbox } from '../components/alerts/BackendAlertInbox.tsx';
import type { AlertStatus } from '../types/index.ts';
const tabs: { key: AlertStatus | 'all'; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'open', label: 'Open' }, { key: 'acknowledged', label: 'Acknowledged' }, { key: 'resolved', label: 'Resolved' },
];
export function AlertsPage() {
  const { acknowledge, undoAcknowledge, alertActionError } = useSimulation();
  const monitoring = useMonitoring();
  const { alerts } = useScope();
  const [tab, setTab] = useState<(typeof tabs)[number]['key']>('all');
  const [params] = useSearchParams();
  const highlightId = Number(params.get('alert')) || null;
  const [push, setPush] = useState<PushState | null>(null);
  useEffect(() => { reconcilePush().then(setPush).catch(() => setPush({ kind: 'off' })); }, []);
  const counts = useMemo(() => ({
    open: alerts.filter((a) => a.status === 'open').length,
    ack: alerts.filter((a) => a.status === 'acknowledged').length,
    res: alerts.filter((a) => a.status === 'resolved').length,
  }), [alerts]);
  const rows = alerts.filter((a) => tab === 'all' || a.status === tab);
  return (
    <Shell title="Alert Center" subtitle="Review signals · acknowledgement required">
      <PageHeader eyebrow="Safety signals" title="Alerts"
        subtitle="Prioritized review signals with observed contributors. No treatment advice."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Alerts' }]} />
      {push && push.kind !== 'on' && (
        <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/50 dark:border-slate-700 dark:text-slate-300" data-testid="push-fallback">
          Push notifications are off on this device. New backend alerts appear here and in the live panel while VitalGuard is open.{' '}
          <Link to="/settings" className="font-semibold text-teal-700 hover:underline">Notification settings</Link>
        </p>
      )}
      <BackendAlertInbox highlightId={highlightId} />
      <div className="mt-6 grid grid-cols-3 gap-3 md:gap-4 stagger">
        {[
          { l: 'Local demo active', v: counts.open, h: 'Requires review', icon: BellRing, cls: 'text-rose-600 bg-rose-50 dark:bg-rose-950/60 dark:text-rose-300' },
          { l: 'Local acknowledged', v: counts.ack, h: 'Under review', icon: ShieldCheck, cls: 'text-amber-600 bg-amber-50 dark:bg-amber-950/60 dark:text-amber-300' },
          { l: 'Local resolved', v: counts.res, h: 'Closed items', icon: CheckCircle2, cls: 'text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-300' },
        ].map(({ l, v, h, icon: Icon, cls }) => (
          <div key={l} className="card card-hover p-4 sm:p-5"><p className="eyebrow flex items-center gap-1.5"><span className={`h-6 w-6 rounded-lg grid place-items-center ${cls}`}><Icon size={13} aria-hidden /></span>{l}</p><p className="metric text-3xl mt-2 tabular-nums">{v}</p><p className="text-[11px] text-slate-400 mt-0.5">{h}</p></div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Local demo alert status filter">
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)} className={`tab-btn ${tab === t.key ? 'tab-on' : 'tab-off'}`}>{t.label}</button>
        ))}
        <Link to="/patients" className="btn-ghost !text-[13px] ml-auto">Open patients <ArrowRight size={14} aria-hidden /></Link>
      </div>
      {alertActionError && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{alertActionError}</p>}
      {rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState icon="alert" title="No alerts in this filter" hint={monitoring.canControl ? 'Start live monitoring to stream vitals and raise alerts.' : 'Alerts for your patients appear here as soon as the live stream raises them.'}
            action={monitoring.canControl && !monitoring.running ? <button onClick={monitoring.start} className="btn-primary">Start live monitoring</button> : undefined} />
        </div>
      ) : (
        <div className="mt-4 grid xl:grid-cols-2 gap-3 items-start">
          {rows.map((a) => (
            <div key={a.id}>
              <AlertCard a={a} onAck={() => acknowledge(a.id)} onReopen={() => undoAcknowledge(a.id)} />
              <Link to={`/patients/${a.patientId}`} className="sr-only">Open {a.patientId}</Link>
            </div>
          ))}
        </div>
      )}
    </Shell>
  );
}
