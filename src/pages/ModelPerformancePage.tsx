import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Database, ExternalLink, Info, Trophy } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import reportJson from '../../ml/reports/physionet2019_benchmark.json';

interface Metrics {
  threshold: number; accuracy: number; balanced_accuracy: number; sensitivity: number; specificity: number;
  precision: number; f1: number; auroc: number; auprc: number; brier?: number;
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
}
interface ModelResult {
  label: string; kind: 'trained' | 'baseline'; test: Metrics; validation?: Metrics; test_auroc_95ci?: [number, number];
  roc_curve?: [number, number][]; train_seconds?: number; p95_single_row_latency_ms?: number;
  feature_importance?: Record<string, number> | null; test_at_0_5?: Partial<Metrics>;
}
interface Report {
  created_at: string;
  dataset: { name: string; url: string; license: string; citation: string; label: string; unit_of_prediction: string;
    patients_used: number; rows_used: number; positive_rate: number; patients_with_sepsis: number;
    feature_sets: Record<string, string[]>; split: string; preprocessing: string[];
    split_counts?: never; training_rows_after_negative_sampling: number };
  protocol: Record<string, string>;
  results: Record<'api_vitals' | 'extended', Record<string, ModelResult>>;
  baselines: Record<string, ModelResult>;
  best_by_feature_set: Record<'api_vitals' | 'extended', string>;
  selected_model: string;
  limitations: string[];
}
const report = reportJson as unknown as Report;

type FeatureSet = 'api_vitals' | 'extended';
const SETS: { key: FeatureSet; label: string; hint: string }[] = [
  { key: 'api_vitals', label: '7 API vitals', hint: 'Single-hour vitals the live API accepts (deployable today)' },
  { key: 'extended', label: 'Vitals + 6 h trends', hint: 'Adds trends, MAP, ICU stay length, sex, admission delay' },
];
// Categorical slots in fixed order (validated light/dark); models keep their colour in every chart.
const MODEL_ORDER = ['logistic_regression', 'random_forest', 'hist_gradient_boosting', 'xgboost'] as const;
const COLORS = {
  light: { logistic_regression: '#2a78d6', random_forest: '#eb6834', hist_gradient_boosting: '#1baf7a', xgboost: '#eda100' },
  dark: { logistic_regression: '#3987e5', random_forest: '#d95926', hist_gradient_boosting: '#199e70', xgboost: '#c98500' },
} as const;
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-display text-2xl font-extrabold tabular-nums text-slate-900 dark:text-slate-50">{value}</p>
      <p className="mt-1 text-[11px] text-slate-500">{hint}</p>
    </div>
  );
}

