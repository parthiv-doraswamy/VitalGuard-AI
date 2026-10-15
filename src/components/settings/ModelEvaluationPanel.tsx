import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, Cpu, RefreshCw, Scale } from 'lucide-react';
import { APP_CONFIG } from '../../services/config.ts';

/** GET /api/v1/model/info — the model actually serving predictions. Newer fields are optional for older backends. */
export type ModelInfo = {
  model_version: string;
  algorithm: string;
  training_data: string;
  clinically_validated: false;
  mode?: 'synthetic-demo' | 'research-model';
  model_source?: 'artifact' | 'artifact-previous-after-active-failed' | 'fallback-synthetic-training';
  load_error?: string | null;
  supports_coefficient_contributions?: boolean;
  artifact?: {
    sha256: string | null;
    created_at: string | null;
    dataset_kind: string;
    dataset_id: string | null;
    decision_threshold?: number | null;
    selection?: { benchmark_id: string; selected: string; rule: string; compared: string[] } | null;
  } | null;
};

/** GET /api/v1/model/evaluation — either the synthetic holdout report or a research test-split report. */
export type Evaluation = {
  model_version: string;
  evaluation_type: string;
  sample_count?: number;
  test_rows?: number;
  positive_label_definition?: string;
  threshold?: number;
  metrics: Record<string, unknown>;
  confusion_matrix?: { labels: string[]; rows_actual_columns_predicted: number[][] };
  limitations?: string[];
  disclaimer?: string;
  calibration?: { brier_score?: number; calibration_slope?: number; calibration_intercept?: number };
  clinically_validated: false;
};

// Rates shown as percentages; anything else numeric is shown as a plain value.
const RATE_METRICS: Record<string, string> = {
  accuracy: 'Accuracy', balanced_accuracy: 'Balanced accuracy', precision: 'Precision', recall: 'Recall', f1: 'F1 score', roc_auc: 'ROC-AUC',
  pr_auc_average_precision: 'PR-AUC', sensitivity: 'Sensitivity', specificity: 'Specificity',
  precision_ppv: 'Precision (PPV)', npv: 'NPV',
};

const SOURCE_LABELS: Record<string, string> = {
  artifact: 'Verified artifact',
  'artifact-previous-after-active-failed': 'Previous artifact (active one failed verification)',
  'fallback-synthetic-training': 'Fallback: rebuilt synthetic model',
};

