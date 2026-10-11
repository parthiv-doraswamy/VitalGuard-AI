import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldAlert } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';
import { authorizedFetch } from '../../services/authenticatedFetch.ts';

type QualityItem = {
  patient_id: string;
  latest_observation_id: number | null;
  last_observed_at: string | null;
  age_seconds: number | null;
  status: 'fresh' | 'stale' | 'incomplete' | 'unknown';
  missing_fields: string[];
};
type QualityResponse = {
  items: QualityItem[];
  count: number;
  stale_after_seconds: number;
  demo_only: true;
  disclaimer: string;
};

function ageLabel(seconds: number | null) {
  if (seconds === null) return 'Timestamp unavailable';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function DataQualityPanel() {
  const [data, setData] = useState<QualityResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await authorizedFetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations/quality?stale_after_seconds=300&limit=100`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setData(await response.json() as QualityResponse);
      setError('');
    } catch {
      setError('Data quality endpoint is not available yet. Check that the latest backend phase is deployed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  const stale = data?.items.filter((item) => item.status === 'stale').length ?? 0;
  const incomplete = data?.items.filter((item) => item.status === 'incomplete' || item.status === 'unknown').length ?? 0;
  const fresh = data?.items.filter((item) => item.status === 'fresh').length ?? 0;

  return (
    <section className="card mt-4 p-4 sm:p-5" aria-labelledby="data-quality-heading">
      <div className="flex flex-wrap justify-between items-start gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><ShieldAlert size={13} /> Feed integrity</p>
          <h2 id="data-quality-heading" className="font-display text-xl font-extrabold mt-1">Observation data quality</h2>
          <p className="text-xs text-slate-500 mt-1">Backend records · freshness threshold 5 minutes · refreshes every 30 seconds</p>
        </div>
        <button className="btn-secondary" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}
      {data && <>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-teal-50 dark:bg-teal-950/40 p-3"><p className="text-xs text-teal-700 dark:text-teal-300 flex items-center gap-1"><CheckCircle2 size={13} /> Fresh</p><p className="metric text-2xl mt-1">{fresh}</p></div>
          <div className="rounded-xl bg-rose-50 dark:bg-rose-950/40 p-3"><p className="text-xs text-rose-700 dark:text-rose-300 flex items-center gap-1"><Clock3 size={13} /> Stale</p><p className="metric text-2xl mt-1">{stale}</p></div>
          <div className="rounded-xl bg-amber-50 dark:bg-amber-950/40 p-3"><p className="text-xs text-amber-700 dark:text-amber-300 flex items-center gap-1"><AlertTriangle size={13} /> Incomplete / unknown</p><p className="metric text-2xl mt-1">{incomplete}</p></div>
        </div>
        {data.items.length > 0 ? <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="table-head"><th>Demo patient</th><th>Feed status</th><th>Last observation</th><th>Missing fields</th></tr></thead>
            <tbody>{data.items.slice(0, 8).map((item) => <tr className="table-row" key={item.patient_id}>
              <td className="px-3 py-3 font-semibold">{item.patient_id}</td>
              <td className="px-3 py-3"><span className={`rounded-md px-2 py-1 text-[10px] uppercase tracking-wider font-bold ${item.status === 'fresh' ? 'bg-teal-50 text-teal-700' : item.status === 'stale' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'}`}>{item.status}</span></td>
              <td className="px-3 py-3 text-slate-500">{ageLabel(item.age_seconds)}</td>
              <td className="px-3 py-3 text-slate-500">{item.missing_fields.length ? item.missing_fields.join(', ') : '—'}</td>
            </tr>)}</tbody>
          </table>
        </div> : <p className="text-sm text-slate-500 mt-4">No persisted observations in the backend history window yet.</p>}
      </>}
      <p className="mt-3 text-[11px] text-slate-400">Stale or missing data is unknown, not normal. This panel evaluates persisted synthetic records only and cannot verify device connectivity.</p>
    </section>
  );
}
