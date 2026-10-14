import { useCallback, useEffect, useState } from 'react';
import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, RefreshCw, TrendingUp } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type Trend = {
  metric: string;
  sample_count: number;
  status?: string;
  first_value?: number;
  latest_value?: number;
  absolute_change?: number;
  slope_per_observation?: number;
  direction?: 'increasing' | 'decreasing' | 'stable';
};
type TrendResponse = {
  patient_id: string;
  observation_count: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
  trends: Trend[];
  method: string;
  interpretation: string;
  demo_only: true;
  clinically_validated: false;
};

const labels: Record<string, string> = {
  heart_rate: 'Heart rate', spo2: 'SpO₂', systolic_bp: 'Systolic BP',
  temperature: 'Temperature', respiratory_rate: 'Respiratory rate', risk_score: 'Synthetic model score',
};
const unit: Record<string, string> = {
  heart_rate: 'bpm', spo2: '%', systolic_bp: 'mmHg', temperature: '°C',
  respiratory_rate: '/min', risk_score: '/100',
};

export function BackendObservationTrends({ patientId }: { patientId: string }) {
  const [data, setData] = useState<TrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ patient_id: patientId, limit: '50' });
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations/trends?${params}`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`Trend API returned ${response.status}`);
      setData(await response.json() as TrendResponse);
      setError('');
    } catch {
      setError('Persisted trend analytics are unavailable. Confirm the latest backend deployment is live.');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { void load(); }, [load]);

  return (
    <section className="card mt-4 p-4 sm:p-5" aria-labelledby="backend-trends-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><TrendingUp size={13} /> Descriptive history</p>
          <h2 id="backend-trends-heading" className="font-display text-xl font-extrabold mt-1">Persisted observation trends</h2>
          <p className="text-xs text-slate-500 mt-1">Stored backend observations for {patientId} · no future prediction</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}
      {loading && !data ? <p className="text-sm text-slate-500 mt-4">Loading stored trend summaries…</p> :
        data && data.observation_count < 2 ? <p className="text-sm text-slate-500 mt-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">At least two persisted observations are needed to summarize a trend. Current records: {data.observation_count}.</p> :
        data && <div className="mt-4 grid sm:grid-cols-2 xl:grid-cols-3 gap-2">
          {data.trends.map((trend) => {
            const Icon = trend.direction === 'increasing' ? ArrowUpRight : trend.direction === 'decreasing' ? ArrowDownRight : ArrowRight;
            const tone = trend.direction === 'increasing' ? 'text-amber-700 dark:text-amber-300' : trend.direction === 'decreasing' ? 'text-teal-700 dark:text-teal-300' : 'text-slate-500';
            return <article key={trend.metric} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <p className="text-xs text-slate-500">{labels[trend.metric] ?? trend.metric}</p>
              {trend.status === 'insufficient_data' ? <p className="text-sm mt-2 text-slate-500">Insufficient data</p> : <>
                <p className="metric text-xl mt-1">{trend.latest_value}<span className="text-xs font-normal text-slate-500"> {unit[trend.metric] ?? ''}</span></p>
                <p className={`mt-1 text-xs flex items-center gap-1 ${tone}`}><Icon size={13} />{trend.direction} · change {trend.absolute_change! > 0 ? '+' : ''}{trend.absolute_change}</p>
                <p className="text-[10px] text-slate-400 mt-1">From {trend.first_value} · {trend.sample_count} observations</p>
              </>}
            </article>;
          })}
        </div>}
      {data && <p className="text-[11px] text-slate-400 mt-3 flex items-start gap-1.5"><Activity size={12} className="mt-0.5 shrink-0" />{data.interpretation} Method: {data.method}.</p>}
      <p className="text-[11px] text-slate-400 mt-1">Direction describes stored values only. It is not a forecast or clinical interpretation; synthetic data only.</p>
    </section>
  );
}
