import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Clock3, RefreshCw, Search } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { api, type ObservationRecord } from '../services/api.ts';

const PAGE_SIZE = 25;

function formatDate(value: string | null | undefined) {
  if (!value) return 'Unknown time';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown time' : date.toLocaleString();
}

function riskStyle(level: string) {
  switch (level.toLowerCase()) {
    case 'critical': return 'bg-rose-100 text-rose-800 border-rose-200';
    case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'moderate': return 'bg-amber-100 text-amber-800 border-amber-200';
    default: return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  }
}

export function HistoryPage() {
  const [items, setItems] = useState<ObservationRecord[]>([]);
  const [patientFilter, setPatientFilter] = useState('');
  const [appliedFilter, setAppliedFilter] = useState('');
  const [beforeId, setBeforeId] = useState<number | undefined>();
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [disclaimer, setDisclaimer] = useState('Synthetic demonstration records only; not for clinical use.');

  const load = useCallback(async (filter: string, cursor?: number, append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError('');
    try {
      const result = await api.listObservations(filter || undefined, PAGE_SIZE, cursor);
      setItems((current) => append ? [...current, ...result.items] : result.items);
      setBeforeId(result.next_before_id ?? undefined);
      setHasMore(result.next_before_id !== null);
      setDisclaimer(result.disclaimer);
    } catch {
      setError('Could not load persisted observation history. Check the backend connection and try again.');
      if (!append) setItems([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => { void load(appliedFilter); }, [appliedFilter, load]);

  const applyFilter = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAppliedFilter(patientFilter.trim());
  };

  const refresh = () => { void load(appliedFilter); };

  return (
    <Shell title="Observation history" subtitle="Persisted synthetic model outputs">
      <PageHeader eyebrow="Backend records" title="Observation history"
        subtitle="Review predictions actually stored by the backend. This page is separate from the dashboard's live overview."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'History' }]}
        actions={<button type="button" className="btn-secondary" onClick={refresh} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>} />

      <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        <p className="font-semibold flex items-center gap-2"><AlertTriangle size={15} /> Synthetic demo only</p>
        <p className="mt-1 text-xs leading-relaxed">These records use generated data and heuristic labels. Scores are not clinically validated and must not be used for diagnosis, triage or treatment.</p>
      </div>

      <SectionCard title="Stored predictions" eyebrow="History" hint="Newest records first · backend-persisted observations">
        <form onSubmit={applyFilter} className="mb-4 flex flex-col sm:flex-row gap-2">
          <label className="sr-only" htmlFor="history-patient-filter">Filter by patient ID</label>
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
            <input id="history-patient-filter" className="input-field w-full pl-9" value={patientFilter}
              onChange={(event) => setPatientFilter(event.target.value)} maxLength={64}
              placeholder="Filter by demo patient ID" />
          </div>
          <button className="btn-primary" type="submit"><Search size={14} /> Apply filter</button>
          {appliedFilter && <button className="btn-secondary" type="button" onClick={() => { setPatientFilter(''); setAppliedFilter(''); }}>Clear</button>}
        </form>

        {error && <p role="alert" className="mb-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">{error}</p>}

        {loading ? <div className="py-12 text-center text-sm text-slate-500" role="status">Loading persisted history…</div> :
          items.length === 0 ? <div className="py-12 text-center">
            <Clock3 size={25} className="mx-auto text-slate-400" aria-hidden />
            <p className="mt-2 font-semibold">No persisted observations found</p>
            <p className="mt-1 text-xs text-slate-500">{appliedFilter ? 'Try another patient ID or clear the filter.' : 'Create a synthetic observation through the demo workflow, then refresh this page.'}</p>
          </div> : <>
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 dark:bg-slate-800">{items.length} records loaded</span>
              {appliedFilter && <span>Patient: <strong>{appliedFilter}</strong></span>}
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/70">
                  <tr>
                    <th scope="col" className="px-3 py-3">Observed at</th>
                    <th scope="col" className="px-3 py-3">Patient ID</th>
                    <th scope="col" className="px-3 py-3">Risk score</th>
                    <th scope="col" className="px-3 py-3">Risk level</th>
                    <th scope="col" className="px-3 py-3">Vitals snapshot</th>
                    <th scope="col" className="px-3 py-3">Model version</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {items.map((item) => <tr key={item.id} className="align-top hover:bg-slate-50/80 dark:hover:bg-white/[0.02]">
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">{formatDate(item.created_at)}</td>
                    <td className="px-3 py-3 font-semibold break-all">{item.patient_id}</td>
                    <td className="px-3 py-3"><span className="font-display text-lg font-extrabold tabular-nums">{item.prediction.risk_score}<span className="text-xs font-semibold text-slate-400">/100</span></span></td>
                    <td className="px-3 py-3"><span className={`inline-flex rounded-full border px-2 py-1 text-xs font-bold capitalize ${riskStyle(item.prediction.risk_level)}`}>{item.prediction.risk_level}</span></td>
                    <td className="px-3 py-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                      HR {item.inputs.heart_rate} bpm · SpO₂ {item.inputs.spo2}%<br />
                      RR {item.inputs.respiratory_rate}/min · SBP {item.inputs.systolic_bp} mmHg<br />
                      Temp {item.inputs.temperature}°C
                    </td>
                    <td className="px-3 py-3 font-mono text-xs break-all">{item.model_version}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
            {hasMore && <div className="mt-4 flex justify-center">
              <button type="button" className="btn-secondary" disabled={loadingMore} onClick={() => {
                if (beforeId !== undefined) void load(appliedFilter, beforeId, true);
              }}>
                {loadingMore ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                {loadingMore ? 'Loading…' : 'Load older records'}
              </button>
            </div>}
          </>}
        <p className="mt-4 text-[11px] text-slate-400">{disclaimer}</p>
      </SectionCard>
    </Shell>
  );
}
