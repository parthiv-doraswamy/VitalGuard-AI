import { useCallback, useEffect, useState } from 'react';
import { Clock3, RefreshCw, History } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type RecordItem = {
  id: number;
  patient_id: string;
  created_at: string;
  model_version: string;
  inputs: Record<string, number>;
  prediction: { risk_score: number; risk_level: string; model_version: string };
};
type HistoryResponse = { items: RecordItem[]; count: number; limit: number; next_before_id: number | null; demo_only: true; disclaimer: string };

export function BackendObservationHistory() {
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [patientId, setPatientId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '25' });
      if (patientId.trim()) params.set('patient_id', patientId.trim());
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/observations?${params.toString()}`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error('History API unavailable');
      setData(await response.json() as HistoryResponse);
      setError('');
    } catch {
      setError('Backend prediction history is unavailable. Check the API deployment and storage health.');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { void load(); }, [load]);

  return (
    <section className="card mt-4 p-4 sm:p-5" aria-labelledby="backend-history-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><History size={13} /> Persisted backend records</p>
          <h2 id="backend-history-heading" className="font-display text-xl font-extrabold mt-1">Prediction history</h2>
          <p className="text-xs text-slate-500 mt-1">Stored synthetic API predictions · newest first</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <form className="mt-3 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); void load(); }}>
        <input className="input-field min-w-[200px] flex-1" aria-label="Filter history by demo patient ID" placeholder="Filter by demo patient ID" value={patientId} onChange={(event) => setPatientId(event.target.value)} maxLength={64} />
        <button className="btn-secondary" type="submit">Apply filter</button>
        {patientId && <button className="btn-ghost" type="button" onClick={() => setPatientId('')}>Clear</button>}
      </form>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}
      {data && <>
        <p className="text-xs text-slate-500 mt-3">{data.count} record(s) returned · limit {data.limit}</p>
        {data.items.length ? <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead><tr className="table-head"><th>Record</th><th>Patient</th><th>Score</th><th>Level</th><th>Model</th><th>Observed at</th></tr></thead>
            <tbody>{data.items.map((item) => <tr key={item.id} className="table-row">
              <td className="px-3 py-3 text-slate-500">#{item.id}</td>
              <td className="px-3 py-3 font-semibold">{item.patient_id}</td>
              <td className="px-3 py-3 font-bold tabular-nums">{item.prediction.risk_score}/100</td>
              <td className="px-3 py-3"><span className={`rounded-md px-2 py-1 text-[10px] uppercase font-bold ${item.prediction.risk_level === 'critical' || item.prediction.risk_level === 'high' ? 'bg-rose-50 text-rose-700' : item.prediction.risk_level === 'moderate' ? 'bg-amber-50 text-amber-700' : 'bg-teal-50 text-teal-700'}`}>{item.prediction.risk_level}</span></td>
              <td className="px-3 py-3 text-xs text-slate-500">{item.model_version}</td>
              <td className="px-3 py-3 text-xs text-slate-500 whitespace-nowrap"><Clock3 size={12} className="inline mr-1" />{new Date(item.created_at).toLocaleString()}</td>
            </tr>)}</tbody>
          </table>
        </div> : <p className="text-sm text-slate-500 mt-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">No stored records match this filter. Use the Risk Engine panel in Settings to create a synthetic prediction.</p>}
      </>}
      <p className="mt-3 text-[11px] text-slate-400">Records are synthetic demo observations. This view is not a medical record system.</p>
    </section>
  );
}
