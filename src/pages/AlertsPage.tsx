import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BellRing, CheckCircle2, ShieldCheck } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader } from '../components/ui/Primitives.tsx';
import { EmptyState } from '../components/ui/States.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { AlertCard } from '../components/alerts/AlertCard.tsx';
import { BackendAlertInbox } from '../components/alerts/BackendAlertInbox.tsx';
import type { AlertStatus } from '../types/index.ts';
const tabs: { key: AlertStatus | 'all'; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'open', label: 'Open' }, { key: 'acknowledged', label: 'Acknowledged' }, { key: 'resolved', label: 'Resolved' },
];
export function AlertsPage() {
  const { alerts, acknowledge, undoAcknowledge, start } = useSimulation();
  const [tab, setTab] = useState<(typeof tabs)[number]['key']>('all');
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
      <BackendAlertInbox />
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
        <Link to="/patients/P-SIM-003" className="btn-ghost !text-[13px] ml-auto">Open P-SIM-003 <ArrowRight size={14} aria-hidden /></Link>
      </div>
      {rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState icon="alert" title="No local demo alerts" hint="The local simulator has no signals in this filter."
            action={<button onClick={start} className="btn-primary">Start Live Simulation</button>} />
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
