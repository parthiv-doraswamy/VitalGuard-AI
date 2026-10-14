import { useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, FlaskConical, LoaderCircle } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type Vitals = {
  patient_id: string;
  age: number;
  heart_rate: number;
  spo2: number;
  systolic_bp: number;
  diastolic_bp: number;
  temperature: number;
  respiratory_rate: number;
};
type Contribution = {
  feature: string;
  observed_value: number;
  standardized_log_odds_contribution: number;
  direction: string;
  method: string;
};
type Explanation = {
  patient_id: string;
  model_version: string;
  risk_score: number;
  contributions: Contribution[];
  method: string;
  caveat: string;
  demo_only: true;
};

const initial: Vitals = {
  patient_id: 'DEMO-EXPLAIN-001', age: 58, heart_rate: 82, spo2: 98,
  systolic_bp: 122, diastolic_bp: 78, temperature: 37, respiratory_rate: 16,
};
const fields: Array<{ key: Exclude<keyof Vitals, 'patient_id'>; label: string; unit: string; min: number; max: number; step?: number }> = [
  { key: 'age', label: 'Age', unit: 'years', min: 18, max: 110 },
  { key: 'heart_rate', label: 'Heart rate', unit: 'bpm', min: 20, max: 250 },
  { key: 'spo2', label: 'SpO₂', unit: '%', min: 50, max: 100 },
  { key: 'systolic_bp', label: 'Systolic BP', unit: 'mmHg', min: 50, max: 280 },
  { key: 'diastolic_bp', label: 'Diastolic BP', unit: 'mmHg', min: 20, max: 180 },
  { key: 'temperature', label: 'Temperature', unit: '°C', min: 30, max: 45, step: 0.1 },
  { key: 'respiratory_rate', label: 'Respiratory rate', unit: '/min', min: 3, max: 70 },
];

export function ExplainabilityWorkbench() {
  const [vitals, setVitals] = useState<Vitals>(initial);
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const run = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (vitals.diastolic_bp >= vitals.systolic_bp) {
      setError('Diastolic blood pressure must be lower than systolic blood pressure.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/risk/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(vitals),
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult(await response.json() as Explanation);
    } catch {
      setError('Could not reach the model explanation endpoint. Ensure the latest backend deployment is live.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card p-4 sm:p-5" aria-labelledby="explainability-workbench-heading">
      <div>
        <p className="eyebrow flex items-center gap-1.5"><FlaskConical size={13} /> Model transparency</p>
        <h2 id="explainability-workbench-heading" className="font-display text-xl font-extrabold mt-1">Risk contribution workbench</h2>
        <p className="text-xs text-slate-500 mt-1">Enter synthetic vitals to inspect model coefficient contributions. This does not save an observation.</p>
      </div>
      <form onSubmit={run} className="mt-4">
        <label className="block text-xs font-semibold text-slate-500 mb-1.5" htmlFor="explain-patient-id">Demo patient label</label>
        <input id="explain-patient-id" className="input-field w-full" maxLength={64} required value={vitals.patient_id}
          onChange={(e) => setVitals((current) => ({ ...current, patient_id: e.target.value }))} />
        <div className="mt-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {fields.map((field) => <label key={field.key} className="block">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{field.label} <span className="font-normal text-slate-400">({field.unit})</span></span>
            <input className="input-field w-full mt-1" type="number" min={field.min} max={field.max} step={field.step ?? 1} required
              value={vitals[field.key]} onChange={(e) => setVitals((current) => ({ ...current, [field.key]: Number(e.target.value) }))} />
          </label>)}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? <LoaderCircle size={15} className="animate-spin" /> : <Activity size={15} />}
            {loading ? 'Evaluating…' : 'Explain synthetic score'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => { setVitals(initial); setResult(null); setError(''); }}>Reset example</button>
        </div>
      </form>
      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-200">{error}</p>}
      {result && <div className="mt-4 border-t border-slate-200 dark:border-slate-700 pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3">
            <p className="text-xs text-slate-500">Synthetic model score</p>
            <p className="metric text-3xl">{result.risk_score}<span className="text-sm">/100</span></p>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold">{result.model_version}</p>
            <p className="text-xs text-slate-500 mt-1">Method: {result.method}</p>
          </div>
        </div>
        <div className="mt-3 space-y-2">
          {result.contributions.map((item) => {
            const positive = item.standardized_log_odds_contribution >= 0;
            const magnitude = Math.min(100, Math.abs(item.standardized_log_odds_contribution) * 20);
            return <div key={item.feature} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span className="font-bold">{item.feature.replace(/_/g, ' ')}</span>
                <span className="tabular-nums text-slate-500">Observed: {item.observed_value} · contribution {item.standardized_log_odds_contribution.toFixed(3)}</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div className={`h-full rounded-full ${positive ? 'bg-rose-500' : 'bg-teal-500'}`} style={{ width: `${magnitude}%` }} />
              </div>
              <p className={`mt-1.5 text-xs flex items-center gap-1 ${positive ? 'text-rose-600 dark:text-rose-300' : 'text-teal-700 dark:text-teal-300'}`}>
                {positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                {positive ? 'Moves model log-odds toward the synthetic positive class' : 'Moves model log-odds toward the synthetic negative class'}
              </p>
            </div>;
          })}
        </div>
        <p className="mt-3 text-xs text-amber-700 dark:text-amber-300 flex items-start gap-1.5"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{result.caveat} Contributions are not SHAP, causal effects, or clinical guidance.</p>
      </div>}
      <p className="mt-3 text-[11px] text-slate-400">Use synthetic examples only. The model was trained on generated heuristic labels and is not clinically validated.</p>
    </section>
  );
}
