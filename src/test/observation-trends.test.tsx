import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BackendObservationTrends } from '../components/patients/BackendObservationTrends.tsx';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('renders descriptive trend direction without presenting a forecast', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      patient_id: 'DEMO-TREND-001',
      observation_count: 3,
      first_observed_at: '2026-10-10T10:00:00+00:00',
      last_observed_at: '2026-10-10T10:02:00+00:00',
      trends: [
        { metric: 'heart_rate', sample_count: 3, first_value: 70, latest_value: 90, absolute_change: 20, slope_per_observation: 10, direction: 'increasing', stability_threshold: 0.5 },
        { metric: 'spo2', sample_count: 3, first_value: 99, latest_value: 95, absolute_change: -4, slope_per_observation: -2, direction: 'decreasing', stability_threshold: 0.2 },
      ],
      method: 'ordinary least-squares slope over observation order',
      interpretation: 'Descriptive history only. No future values are forecast and no clinical meaning is inferred.',
      demo_only: true,
      clinically_validated: false,
    }),
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<BackendObservationTrends patientId="DEMO-TREND-001" />);
  await waitFor(() => expect(screen.getByText('increasing · change +20')).toBeInTheDocument());
  expect(screen.getByText('decreasing · change -4')).toBeInTheDocument();
  expect(screen.getByText(/no future prediction/i)).toBeInTheDocument();
});
