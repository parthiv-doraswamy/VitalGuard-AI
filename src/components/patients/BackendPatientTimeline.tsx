import { useCallback, useEffect, useState } from 'react';
import { Activity, BellRing, Clock3, History, RefreshCw, ShieldCheck } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type TimelineEvent = {
  event_id: string;
  type: 'observation' | 'alert' | 'alert_audit' | string;
  occurred_at: string | null;
  patient_id: string;
  summary: string;
  observation_id?: number;
  risk_score?: number | null;
  risk_level?: string | null;
  model_version?: string | null;
  alert_id?: number;
  severity?: string;
  status?: string;
  action?: string;
  actor?: string;
  demo_only: true;
};
type TimelineResponse = {
  patient_id: string;
  items: TimelineEvent[];
  count: number;
  available_event_count: number;
  limit: number;
  demo_only: true;
  disclaimer: string;
};

const eventIcon = (type: string) => type === 'observation' ? Activity : type === 'alert' ? BellRing : type === 'alert_audit' ? ShieldCheck : History;

export function BackendPatientTimeline({ patientId }: { patientId: string }) {
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/patients/${encodeURIComponent(patientId)}/timeline?limit=30`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`Timeline API returned ${response.status}`);
      setTimeline(await response.json() as TimelineResponse);
      setError('');
    } catch {
      setError('Persisted backend timeline is unavailable. Confirm the latest backend deployment is live.');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { void load(); }, [load]);

  return (
    <section className="card mt-4 p-4 sm:p-5" aria-labelledby="backend-patient-timeline-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><History size={13} /> Persisted backend events</p>
          <h2 id="backend-patient-timeline-heading" className="font-display text-xl font-extrabold mt-1">Observation & alert timeline</h2>
          <p className="text-xs text-slate-500 mt-1">Backend records for {patientId} · newest first</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}
      {loading && !timeline ? <p className="text-sm text-slate-500 mt-4">Loading persisted timeline…</p> :
        timeline && timeline.items.length === 0 ? <p className="text-sm text-slate-500 mt-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">No backend events are stored for this ID. Local dashboard fixtures are separate from backend records.</p> :
        timeline && <ol className="mt-4 space-y-3">
          {timeline.items.map((event) => {
            const Icon = eventIcon(event.type);
            return <li key={event.event_id} className="relative flex gap-3">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"><Icon size={15} /></span>
              <div className="min-w-0 flex-1 border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold">{event.summary}</p>
                  <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-wider text-slate-500">{event.type.replace(/_/g, ' ')}</span>
                </div>
                <p className="text-xs text-slate-500 mt-1 flex items-center gap-1"><Clock3 size={12} />{event.occurred_at ? new Date(event.occurred_at).toLocaleString() : 'Timestamp unavailable'}</p>
                {event.type === 'observation' && <p className="text-xs text-slate-500 mt-1">Score {event.risk_score ?? '—'}/100 · {event.risk_level ?? 'unknown'} · {event.model_version ?? 'model version unavailable'}</p>}
                {event.type === 'alert' && <p className="text-xs text-slate-500 mt-1">Alert #{event.alert_id} · {event.severity ?? 'severity unavailable'} · {event.status ?? 'status unavailable'}</p>}
                {event.type === 'alert_audit' && <p className="text-xs text-slate-500 mt-1">Alert #{event.alert_id} · {event.action ?? 'updated'} · demo actor: {event.actor ?? 'unknown'}</p>}
              </div>
            </li>;
          })}
        </ol>}
      {timeline && <p className="text-[11px] text-slate-400 mt-3">{timeline.count} of {timeline.available_event_count} available events · synthetic data only</p>}
      <p className="text-[11px] text-slate-400 mt-1">Not a regulated medical record or clinical workflow. Never use real patient data.</p>
    </section>
  );
}
