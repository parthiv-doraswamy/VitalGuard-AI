import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldAlert } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type DemoAlert = {
  id: number; patient_id: string; severity: string; status: 'open' | 'acknowledged' | 'resolved';
  title: string; created_at: string | null; acknowledged_at?: string | null; resolved_at?: string | null;
  details?: Record<string, unknown>;
};
type QualityItem = {
  patient_id: string; latest_observation_id: number | null; last_observed_at: string | null;
  age_seconds: number | null; status: 'fresh' | 'stale' | 'incomplete' | 'unknown'; missing_fields: string[];
};
type QualityReport = { items: QualityItem[]; count: number; stale_after_seconds: number; disclaimer: string };
type EvaluationReport = {
  model_version?: string; evaluation_type?: string; sample_count?: number; threshold?: number;
  metrics?: Record<string, number>; confusion_matrix?: { labels: string[]; rows_actual_columns_predicted: number[][] };
  limitations?: string[]; demo_only?: boolean; clinically_validated?: boolean;
};
type AlertResponse = { items: DemoAlert[]; count: number; demo_only: boolean };

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${APP_CONFIG.apiBaseUrl}${path}`, {
    ...init,
    signal: AbortSignal.timeout(8000),
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const message = await response.text().catch(() => '');
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
const when = (value: string | null | undefined) => value ? new Date(value).toLocaleString() : 'Unknown time';
const qualityStyle: Record<QualityItem['status'], string> = {
  fresh: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  stale: 'bg-rose-50 text-rose-800 border-rose-200',
  incomplete: 'bg-amber-50 text-amber-800 border-amber-200',
  unknown: 'bg-slate-100 text-slate-700 border-slate-200',
};

export function BackendPhase567Panel() {
  const [alerts, setAlerts] = useState<DemoAlert[]>([]);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);
  const [status, setStatus] = useState<'all' | DemoAlert['status']>('open');
  const [busy, setBusy] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const query = status === 'all' ? '' : `?status=${status}`;
      const [alertResult, qualityResult, evaluationResult] = await Promise.all([
        apiRequest<AlertResponse>(`/api/v1/alerts${query}&limit=20`.replace('?&', '?')),
        apiRequest<QualityReport>('/api/v1/observations/quality?limit=100'),
        apiRequest<EvaluationReport>('/api/v1/model/evaluation'),
      ]);
      setAlerts(alertResult.items);
      setQuality(qualityResult);
      setEvaluation(evaluationResult);
      setUpdatedAt(new Date().toISOString());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load backend phase data.');
    } finally {
      setBusy(false);
    }
  }, [status]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function transition(alertId: number, action: 'acknowledge' | 'resolve') {
    setActingId(alertId);
    setError('');
    try {
      await apiRequest(`/api/v1/alerts/${alertId}/${action}`, {
        method: 'POST', body: JSON.stringify({ actor: 'demo-operator' }),
      });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Alert update failed.');
    } finally {
      setActingId(null);
    }
  }

  const metrics = evaluation?.metrics;
  return (
    <section className="mt-5 space-y-4" aria-label="Backend monitoring and model transparency">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="eyebrow">Phases 5–7 · Backend-backed monitoring</p>
          <h2 className="text-xl font-bold mt-1">Operations & model transparency</h2>
          <p className="text-sm text-slate-500 mt-1">Persisted alert actions, observation freshness and synthetic evaluation.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={busy} className="btn-secondary inline-flex items-center gap-2">
          <RefreshCw size={14} className={busy ? 'animate-spin' : ''} aria-hidden />{busy ? 'Refreshing…' : 'Refresh backend data'}
        </button>
      </div>
      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Backend data unavailable: {error}</p>}
      <div className="grid xl:grid-cols-2 gap-4 items-start">
        <section className="card p-5" aria-labelledby="backend-alerts-heading">
          <div className="flex items-start justify-between gap-3">
            <div><p className="eyebrow flex items-center gap-1.5"><AlertTriangle size={13} aria-hidden />Phase 5</p><h3 id="backend-alerts-heading" className="text-lg font-bold mt-1">Persisted alert inbox</h3></div>
            <select aria-label="Filter backend alerts" value={status} onChange={(event) => setStatus(event.target.value as typeof status)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:bg-slate-900 dark:border-white/10">
              <option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option><option value="all">All statuses</option>
            </select>
          </div>
          {alerts.length === 0 ? <p className="text-sm text-slate-500 mt-4">No persisted alerts for this filter yet. Run a synthetic prediction or simulator observation to create one.</p> : (
            <ul className="mt-3 space-y-2">
              {alerts.map((alert) => <li key={alert.id} className="rounded-xl border border-slate-200 p-3 dark:border-white/10">
                <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">#{alert.id} · {alert.patient_id}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${alert.severity === 'critical' || alert.severity === 'high' ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{alert.severity}</span><span className="ml-auto text-xs text-slate-500 capitalize">{alert.status}</span></div>
                <p className="font-semibold text-sm mt-2">{alert.title}</p><p className="text-xs text-slate-500 mt-1">Created {when(alert.created_at)}</p>
                {alert.status !== 'resolved' && <div className="mt-3 flex gap-2">
                  {alert.status === 'open' && <button type="button" className="btn-secondary !py-1.5 !text-xs" disabled={actingId !== null} onClick={() => void transition(alert.id, 'acknowledge')}>{actingId === alert.id ? 'Saving…' : 'Acknowledge'}</button>}
                  <button type="button" className="btn-primary !py-1.5 !text-xs" disabled={actingId !== null} onClick={() => void transition(alert.id, 'resolve')}>{actingId === alert.id ? 'Saving…' : 'Resolve'}</button>
                </div>}
              </li>)}
            </ul>
          )}
          <p className="mt-3 text-xs text-slate-500">Changes are saved by the backend with an audit event. This demo actor is not authentication or authorization.</p>
        </section>
        <section className="card p-5" aria-labelledby="quality-heading">
          <p className="eyebrow flex items-center gap-1.5"><Clock3 size={13} aria-hidden />Phase 6</p>
          <h3 id="quality-heading" className="text-lg font-bold mt-1">Observation data quality</h3>
          <p className="text-xs text-slate-500 mt-1">Latest saved observation per patient in the bounded history window.</p>
          {!quality || quality.items.length === 0 ? <p className="text-sm text-slate-500 mt-4">No persisted observations found.</p> : <>
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(['fresh', 'stale', 'incomplete', 'unknown'] as const).map((label) => <div key={label} className="rounded-xl border border-slate-200 p-2.5 dark:border-white/10"><p className="text-xs text-slate-500 capitalize">{label}</p><p className="text-xl font-bold mt-1 tabular-nums">{quality.items.filter((item) => item.status === label).length}</p></div>)}
            </div>
            <ul className="mt-3 space-y-2 max-h-72 overflow-y-auto">
              {quality.items.map((item) => <li key={item.patient_id} className="flex flex-wrap items-start gap-2 rounded-xl border border-slate-200 p-3 dark:border-white/10">
                <div className="min-w-0 flex-1"><p className="font-mono text-xs">{item.patient_id}</p><p className="text-xs text-slate-500 mt-1">{item.age_seconds === null ? 'Age unknown' : `Observed ${Math.floor(item.age_seconds / 60)}m ${item.age_seconds % 60}s ago`} · {when(item.last_observed_at)}</p>{item.missing_fields.length > 0 && <p className="text-xs text-amber-700 mt-1">Missing: {item.missing_fields.join(', ')}</p>}</div>
                <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase ${qualityStyle[item.status]}`}>{item.status}</span>
              </li>)}
            </ul>
          </>}
          <p className="mt-3 text-xs text-amber-800 flex items-start gap-1.5"><ShieldAlert size={13} className="mt-0.5 shrink-0" aria-hidden />Missing or stale readings are unknown, never normal. This endpoint cannot detect a device that has never sent data.</p>
        </section>
      </div>
      <section className="card p-5" aria-labelledby="evaluation-heading">
        <p className="eyebrow flex items-center gap-1.5"><Activity size={13} aria-hidden />Phase 7</p>
        <h3 id="evaluation-heading" className="text-lg font-bold mt-1">Model evaluation transparency</h3>
        <p className="text-xs text-slate-500 mt-1">{evaluation?.evaluation_type ?? 'Loading evaluation protocol…'} · version {evaluation?.model_version ?? '—'} · n={evaluation?.sample_count ?? '—'}</p>
        {metrics && <div className="mt-3 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(metrics).map(([name, value]) => <div key={name} className="rounded-xl border border-slate-200 p-3 dark:border-white/10"><p className="text-xs text-slate-500 uppercase">{name.replaceAll('_', ' ')}</p><p className="text-xl font-bold mt-1 tabular-nums">{(value * 100).toFixed(1)}%</p></div>)}
        </div>}
        {evaluation?.confusion_matrix && <div className="mt-3 overflow-x-auto"><p className="text-sm font-semibold mb-2">Confusion matrix (rows = actual synthetic label; columns = predicted)</p><table className="w-full max-w-sm text-sm border-collapse"><thead><tr><th className="border border-slate-200 p-2"></th>{evaluation.confusion_matrix.labels.map((label) => <th key={label} className="border border-slate-200 p-2">{label.replace('synthetic_', '')}</th>)}</tr></thead><tbody>{evaluation.confusion_matrix.rows_actual_columns_predicted.map((row, index) => <tr key={index}><th className="border border-slate-200 p-2 text-left">{evaluation.confusion_matrix?.labels[index]?.replace('synthetic_', '')}</th>{row.map((cell, column) => <td key={column} className="border border-slate-200 p-2 text-center tabular-nums">{cell}</td>)}</tr>)}</tbody></table></div>}
        {evaluation?.limitations && <ul className="mt-3 list-disc pl-5 text-xs text-slate-500 space-y-1">{evaluation.limitations.map((item) => <li key={item}>{item}</li>)}</ul>}
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2"><ShieldAlert size={14} className="mt-0.5 shrink-0" aria-hidden />Synthetic holdout metrics measure agreement with generated heuristic labels only. They are not clinical accuracy, calibration or safety evidence; this prototype is not for diagnosis, triage or treatment.</p>
      </section>
      {updatedAt && <p className="text-right text-[11px] text-slate-400">Backend data refreshed {when(updatedAt)}</p>}
    </section>
  );
}