export function ModelEvaluationPanel() {
  const [report, setReport] = useState<Evaluation | null>(null);
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [evaluationResponse, infoResponse] = await Promise.all([
        fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/model/evaluation`, { signal: AbortSignal.timeout(10000) }),
        fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/model/info`, { signal: AbortSignal.timeout(10000) }),
      ]);
      if (!evaluationResponse.ok) throw new Error('Evaluation endpoint unavailable');
      setReport(await evaluationResponse.json() as Evaluation);
      setInfo(infoResponse.ok ? await infoResponse.json() as ModelInfo : null);
      setError('');
    } catch {
      setError('Model evaluation endpoint is not available yet. Check the backend deployment branch and build logs.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const rates = report ? Object.entries(report.metrics).filter((entry): entry is [string, number] =>
    entry[0] in RATE_METRICS && typeof entry[1] === 'number') : [];
  const unavailable = report ? Object.keys(RATE_METRICS).filter((key) => key in report.metrics && report.metrics[key] === null) : [];
  const syntheticDemo = !info || (info.mode ?? 'synthetic-demo') === 'synthetic-demo';
  const versionMismatch = info && report && info.model_version !== report.model_version;
  const samples = report?.sample_count ?? report?.test_rows;

  return (
    <section className="card p-4 sm:p-5" aria-labelledby="model-evaluation-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><Scale size={13} /> Model transparency</p>
          <h2 id="model-evaluation-heading" className="font-display text-xl font-extrabold mt-1">Model evaluation report</h2>
          <p className="text-xs text-slate-500 mt-1">{report?.evaluation_type ?? 'Reproducible evaluation'} · not clinical performance</p>
        </div>
        <button className="btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh report
        </button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">{error}</p>}

      {info && (
        <div className="mt-4 rounded-xl border border-slate-200 dark:border-slate-700 p-3" data-testid="active-model">
          <p className="text-sm font-bold flex items-center gap-1.5"><Cpu size={14} /> Active model</p>
          {syntheticDemo && (
            <p className="mt-2 rounded-lg bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200 px-2.5 py-1.5 text-xs font-semibold" data-testid="synthetic-demo-mode">
              Synthetic demo mode — no validated research model is available. Scores come from a model trained on generated data.
            </p>
          )}
          <dl className="mt-2 grid sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
            <div><dt className="text-slate-500">Version</dt><dd className="font-semibold break-all" data-testid="active-model-version">{info.model_version}</dd></div>
            <div><dt className="text-slate-500">Algorithm</dt><dd className="font-semibold">{info.algorithm}</dd></div>
            <div><dt className="text-slate-500">Source</dt><dd className="font-semibold" data-testid="active-model-source">{SOURCE_LABELS[info.model_source ?? 'artifact'] ?? info.model_source}</dd></div>
            <div><dt className="text-slate-500">Training data</dt><dd className="font-semibold">{info.training_data}{info.artifact?.dataset_id ? ` (${info.artifact.dataset_id})` : ''}</dd></div>
            {info.artifact?.sha256 && <div><dt className="text-slate-500">Artifact SHA-256</dt><dd className="font-mono" title={info.artifact.sha256}>{info.artifact.sha256.slice(0, 12)}…</dd></div>}
            {typeof info.artifact?.decision_threshold === 'number' && <div><dt className="text-slate-500">Operating threshold</dt><dd className="font-semibold">{info.artifact.decision_threshold.toFixed(3)} (validation-selected)</dd></div>}
          </dl>
          {info.artifact?.selection && (
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-300" data-testid="model-selection">
              Selected <strong>{info.artifact.selection.selected}</strong> over {info.artifact.selection.compared.filter((name) => name !== info.artifact?.selection?.selected).join(', ') || 'no other candidates'} · {info.artifact.selection.rule}
            </p>
          )}
          {info.load_error && <p role="alert" className="mt-2 text-xs text-rose-700" data-testid="model-load-error">Artifact problem: {info.load_error}</p>}
          {versionMismatch && <p role="alert" className="mt-2 text-xs text-rose-700">Evaluation report version ({report.model_version}) differs from the active model.</p>}
        </div>
      )}

      {report && <>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-lg bg-slate-100 dark:bg-slate-800 px-2.5 py-1.5">Evaluated version {report.model_version}</span>
          {samples !== undefined && <span className="rounded-lg bg-slate-100 dark:bg-slate-800 px-2.5 py-1.5">{samples.toLocaleString()} {report.sample_count !== undefined ? 'holdout samples' : 'test rows'}</span>}
          {syntheticDemo && <span className="rounded-lg bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200 px-2.5 py-1.5">Synthetic labels only</span>}
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {rates.map(([key, value]) => (
            <div key={key} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <p className="text-xs text-slate-500">{RATE_METRICS[key]}</p>
              <p className="metric text-2xl mt-1">{(value * 100).toFixed(1)}<span className="text-sm">%</span></p>
            </div>
          ))}
          {report.calibration?.brier_score !== undefined && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
              <p className="text-xs text-slate-500">Brier score</p>
              <p className="metric text-2xl mt-1">{report.calibration.brier_score.toFixed(3)}</p>
            </div>
          )}
        </div>
        {unavailable.length > 0 && <p className="mt-2 text-xs text-slate-500">Not computable for this split: {unavailable.map((key) => RATE_METRICS[key]).join(', ')}.</p>}
        <div className="mt-4 grid md:grid-cols-2 gap-4">
          {report.confusion_matrix && (
            <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3">
              <p className="text-sm font-bold flex items-center gap-1.5"><Activity size={14} /> Confusion matrix</p>
              <p className="text-xs text-slate-500 mt-1">Rows = actual class; columns = predicted class</p>
              <table className="mt-2 w-full text-sm"><tbody>
                {report.confusion_matrix.rows_actual_columns_predicted.map((row, index) => <tr key={index}>
                  <th className="text-left py-2 pr-2 text-xs text-slate-500">{report.confusion_matrix?.labels[index]?.replace('synthetic_', '')}</th>
                  {row.map((value, cell) => <td key={cell} className="text-center py-2 px-3 font-bold tabular-nums border border-slate-200 dark:border-slate-700">{value.toLocaleString()}</td>)}
                </tr>)}
              </tbody></table>
            </div>
          )}
          <div className="rounded-xl border border-amber-200 dark:border-amber-900 p-3">
            <p className="text-sm font-bold flex items-center gap-1.5 text-amber-800 dark:text-amber-200"><AlertTriangle size={14} /> Important limitations</p>
            <ul className="mt-2 list-disc pl-4 space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
              {(report.limitations ?? (report.disclaimer ? [report.disclaimer] : [])).map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
          </div>
        </div>
        {report.positive_label_definition && (
          <p className="text-xs text-slate-500 mt-3">
            {syntheticDemo
              ? <>Synthetic label rule: {report.positive_label_definition}. Metrics show agreement with that generated rule only.</>
              : <>Label: {report.positive_label_definition}. {report.evaluation_type}.</>}
          </p>
        )}
      </>}
      <p className="mt-3 text-[11px] text-slate-400">This report does not establish safety, clinical accuracy, calibration, or suitability for diagnosis, triage, or treatment.</p>
    </section>
  );
}
