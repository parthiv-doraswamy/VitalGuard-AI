import { useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, Clock3, Database, RefreshCw, Send } from 'lucide-react';
import { api, type ObservationHistory, type RiskPredictionResult } from '../../services/api.ts';

const sampleInput = {
  patient_id: 'DEMO-WEB-001',
  age: 58,
  heart_rate: 104,
  spo2: 94,
  systolic_bp: 112,
  diastolic_bp: 74,
  temperature: 37.6,
  respiratory_rate: 21,
};

const riskStyle: Record<RiskPredictionResult['risk_level'], string> = {
  low: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  moderate: 'border-amber-200 bg-amber-50 text-amber-800',
  high: 'border-orange-200 bg-orange-50 text-orange-800',
  critical: 'border-rose-200 bg-rose-50 text-rose-800',
};

export function RiskEnginePanel() {
  const [prediction, setPrediction] = useState<RiskPredictionResult | null>(null);
  const [history, setHistory] = useState<ObservationHistory | null>(null);
  const [busy, setBusy] = useState<'health' | 'predict' | 'history' | null>(null);
  const [connection, setConnection] = useState<'unknown' | 'online' | 'offline'>('unknown');
  const [error, setError] = useState('');

  async function checkHealth() {
    setBusy('health');
    setError('');
    try {
      await api.health();
      setConnection('online');
    } catch {
      setConnection('offline');
      setError('The risk API could not be reached. It may still be deploying or waking from sleep.');
    } finally {
      setBusy(null);
    }
  }

  async function runPrediction() {
    setBusy('predict');
    setError('');
    try {
      const result = await api.predictRisk(sampleInput);
      setPrediction(result);
      setConnection('online');
      const records = await api.listObservations(sampleInput.patient_id, 5);
      setHistory(records);
    } catch {
      setConnection('offline');
      setError('Prediction failed. Check that the backend deployment is live and its logs contain no startup errors.');
    } finally {
      setBusy(null);
    }
  }

  async function loadHistory() {
    setBusy('history');
    setError('');
    try {
      setHistory(await api.listObservations(undefined, 10));
      setConnection('online');
    } catch {
      setConnection('offline');
      setError('Could not load prediction history from the API.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card p-5 sm:p-6" aria-labelledby="risk-engine-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><Activity size={13} aria-hidden />Phase 4 · Backend integration</p>
          <h2 id="risk-engine-heading" className="text-lg font-bold mt-1">Synthetic risk engine</h2>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">Send a fixed, fictional observation to the FastAPI model and inspect the saved result. This does not use the dashboard’s local patient data.</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${connection === 'online' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : connection === 'offline' ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
          {connection === 'online' ? <CheckCircle2 size={13} /> : connection === 'offline' ? <AlertCircle size={13} /> : <Database size={13} />}
          {connection === 'online' ? 'API reachable' : connection === 'offline' ? 'API unavailable' : 'Not checked'}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          ['Demo patient', sampleInput.patient_id],
          ['Heart rate', `${sampleInput.heart_rate} bpm`],
          ['SpO₂', `${sampleInput.spo2}%`],
          ['Respiratory rate', `${sampleInput.respiratory_rate}/min`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200/80 dark:border-white/10 p-3 min-w-0">
            <p className="text-[11px] text-slate-500">{label}</p>
            <p className="mt-1 text-sm font-semibold truncate">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="btn-primary inline-flex items-center gap-2" onClick={runPrediction} disabled={busy !== null}>
          <Send size={14} aria-hidden />{busy === 'predict' ? 'Running prediction…' : 'Run demo prediction'}
        </button>
        <button type="button" className="tab-btn tab-off inline-flex items-center gap-2" onClick={checkHealth} disabled={busy !== null}>
          <Activity size={14} aria-hidden />{busy === 'health' ? 'Checking…' : 'Check API'}
        </button>
        <button type="button" className="tab-btn tab-off inline-flex items-center gap-2" onClick={loadHistory} disabled={busy !== null}>
          <RefreshCw size={14} aria-hidden />{busy === 'history' ? 'Loading…' : 'Refresh history'}
        </button>
      </div>

      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {prediction && (
        <div className="mt-4 rounded-2xl border border-slate-200 dark:border-white/10 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500">Model output · {prediction.model_version}</p>
              <p className="mt-1 text-3xl font-bold tabular-nums">{prediction.risk_score}<span className="text-base text-slate-500">/100</span></p>
              <p className="text-xs text-slate-500 mt-1">Model probability: {(prediction.model_probability * 100).toFixed(1)}% (synthetic model output, not a clinical probability)</p>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase ${riskStyle[prediction.risk_level]}`}>{prediction.risk_level} demo band</span>
          </div>
          <div className="mt-3">
            <p className="text-sm font-semibold">Configured indicators</p>
            {prediction.factors.length === 0 ? <p className="text-sm text-slate-500 mt-1">No configured indicators returned.</p> : (
              <ul className="mt-2 space-y-2">
                {prediction.factors.map((factor) => (
                  <li key={factor.feature} className="text-sm border-l-2 border-teal-500 pl-3">
                    <span className="font-semibold">{factor.feature}</span> · {factor.observed_value} — {factor.explanation}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="mt-3 text-xs text-slate-500">Saved observation #{prediction.observation_id ?? 'not returned'}{prediction.created_at ? ` · ${new Date(prediction.created_at).toLocaleString()}` : ''}</p>
          <p className="mt-2 rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-900">{prediction.disclaimer}</p>
        </div>
      )}

      {history && (
        <div className="mt-4">
          <h3 className="text-sm font-bold flex items-center gap-2"><Clock3 size={14} aria-hidden />Saved demo observations ({history.count})</h3>
          {history.items.length === 0 ? <p className="text-sm text-slate-500 mt-2">No saved observations yet. Run a demo prediction first.</p> : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead><tr className="border-b border-slate-200 dark:border-white/10 text-xs text-slate-500"><th className="py-2 pr-3">Record</th><th className="py-2 pr-3">Patient ID</th><th className="py-2 pr-3">Risk score</th><th className="py-2">Saved at</th></tr></thead>
                <tbody>{history.items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-100 dark:border-white/5">
                    <td className="py-2 pr-3">#{item.id}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{item.patient_id}</td>
                    <td className="py-2 pr-3 tabular-nums">{item.prediction.risk_score}/100 · {item.prediction.risk_level}</td>
                    <td className="py-2 text-xs text-slate-500 whitespace-nowrap">{new Date(item.created_at).toLocaleString()}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-slate-500 mt-2">{history.disclaimer}</p>
        </div>
      )}

      <p className="mt-4 text-xs leading-relaxed text-slate-500">Important: this classifier is trained on generated synthetic data with heuristic-generated labels. It is not clinically validated and must not be used for diagnosis, triage, treatment or real patient monitoring.</p>
    </section>
  );
}
