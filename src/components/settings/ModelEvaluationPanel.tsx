import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, RefreshCw, Scale } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

type Evaluation = {
  model_version: string;
  evaluation_type: string;
  sample_count: number;
  positive_label_definition: string;
  threshold: number;
  metrics: Record<string, number>;
  confusion_matrix: { labels: string[]; rows_actual_columns_predicted: number[][] };
  limitations: string[];
  demo_only: true;
  clinically_validated: false;
};

export function ModelEvaluationPanel() {
  const [report, setReport] = useState<Evaluation | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/model/evaluation`, { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('Evaluation endpoint unavailable');
      setReport(await response.json() as Evaluation);
      setError('');
    } catch {
      setError('Model evaluation endpoint is not available yet. Check the backend deployment branch and build logs.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const metricNames: Record<string, string> = {
    accuracy: 'Accuracy', precision: 'Precision', recall: 'Recall', f1: 'F1 score', roc_auc: 'ROC-AUC',
  };

  return (
    <section className="card p-4 sm:p-5" aria-labelledby="model-evaluation-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><Scale size={13} /> Model transparency</p>
          <h2 id="model-evaluation-heading" className="font-display text-xl font-extrabold mt-1">Model evaluation report</h2>
          <p className="text-xs text-slate-500 mt-1">Reproducible synthetic holdout · not clinical performance</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh report
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}
      {report && <>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-lg bg-slate-100 dark:bg-slate-800 px-2.5 py-1.5">Version {report.model_version}</span>
          <span className="rounded-lg bg-slate-100 dark:bg-slate-800 px-2.5 py-1.5">{report.sample_count.toLocaleString()} holdout samples</span>
          <span className="rounded-lg bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200 px-2.5 py-1.5">Synthetic labels only</span>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(report.metrics).map(([key, value]) => (
            <div key={key} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <p className="text-xs text-slate-500">{metricNames[key] ?? key}</p>
              <p className="metric text-2xl mt-1">{(value * 100).toFixed(1)}<span className="text-sm">%</span></p>
            </div>
          ))}
        </div>
        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3">
            <p className="text-sm font-bold flex items-center gap-1.5"><Activity size={14} /> Confusion matrix</p>
            <p className="text-xs text-slate-500 mt-1">Rows = actual synthetic class; columns = predicted class</p>
            <table className="mt-2 w-full text-sm"><tbody>
              {report.confusion_matrix.rows_actual_columns_predicted.map((row, index) => <tr key={index}>
                <th className="text-left py-2 pr-2 text-xs text-slate-500">{report.confusion_matrix.labels[index]?.replace('synthetic_', '')}</th>
                {row.map((value, cell) => <td key={cell} className="text-center py-2 px-3 font-bold tabular-nums border border-slate-200 dark:border-slate-700">{value.toLocaleString()}</td>)}
              </tr>)}
            </tbody></table>
          </div>
          <div className="rounded-xl border border-amber-200 dark:border-amber-900 p-3">
            <p className="text-sm font-bold flex items-center gap-1.5 text-amber-800 dark:text-amber-200"><AlertTriangle size={14} /> Important limitations</p>
            <ul className="mt-2 list-disc pl-4 space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
              {report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-3">Synthetic label rule: {report.positive_label_definition}. Metrics show agreement with that generated rule only.</p>
      </>}
      <p className="mt-3 text-[11px] text-slate-400">This report does not establish safety, clinical accuracy, calibration, or suitability for diagnosis, triage, or treatment.</p>
    </section>
  );
}
