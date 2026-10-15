import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SimulationProvider } from '../store/SimulationContext.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { useScope } from '../store/useScope.ts';
import { applyObservations, news2FromVitals, type PatientState } from '../store/liveIngest.ts';
import { freshSnapshot } from '../store/snapshot.ts';
import { openOfflineSession } from '../services/auth.ts';
import { PatientsPage } from '../pages/PatientsPage.tsx';
import type { ObservationEvent } from '../services/api.ts';
import type { SimValue } from '../store/simInit.ts';

function event(id: number, patientId: string, score: number, overrides: Partial<Record<string, number>> = {}): ObservationEvent {
  return {
    type: 'observation.created', event_id: id, observation_id: id, session_id: 's', sequence: id, patient_id: patientId,
    created_at: new Date(1_700_000_000_000 + id * 1000).toISOString(), timestamp: '', model_version: 'm',
    observation: { age: 70, heart_rate: 120, spo2: 89, systolic_bp: 95, diastolic_bp: 60, temperature: 38.6, respiratory_rate: 26, ...overrides },
    prediction: { risk_score: score, risk_level: 'high', model_probability: score / 100 }, alert: null,
    server_received_at: null, published_at: null, demo_only: true, data_origin: 'synthetic',
  };
}

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('applying backend stream events', () => {
  it('updates vitals, history and backend risk for known patients only', () => {
    const base: PatientState = freshSnapshot();
    const before = base.histories['P-SIM-003'].length;
    const next = applyObservations(base, [event(2, 'P-SIM-003', 72), event(1, 'P-SIM-003', 55), event(3, 'NOT-IN-COHORT', 99)]);
    expect(next.latest['P-SIM-003'].heartRate).toBe(120);
    expect(next.histories['P-SIM-003']).toHaveLength(before + 2);
    // Applied in event order, so the newest score wins and the trajectory ends with it.
    expect(next.risks['P-SIM-003'].score).toBe(72);
    expect(next.risks['P-SIM-003'].level).toBe('high');
    expect(next.risks['P-SIM-003'].trajectory.slice(-2)).toEqual([55, 72]);
    expect(next.latest['NOT-IN-COHORT']).toBeUndefined();
    expect(base.latest['P-SIM-003'].heartRate).not.toBe(120); // input state is not mutated
  });

  it('computes NEWS2 from the observed vitals', () => {
    const calm = { patientId: 'x', timestamp: '', heartRate: 72, spo2: 98, systolicBp: 122, diastolicBp: 78, temperature: 36.8, respiratoryRate: 15 };
    expect(news2FromVitals(calm)).toBe(0);
    expect(news2FromVitals({ ...calm, heartRate: 135, spo2: 88, systolicBp: 88, temperature: 39.4, respiratoryRate: 30 })).toBe(14);
  });
});

function Probe({ onValue }: { onValue: (value: SimValue & { scoped: ReturnType<typeof useScope> }) => void }) {
  const sim = useSimulation();
  onValue({ ...sim, scoped: useScope() });
  return null;
}

describe('role scope and live alerts', () => {
  it('shows doctors only their assigned patients', () => {
    openOfflineSession('dr.khan');
    render(<SimulationProvider><MemoryRouter><PatientsPage /></MemoryRouter></SimulationProvider>);
    expect(screen.getByRole('heading', { name: 'My patients' })).toBeInTheDocument();
    expect(screen.getByText(/Census · 10 assigned patients/)).toBeInTheDocument();
    // dr.khan covers Emergency; P-SIM-003 is an ICU patient.
    expect(screen.queryByText('P-SIM-003')).not.toBeInTheDocument();
  });

  it('notifies the assigned doctor (toast + system notification) and nobody else', async () => {
    const showNotification = vi.fn(async () => undefined);
    vi.stubGlobal('Notification', Object.assign(vi.fn(), { permission: 'granted' }));
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { getRegistration: async () => ({ showNotification }) } });
    openOfflineSession('doctor.demo');
    let latest: (SimValue & { scoped: ReturnType<typeof useScope> }) | null = null;
    render(<SimulationProvider><Probe onValue={(value) => { latest = value; }} /></SimulationProvider>);

    await act(async () => {
      latest!.ingestAlert({ id: 7, patient_id: 'P-SIM-003', severity: 'critical', status: 'open', title: 'Critical demo risk score', created_at: null }, { announce: true });
      latest!.ingestAlert({ id: 8, patient_id: 'P-SIM-004', severity: 'high', status: 'open', title: 'High demo risk score', created_at: null }, { announce: true });
    });
    expect(showNotification).toHaveBeenCalledTimes(1);
    expect(showNotification.mock.calls[0]).toEqual([expect.stringContaining('critical alert (ICU · bed B-14)'),
      expect.objectContaining({ tag: 'vg-alert-7', requireInteraction: true })]);
    expect(latest!.toasts.map((toast) => toast.patientId)).toEqual(['P-SIM-003']);
    // Both alerts are stored, but the doctor's scope only contains their own patient's alert.
    expect(latest!.alerts.filter((alert) => alert.id.startsWith('BE-'))).toHaveLength(2);
    expect(latest!.scoped.alerts.filter((alert) => alert.id.startsWith('BE-')).map((alert) => alert.patientId)).toEqual(['P-SIM-003']);

    // A status update for a known alert changes it in place and never re-announces.
    await act(async () => { latest!.ingestAlert({ id: 7, patient_id: 'P-SIM-003', severity: 'critical', status: 'acknowledged', title: 'x', created_at: null }, { announce: true }); });
    expect(showNotification).toHaveBeenCalledTimes(1);
    expect(latest!.alerts.find((alert) => alert.id === 'BE-7')?.status).toBe('acknowledged');
  });

  it('batches a cohort tick into the shared patient state', async () => {
    vi.useFakeTimers();
    openOfflineSession('nurse.demo');
    let latest: SimValue | null = null;
    render(<SimulationProvider><Probe onValue={(value) => { latest = value; }} /></SimulationProvider>);
    act(() => { latest!.ingestObservations([event(10, 'P-SIM-001', 40), event(11, 'P-SIM-002', 80)]); });
    expect(latest!.risks['P-SIM-002'].score).not.toBe(80); // not applied until the batch flushes
    await act(async () => { vi.advanceTimersByTime(200); });
    expect(latest!.risks['P-SIM-002'].score).toBe(80);
    expect(latest!.latest['P-SIM-001'].spo2).toBe(89);
    expect(latest!.streamTick).toBe(11);
  });
});
