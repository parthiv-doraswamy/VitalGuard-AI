import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BackendPatientTimeline } from '../components/patients/BackendPatientTimeline.tsx';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('renders persisted observation, alert and audit events', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      patient_id: 'DEMO-TIMELINE-001',
      items: [
        { event_id: 'observation:1', type: 'observation', occurred_at: '2026-10-10T12:00:00Z', patient_id: 'DEMO-TIMELINE-001', summary: 'Synthetic risk prediction recorded', observation_id: 1, risk_score: 44, risk_level: 'moderate', model_version: 'synthetic-v1', demo_only: true },
        { event_id: 'alert:1', type: 'alert', occurred_at: '2026-10-10T12:01:00Z', patient_id: 'DEMO-TIMELINE-001', summary: 'Synthetic alert', alert_id: 1, severity: 'high', status: 'open', demo_only: true },
        { event_id: 'audit:1', type: 'alert_audit', occurred_at: '2026-10-10T12:02:00Z', patient_id: 'DEMO-TIMELINE-001', summary: 'Alert acknowledged', alert_id: 1, action: 'acknowledge', actor: 'demo-operator', demo_only: true },
      ],
      count: 3,
      available_event_count: 3,
      limit: 30,
      demo_only: true,
      disclaimer: 'Synthetic only.',
    }),
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<BackendPatientTimeline patientId="DEMO-TIMELINE-001" />);

  await waitFor(() => expect(screen.getByText('Synthetic risk prediction recorded')).toBeInTheDocument());
  expect(screen.getByText('Synthetic alert')).toBeInTheDocument();
  expect(screen.getByText('Alert acknowledged')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledOnce();
});
