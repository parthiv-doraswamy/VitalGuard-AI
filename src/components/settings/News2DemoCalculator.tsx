import { useState } from 'react';
import { AlertTriangle, Calculator, LoaderCircle } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type FormValues = {
  patient_id: string;
  respiratory_rate: number;
  spo2: number;
  systolic_bp: number;
  heart_rate: number;
  temperature: number;
  consciousness: 'alert' | 'new_confusion' | 'voice' | 'pain' | 'unresponsive';
  supplemental_oxygen: boolean;
  spo2_scale: 1 | 2;
  scale2_authorized: boolean;
};
type ScoreResult = {
  score_name: string;
  score_version: string;
  parameter_scores: Record<string, number>;
  total_score: number;
  spo2_scale: number;
  supplemental_oxygen: boolean;
  demo_only: true;
  clinically_validated_implementation: false;
  disclaimer: string;
};

const defaults: FormValues = {
  patient_id: 'DEMO-NEWS2-001', respiratory_rate: 16, spo2: 98, systolic_bp: 120,
  heart_rate: 80, temperature: 37, consciousness: 'alert',
  supplemental_oxygen: false, spo2_scale: 1, scale2_authorized: false,
};
const numberFields: Array<{ key: 'respiratory_rate' | 'spo2' | 'systolic_bp' | 'heart_rate' | 'temperature'; label: string; unit: string; min: number; max: number; step?: number }> = [
  { key: 'respiratory_rate', label: 'Respiratory rate', unit: '/min', min: 1, max: 100 },
  { key: 'spo2', label: 'SpO₂', unit: '%', min: 50, max: 100 },
  { key: 'systolic_bp', label: 'Systolic blood pressure', unit: 'mmHg', min: 20, max: 300 },
  { key: 'heart_rate', label: 'Pulse', unit: 'bpm', min: 1, max: 250 },
  { key: 'temperature', label: 'Temperature', unit: '°C', min: 30, max: 45, step: 0.1 },
];
const labels: Record<string, string> = {
  respiratory_rate: 'Respiratory rate', spo2: 'Oxygen saturation', supplemental_oxygen: 'Supplemental oxygen',
  systolic_bp: 'Systolic blood pressure', heart_rate: 'Pulse', consciousness: 'Consciousness',
  temperature: 'Temperature',
};

