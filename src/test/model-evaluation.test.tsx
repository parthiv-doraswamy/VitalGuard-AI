import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { ModelEvaluationPanel, type Evaluation, type ModelInfo } from '../components/settings/ModelEvaluationPanel.tsx';

const DEMO_INFO: ModelInfo = {
  model_version: 'synthetic-logreg-0.1.0', algorithm: 'StandardScaler + LogisticRegression',
  training_data: 'generated synthetic observations only', clinically_validated: false, mode: 'synthetic-demo',
  model_source: 'artifact', load_error: null, supports_coefficient_contributions: true,
  artifact: { sha256: 'a'.repeat(64), created_at: '2026-10-14T00:00:00+00:00', dataset_kind: 'synthetic-demo',
    dataset_id: 'synthetic-demo-seed20261010-n12000', decision_threshold: null, selection: null },
};
const DEMO_EVALUATION: Evaluation = {
  model_version: 'synthetic-logreg-0.1.0', evaluation_type: 'deterministic stratified synthetic holdout', sample_count: 3000,
  positive_label_definition: 'synthetic heuristic score plus seeded noise >= 35', threshold: 0.5,
  metrics: { accuracy: 0.75, precision: 0.6, recall: 0.8, f1: 0.69, roc_auc: 0.8223 },
  confusion_matrix: { labels: ['synthetic_negative', 'synthetic_positive'], rows_actual_columns_predicted: [[1500, 400], [200, 900]] },
  limitations: ['Synthetic labels are derived from a hand-crafted heuristic.'], clinically_validated: false,
};
const RESEARCH_INFO: ModelInfo = {
  ...DEMO_INFO, model_version: 'logreg-mimic-iv-1a2b3c4d-5e6f7a8b', mode: 'research-model',
  training_data: 'mimic-iv-format (approved-clinical)',
  artifact: { ...DEMO_INFO.artifact!, dataset_kind: 'approved-clinical', dataset_id: 'mimic_iv-0123456789ab', decision_threshold: 0.4219,
    selection: { benchmark_id: 'benchmark-x', selected: 'logreg', rule: 'baseline unless a gated candidate is clearly better',
      compared: ['logreg', 'random_forest', 'xgboost'] } },
};
const RESEARCH_EVALUATION: Evaluation = {
  model_version: 'logreg-mimic-iv-1a2b3c4d-5e6f7a8b', evaluation_type: 'held-out test split (patient-disjoint)', test_rows: 969,
  metrics: { roc_auc: 0.8066, pr_auc_average_precision: null, sensitivity: 0.5862, specificity: 0.8883, threshold: 0.4219,
    alerts_per_100_predictions: 13.1, confusion_matrix: { tp: 17, fp: 105, tn: 835, fn: 12 } },
  calibration: { brier_score: 0.0755, calibration_slope: 0.94 },
  disclaimer: 'Research evaluation only. Not clinically validated.', clinically_validated: false,
};

function mockApi(evaluation: unknown, info: unknown, infoOk = true) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/api/v1/model/info')) return { ok: infoOk, json: async () => info } as Response;
    return { ok: evaluation !== null, json: async () => evaluation } as Response;
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('model evaluation panel', () => {
  it('shows the active synthetic demo model explicitly', async () => {
    mockApi(DEMO_EVALUATION, DEMO_INFO);
    render(<ModelEvaluationPanel />);
    expect(await screen.findByTestId('synthetic-demo-mode')).toHaveTextContent('no validated research model');
    expect(screen.getByTestId('active-model-version')).toHaveTextContent('synthetic-logreg-0.1.0');
    expect(screen.getByTestId('active-model-source')).toHaveTextContent('Verified artifact');
    expect(screen.getByText('ROC-AUC').parentElement).toHaveTextContent('82.2%');
    expect(screen.getByText('3,000 holdout samples')).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
  });

  it('renders a research test report with selection metadata, skipping non-rate and null metrics', async () => {
    mockApi(RESEARCH_EVALUATION, RESEARCH_INFO);
    render(<ModelEvaluationPanel />);
    expect(await screen.findByTestId('model-selection')).toHaveTextContent('Selected logreg over random_forest, xgboost');
    expect(screen.queryByTestId('synthetic-demo-mode')).toBeNull();
    expect(screen.getByText('Sensitivity').parentElement).toHaveTextContent('58.6%');
    expect(screen.getByText('Brier score').parentElement).toHaveTextContent('0.075');
    expect(screen.getByText(/Not computable for this split: PR-AUC/)).toBeInTheDocument();
    expect(screen.getByText('0.422 (validation-selected)')).toBeInTheDocument();
    expect(screen.queryByText('alerts_per_100_predictions')).toBeNull();
    expect(screen.getByText('969 test rows')).toBeInTheDocument();
    expect(screen.getByText('Research evaluation only. Not clinically validated.')).toBeInTheDocument();
  });

  it('warns when the API is serving a fallback model or the report is for another version', async () => {
    mockApi({ ...DEMO_EVALUATION, model_version: 'older-version' },
      { ...DEMO_INFO, model_source: 'fallback-synthetic-training', load_error: 'synthetic-logreg-0.1.0: Model file hash does not match' });
    render(<ModelEvaluationPanel />);
    const active = await screen.findByTestId('active-model');
    expect(within(active).getByTestId('active-model-source')).toHaveTextContent('Fallback: rebuilt synthetic model');
    expect(within(active).getByTestId('model-load-error')).toHaveTextContent('hash does not match');
    expect(within(active).getByText(/differs from the active model/)).toBeInTheDocument();
  });

  it('still renders the evaluation when an older backend has no model info', async () => {
    mockApi(DEMO_EVALUATION, null, false);
    render(<ModelEvaluationPanel />);
    await waitFor(() => expect(screen.getByText('ROC-AUC')).toBeInTheDocument());
    expect(screen.queryByTestId('active-model')).toBeNull();
  });

  it('reports an unavailable evaluation endpoint', async () => {
    mockApi(null, DEMO_INFO);
    render(<ModelEvaluationPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Model evaluation endpoint is not available');
  });
});