export function ModelPerformancePage() {
  const { theme } = useSimulation();
  const [set, setSet] = useState<FeatureSet>('api_vitals');
  const palette = COLORS[theme === 'dark' ? 'dark' : 'light'];
  const ink = theme === 'dark' ? '#c3c2b7' : '#52514e';
  const grid = theme === 'dark' ? '#2a2a28' : '#e8e7e2';
  const models = report.results[set];
  const bestKey = report.best_by_feature_set[set];
  const best = models[bestKey];
  const rows: [string, ModelResult][] = [...MODEL_ORDER.map((key) => [key, models[key]] as [string, ModelResult]),
    ['news2_rule', report.baselines.news2_rule], ['majority_class', report.baselines.majority_class]];

  const roc = useMemo(() => {
    const grid40 = models[MODEL_ORDER[0]].roc_curve ?? [];
    return grid40.map(([fpr], index) => {
      const point: Record<string, number> = { fpr, chance: fpr };
      for (const key of MODEL_ORDER) point[key] = models[key].roc_curve?.[index]?.[1] ?? 0;
      point.news2_rule = report.baselines.news2_rule.roc_curve?.[index]?.[1] ?? 0;
      return point;
    });
  }, [models]);

  const comparison = MODEL_ORDER.map((key) => ({
    model: report.results.api_vitals[key].label,
    api_vitals: report.results.api_vitals[key].test.auroc,
    extended: report.results.extended[key].test.auroc,
  }));
  const xgbImportance = Object.entries(models.xgboost.feature_importance ?? {})
    .sort((a, b) => b[1] - a[1]).slice(0, 10).map(([feature, value]) => ({ feature: feature.replace(/_/g, ' '), value }));

  return (
    <Shell title="Model performance" subtitle="Benchmark on a public ICU dataset">
      <PageHeader eyebrow="Machine learning" title="Model performance"
        subtitle="Logistic Regression, Random Forest, HistGradientBoosting and XGBoost trained and tested on real, de-identified ICU records to predict sepsis within ~6 hours."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Model performance' }]} />

      <SectionCard eyebrow="Dataset" title={report.dataset.name} hint={report.dataset.license} label="Dataset"
        action={<a href={report.dataset.url} target="_blank" rel="noreferrer" className="btn-ghost !py-1.5 !text-[13px]">PhysioNet <ExternalLink size={13} aria-hidden /></a>}>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
          <div><dt className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Patients</dt><dd className="font-bold tabular-nums">{report.dataset.patients_used.toLocaleString()}</dd></div>
          <div><dt className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Patient-hours</dt><dd className="font-bold tabular-nums">{report.dataset.rows_used.toLocaleString()}</dd></div>
          <div><dt className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Developed sepsis</dt><dd className="font-bold tabular-nums">{report.dataset.patients_with_sepsis.toLocaleString()} patients</dd></div>
          <div><dt className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Positive hours</dt><dd className="font-bold tabular-nums">{pct(report.dataset.positive_rate)}</dd></div>
        </dl>
        <p className="mt-3 text-xs text-slate-500 flex items-start gap-1.5"><Database size={13} aria-hidden className="mt-0.5 shrink-0" />
          Label: {report.dataset.label}. Split {report.dataset.split}; thresholds chosen on validation, results below are on the held-out test patients.</p>
      </SectionCard>

      <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label="Feature set">
        {SETS.map((item) => (
          <button key={item.key} type="button" onClick={() => setSet(item.key)} aria-pressed={set === item.key} title={item.hint}
            className={`tab-btn ${set === item.key ? 'tab-on' : 'tab-off'}`}>{item.label}</button>
        ))}
        <span className="text-xs text-slate-500">{SETS.find((item) => item.key === set)?.hint}</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5" data-testid="best-model-tiles">
        <div className="col-span-2 lg:col-span-1 rounded-2xl border border-teal-200 bg-teal-50 p-4 dark:border-teal-900 dark:bg-teal-950/40">
          <p className="text-[11px] font-bold uppercase tracking-wider text-teal-800 dark:text-teal-200 flex items-center gap-1.5"><Trophy size={13} aria-hidden /> Best (validation AUPRC)</p>
          <p className="mt-1 font-display text-xl font-extrabold">{best.label}</p>
          <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">threshold {best.test.threshold}</p>
        </div>
        <Tile label="Accuracy" value={pct(best.test.accuracy)} hint="All test hours" />
        <Tile label="Balanced accuracy" value={pct(best.test.balanced_accuracy)} hint="Mean of sensitivity and specificity" />
        <Tile label="Sensitivity · Specificity" value={`${pct(best.test.sensitivity)} · ${pct(best.test.specificity)}`} hint="Sepsis hours caught · others cleared" />
        <Tile label="AUROC" value={best.test.auroc.toFixed(3)} hint={best.test_auroc_95ci ? `95% CI ${best.test_auroc_95ci[0]}–${best.test_auroc_95ci[1]}` : 'Threshold-free ranking'} />
      </div>

      <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200 flex items-start gap-1.5">
        <Info size={13} aria-hidden className="mt-0.5 shrink-0" />
        Accuracy alone is misleading here: only {pct(report.dataset.positive_rate)} of hours are positive, so “always no sepsis” scores {pct(report.baselines.majority_class.test.accuracy)} accuracy while catching none. Compare balanced accuracy, sensitivity and AUROC.
      </p>

      <div className="mt-4">
        <SectionCard eyebrow="Test set" title="All models" hint="Held-out test patients · threshold per model from validation" label="Model metrics table">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[860px]" data-testid="metrics-table">
              <thead className="table-head"><tr>
                <th scope="col" className="!pl-3">Model</th><th scope="col" className="text-right">Accuracy</th><th scope="col" className="text-right">Balanced acc.</th>
                <th scope="col" className="text-right">Sensitivity</th><th scope="col" className="text-right">Specificity</th><th scope="col" className="text-right">Precision</th>
                <th scope="col" className="text-right">F1</th><th scope="col" className="text-right">AUROC (95% CI)</th><th scope="col" className="text-right">AUPRC</th>
              </tr></thead>
              <tbody>
                {rows.map(([key, result]) => (
                  <tr key={key} className={`border-t border-slate-100 dark:border-slate-800 ${key === bestKey ? 'bg-teal-50/60 dark:bg-teal-950/20' : ''}`}>
                    <th scope="row" className="!pl-3 py-2 text-left font-semibold">
                      <span className="inline-flex items-center gap-2">
                        {key in palette && <span className="h-2.5 w-2.5 rounded-sm" style={{ background: palette[key as keyof typeof palette] }} aria-hidden />}
                        {result.label}{key === bestKey && <Trophy size={13} aria-label="best" className="text-teal-600" />}
                        {result.kind === 'baseline' && <span className="text-[10px] uppercase tracking-wider text-slate-400">baseline</span>}
                      </span>
                    </th>
                    <td className="text-right tabular-nums">{pct(result.test.accuracy)}</td>
                    <td className="text-right tabular-nums">{pct(result.test.balanced_accuracy)}</td>
                    <td className="text-right tabular-nums">{pct(result.test.sensitivity)}</td>
                    <td className="text-right tabular-nums">{pct(result.test.specificity)}</td>
                    <td className="text-right tabular-nums">{pct(result.test.precision)}</td>
                    <td className="text-right tabular-nums">{result.test.f1.toFixed(3)}</td>
                    <td className="text-right tabular-nums">{result.test.auroc.toFixed(3)}{result.test_auroc_95ci ? <span className="text-slate-400"> ({result.test_auroc_95ci[0].toFixed(3)}–{result.test_auroc_95ci[1].toFixed(3)})</span> : null}</td>
                    <td className="text-right tabular-nums">{result.test.auprc.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Prevalence-level AUPRC (no skill) is {report.dataset.positive_rate.toFixed(3)}. NEWS2 uses the same seven vitals with no training.</p>
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <SectionCard eyebrow="Discrimination" title="ROC curves" hint="True vs false positive rate across thresholds (test)" label="ROC curves">
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={roc} margin={{ top: 8, right: 16, bottom: 22, left: 0 }}>
                <CartesianGrid stroke={grid} vertical={false} />
                <XAxis dataKey="fpr" type="number" domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tickFormatter={(v: number) => v.toFixed(1)} stroke={ink} fontSize={11}
                  label={{ value: 'False positive rate', position: 'insideBottom', offset: -10, fill: ink, fontSize: 11 }} />
                <YAxis domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tickFormatter={(v: number) => v.toFixed(1)} stroke={ink} fontSize={11} width={36} />
                <Tooltip formatter={(value: number, name: string) => [value.toFixed(3), name]} labelFormatter={(v: number) => `FPR ${Number(v).toFixed(2)}`} />
                <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
                {MODEL_ORDER.map((key) => (
                  <Line key={key} dataKey={key} name={`${models[key].label} (${models[key].test.auroc.toFixed(3)})`} stroke={palette[key]} strokeWidth={2} dot={false} isAnimationActive={false} />
                ))}
                <Line dataKey="news2_rule" name={`NEWS2 rule (${report.baselines.news2_rule.test.auroc.toFixed(3)})`} stroke={ink} strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="chance" name="Chance" stroke={grid} strokeWidth={1} dot={false} legendType="none" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Feature sets" title="AUROC: vitals only vs with trends" hint="Same models, same patients; trends add signal" label="AUROC by feature set">
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparison} margin={{ top: 8, right: 16, bottom: 8, left: 0 }} barGap={2}>
                <CartesianGrid stroke={grid} vertical={false} />
                <XAxis dataKey="model" stroke={ink} fontSize={11} interval={0} />
                <YAxis domain={[0.5, 0.85]} ticks={[0.5, 0.6, 0.7, 0.8]} tickFormatter={(v: number) => v.toFixed(1)} stroke={ink} fontSize={11} width={36} />
                <Tooltip formatter={(value: number) => value.toFixed(3)} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="api_vitals" name="7 API vitals" fill={palette.logistic_regression} radius={[4, 4, 0, 0]} />
                <Bar dataKey="extended" name="Vitals + 6 h trends" fill={palette.random_forest} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <SectionCard eyebrow="XGBoost" title="What the model relies on" hint={`Top features by gain · ${SETS.find((item) => item.key === set)?.label}`} label="XGBoost feature importance">
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={xgbImportance} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid stroke={grid} horizontal={false} />
                <XAxis type="number" tickFormatter={(v: number) => `${Math.round(v * 100)}%`} stroke={ink} fontSize={11} />
                <YAxis type="category" dataKey="feature" width={150} stroke={ink} fontSize={11} />
                <Tooltip formatter={(value: number) => pct(value)} />
                <Bar dataKey="value" name="Share of gain" fill={palette.xgboost} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard eyebrow="Read before using" title="Protocol and limitations" hint="How the numbers were produced" label="Limitations">
          <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300 list-disc pl-5">
            <li>{report.protocol.selection}; {report.protocol.threshold}.</li>
            <li>Training used {report.dataset.training_rows_after_negative_sampling.toLocaleString()} rows: {report.protocol.training_sampling}.</li>
            {report.limitations.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <p className="mt-3 text-[11px] text-slate-400">{report.dataset.citation} · generated {new Date(report.created_at).toLocaleString()}</p>
        </SectionCard>
      </div>
    </Shell>
  );
}