export function News2DemoCalculator() {
  const [form, setForm] = useState<FormValues>(defaults);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const calculate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (form.spo2_scale === 2 && !form.scale2_authorized) {
      setError('Scale 2 requires an explicit acknowledgement that it must only be used under a qualified clinician’s direction.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/scores/news2`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
        signal: AbortSignal.timeout(10000),
      });
      const body = await response.json().catch(() => null) as { detail?: string } | ScoreResult | null;
      if (!response.ok) throw new Error((body && 'detail' in body && body.detail) || `API returned ${response.status}`);
      setResult(body as ScoreResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not calculate the demo score. Check backend deployment.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card p-4 sm:p-5" aria-labelledby="news2-demo-heading">
      <p className="eyebrow flex items-center gap-1.5"><Calculator size={13} /> Parameter scoring demo</p>
      <h2 id="news2-demo-heading" className="font-display text-xl font-extrabold mt-1">NEWS2 scoring workbench</h2>
      <p className="text-xs text-slate-500 mt-1">Fictional adult observations only. Returns parameter points; does not issue clinical response advice.</p>
      <form onSubmit={calculate} className="mt-4">
        <label className="block text-xs font-semibold text-slate-500 mb-1.5" htmlFor="news2-patient">Demo label</label>
        <input id="news2-patient" className="input-field w-full" required maxLength={64} value={form.patient_id}
          onChange={(event) => setForm((current) => ({ ...current, patient_id: event.target.value }))} />
        <div className="mt-3 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {numberFields.map((field) => <label key={field.key} className="block">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{field.label} <span className="font-normal text-slate-400">({field.unit})</span></span>
            <input className="input-field w-full mt-1" type="number" min={field.min} max={field.max} step={field.step ?? 1} required
              value={form[field.key]} onChange={(event) => setForm((current) => ({ ...current, [field.key]: Number(event.target.value) }))} />
          </label>)}
          <label className="block">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">Consciousness</span>
            <select className="input-field w-full mt-1" value={form.consciousness} onChange={(event) => setForm((current) => ({ ...current, consciousness: event.target.value as FormValues['consciousness'] }))}>
              <option value="alert">Alert</option><option value="new_confusion">New confusion</option><option value="voice">Responds to voice</option><option value="pain">Responds to pain</option><option value="unresponsive">Unresponsive</option>
            </select>
          </label>
        </div>
        <div className="mt-4 grid sm:grid-cols-2 gap-3">
          <label className="flex items-start gap-2 rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-sm">
            <input type="checkbox" checked={form.supplemental_oxygen} onChange={(event) => setForm((current) => ({ ...current, supplemental_oxygen: event.target.checked }))} className="mt-0.5" />
            <span><strong className="block">Supplemental oxygen</strong><span className="text-xs text-slate-500">Adds the oxygen parameter points in the score specification.</span></span>
          </label>
          <label className="block rounded-xl border border-slate-200 dark:border-slate-700 p-3">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">SpO₂ scoring scale</span>
            <select className="input-field w-full mt-1" value={form.spo2_scale} onChange={(event) => setForm((current) => ({ ...current, spo2_scale: Number(event.target.value) as 1 | 2, scale2_authorized: Number(event.target.value) === 2 ? current.scale2_authorized : false }))}>
              <option value={1}>Scale 1 (default)</option><option value={2}>Scale 2 (restricted)</option>
            </select>
          </label>
        </div>
        {form.spo2_scale === 2 && <label className="mt-3 flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900 p-3 text-sm">
          <input type="checkbox" checked={form.scale2_authorized} onChange={(event) => setForm((current) => ({ ...current, scale2_authorized: event.target.checked }))} className="mt-0.5" />
          <span><strong className="block text-amber-900 dark:text-amber-200">Scale 2 authorization assertion</strong><span className="text-xs text-amber-800 dark:text-amber-300">Only use Scale 2 under a qualified clinician's direction. This checkbox is not proof of authorization.</span></span>
        </label>}
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-primary" type="submit" disabled={loading}>{loading ? <LoaderCircle size={15} className="animate-spin" /> : <Calculator size={15} />}{loading ? 'Calculating…' : 'Calculate demo score'}</button>
          <button className="btn-secondary" type="button" onClick={() => { setForm(defaults); setResult(null); setError(''); }}>Reset</button>
        </div>
      </form>
      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-200">{error}</p>}
      {result && <div className="mt-4 border-t border-slate-200 dark:border-slate-700 pt-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3"><p className="text-xs text-slate-500">Total demo score</p><p className="metric text-3xl">{result.total_score}</p></div>
          <div><p className="text-sm font-bold">{result.score_name}</p><p className="text-xs text-slate-500 mt-1">{result.score_version} · SpO₂ Scale {result.spo2_scale}</p></div>
        </div>
        <div className="mt-3 grid sm:grid-cols-2 gap-2">
          {Object.entries(result.parameter_scores).map(([key, score]) => <div key={key} className="flex justify-between gap-3 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <span className="text-sm">{labels[key] ?? key}</span><span className="font-bold tabular-nums">{score}</span>
          </div>)}
        </div>
        <p className="mt-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 p-3 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-1.5"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{result.disclaimer}</p>
      </div>}
      <p className="text-[11px] text-slate-400 mt-3">Source: Royal College of Physicians NEWS2 chart. This prototype is not approved for clinical use; verify against the official chart and local policy.</p>
    </section>
  );
}
