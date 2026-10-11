import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, Clock3, History, RefreshCw, ShieldAlert, WifiOff } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';
import { useLiveEvents } from '../../services/useLiveEvents.ts';

type BackendAlert = {
  id: number;
  patient_id: string;
  severity: string;
  status: 'open' | 'acknowledged' | 'resolved';
  title: string;
  created_at: string;
  acknowledged_by?: string | null;
  details: Record<string, unknown>;
};
type AlertResponse = { items: BackendAlert[]; count: number; demo_only: true };
type AuditEvent = { id: number; entity_type: string; entity_id: string; action: string; actor: string; created_at: string; details: Record<string, unknown> };
type EscalationPreview = {
  items: Array<{
    alert_id: number;
    severity: string;
    status: string;
    deadline_minutes: number | null;
    elapsed_minutes: number;
    review_due: boolean;
    minutes_until_due: number | null;
    reason: string;
  }>;
  count: number;
  due_count: number;
  policy_version: string;
  demo_only: true;
  notifications_sent: false;
  clinical_policy: false;
};

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  // Attach the operator session token to every protected backend request.
  try {
    const raw = sessionStorage.getItem('vitalguard.operator.session');
    if (raw) {
      const session = JSON.parse(raw) as { token?: string; expiresAt?: number };
      if (session.token && session.expiresAt && session.expiresAt > Date.now()) {
        headers.set('Authorization', 'Bearer ' + session.token);
      } else {
        sessionStorage.removeItem('vitalguard.operator.session');
      }
    }
  } catch {
    sessionStorage.removeItem('vitalguard.operator.session');
  }
  // Avoid unnecessary browser CORS preflights on GET requests.
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${APP_CONFIG.apiBaseUrl}${path}`, {
    ...init,
    headers,
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`Alert API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export function BackendAlertInbox() {
  const { lastEvent, status } = useLiveEvents();
  const [items, setItems] = useState<BackendAlert[]>([]);
  const [filter, setFilter] = useState<'all' | BackendAlert['status']>('all');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [auditByAlert, setAuditByAlert] = useState<Record<number, AuditEvent[]>>({});
  const [auditLoadingId, setAuditLoadingId] = useState<number | null>(null);
  const [escalation, setEscalation] = useState<EscalationPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [result, preview] = await Promise.all([
        apiRequest<AlertResponse>('/api/v1/alerts?limit=100'),
        apiRequest<EscalationPreview>('/api/v1/alerts/escalation-preview?limit=100'),
      ]);
      setItems(result.items);
      setEscalation(preview);
      setError('');
    } catch {
      setError('Backend alert service is unavailable. Check the API deployment and database health.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load, lastEvent]);

  const transition = async (id: number, action: 'acknowledge' | 'resolve') => {
    setBusyId(id);
    try {
      await apiRequest(`/api/v1/alerts/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ actor: 'demo-operator' }),
      });
      await load();
    } catch {
      setError('Could not update this alert. Refresh and try again.');
    } finally {
      setBusyId(null);
    }
  };

  const showAudit = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (auditByAlert[id]) return;
    setAuditLoadingId(id);
    try {
      const result = await apiRequest<{ items: AuditEvent[]; count: number; demo_only: true }>('/api/v1/alerts/' + id + '/audit');
      setAuditByAlert((current) => ({ ...current, [id]: result.items }));
    } catch {
      setError('Could not load the audit trail for alert #' + id + '.');
    } finally {
      setAuditLoadingId(null);
    }
  };

  const filtered = items.filter((item) => filter === 'all' || item.status === filter);
  const count = (status: BackendAlert['status']) => items.filter((item) => item.status === status).length;

  return (
    <section className="card mt-5 p-4 sm:p-5" aria-labelledby="backend-alert-inbox">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><ShieldAlert size={13} /> Persistent backend alerts</p>
          <h2 id="backend-alert-inbox" className="font-display text-xl font-extrabold mt-1">Alert operations inbox</h2>
          <p className="text-xs text-slate-500 mt-1">Synthetic backend alerts · demo operator identity only</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="rounded-lg bg-rose-50 text-rose-700 px-2.5 py-1.5 dark:bg-rose-950/50 dark:text-rose-300">Open {count('open')}</span>
        <span className="rounded-lg bg-amber-50 text-amber-700 px-2.5 py-1.5 dark:bg-amber-950/50 dark:text-amber-300">Acknowledged {count('acknowledged')}</span>
        <span className="rounded-lg bg-teal-50 text-teal-700 px-2.5 py-1.5 dark:bg-teal-950/50 dark:text-teal-300">Resolved {count('resolved')}</span>
        <span className="inline-flex items-center gap-1 text-slate-400 ml-auto">
          {status === 'connected' ? <CheckCircle2 size={13} /> : <WifiOff size={13} />}
          Live channel: {status}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Backend alert filters">
        {(['all', 'open', 'acknowledged', 'resolved'] as const).map((value) => (
          <button key={value} className={`tab-btn ${filter === value ? 'tab-on' : 'tab-off'}`} onClick={() => setFilter(value)}>
            {value === 'all' ? 'All' : value[0].toUpperCase() + value.slice(1)}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-200">{error}</p>}
      {escalation && <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-3" aria-label="Demo alert review deadlines">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-bold flex items-center gap-2"><Clock3 size={15} /> Review deadline preview</p>
          <span className={`rounded-lg px-2.5 py-1.5 text-xs font-bold ${escalation.due_count > 0 ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200' : 'bg-teal-50 text-teal-800 dark:bg-teal-950/40 dark:text-teal-200'}`}>
            {escalation.due_count} due for review
          </span>
        </div>
        <p className="text-xs text-slate-500 mt-1">Based on illustrative demo deadlines; no notifications are sent.</p>
        {escalation.items.filter((item) => item.review_due).length > 0
          ? <ul className="mt-2 space-y-1">{escalation.items.filter((item) => item.review_due).map((item) =>
              <li key={item.alert_id} className="text-xs flex items-start gap-2 text-amber-800 dark:text-amber-200">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <span>Alert #{item.alert_id} · {item.severity} · overdue by {Math.max(0, Math.round(item.elapsed_minutes - (item.deadline_minutes ?? item.elapsed_minutes)))} min</span>
              </li>)}</ul>
          : <p className="text-xs text-slate-500 mt-2">No open alerts currently exceed the demo review deadline.</p>}
        <p className="text-[10px] text-slate-400 mt-2">Policy {escalation.policy_version} · demo only · not clinical guidance.</p>
      </div>}
      {loading && items.length === 0 ? <p className="text-sm text-slate-500 mt-4">Loading persistent alerts…</p> :
        filtered.length === 0 ? <p className="text-sm text-slate-500 mt-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">No backend alerts in this filter. Submit a synthetic prediction with an elevated score to create a demo alert.</p> :
        <div className="mt-3 space-y-2">
          {filtered.map((alert) => (
            <article key={alert.id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">#{alert.id} · {alert.severity}</span>
                  <span className={`text-[10px] uppercase tracking-wider font-bold rounded-md px-2 py-1 ${alert.status === 'open' ? 'bg-rose-50 text-rose-700' : alert.status === 'acknowledged' ? 'bg-amber-50 text-amber-700' : 'bg-teal-50 text-teal-700'}`}>{alert.status}</span>
                </div>
                <p className="font-bold text-sm mt-1">{alert.title}</p>
                <p className="text-xs text-slate-500 mt-1">Patient {alert.patient_id} · {new Date(alert.created_at).toLocaleString()}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-secondary !text-xs" aria-expanded={expandedId === alert.id} onClick={() => void showAudit(alert.id)}>
                  <History size={13} /> Audit trail <ChevronDown size={13} className={expandedId === alert.id ? 'rotate-180' : ''} />
                </button>
                {alert.status === 'open' && <button className="btn-secondary !text-xs" disabled={busyId === alert.id} onClick={() => void transition(alert.id, 'acknowledge')}>Acknowledge</button>}
                {alert.status !== 'resolved' && <button className="btn-primary !text-xs" disabled={busyId === alert.id} onClick={() => void transition(alert.id, 'resolve')}>Resolve</button>}
              </div>
              {expandedId === alert.id && <div className="w-full basis-full rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3">
                <p className="text-xs font-bold flex items-center gap-1.5"><History size={13} /> Alert audit timeline</p>
                {auditLoadingId === alert.id ? <p className="text-xs text-slate-500 mt-2">Loading audit events…</p> :
                  (auditByAlert[alert.id] ?? []).length === 0 ? <p className="text-xs text-slate-500 mt-2">No audit events returned.</p> :
                  <ol className="mt-2 space-y-2">
                    {(auditByAlert[alert.id] ?? []).map((event) => <li key={event.id} className="border-l-2 border-teal-500 pl-3 py-0.5">
                      <p className="text-xs font-semibold capitalize">{event.action.replace(/_/g, ' ')}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">{event.actor} · {new Date(event.created_at).toLocaleString()}</p>
                    </li>)}
                  </ol>}
                <p className="text-[10px] text-slate-400 mt-2">Demo audit only; the actor label is not verified identity.</p>
              </div>}
            </article>
          ))}
        </div>
      }
      <p className="text-[11px] text-slate-400 mt-3">For demonstration only. This inbox does not authenticate staff or provide clinical alarm monitoring.</p>
    </section>
  );
}
