import type { ObservationEvent } from '../services/api.ts';
import { riskLevelFor } from '../services/simulation.ts';
import type { AlertItem, AlertSeverity, AlertStatus, Patient, RiskSignal, TrendDirection, VitalReading } from '../types/index.ts';

/**
 * Pure helpers that turn committed backend stream events into the dashboard's
 * patient state. Scores come from the backend model; nothing here re-scores.
 */

const HISTORY_LIMIT = 40;
const TRAJECTORY_LIMIT = 12;

export interface PatientState {
  patients: Patient[];
  latest: Record<string, VitalReading>;
  risks: Record<string, RiskSignal>;
  histories: Record<string, VitalReading[]>;
}

export function readingFromEvent(event: ObservationEvent): VitalReading {
  const o = event.observation;
  return {
    patientId: event.patient_id, timestamp: event.created_at,
    heartRate: o.heart_rate, spo2: o.spo2, systolicBp: o.systolic_bp, diastolicBp: o.diastolic_bp,
    temperature: o.temperature, respiratoryRate: o.respiratory_rate,
  };
}

/** NEWS2 aggregate from the observed vitals (SpO2 scale 1, room air, alert). Display only, not clinical use. */
export function news2FromVitals(v: VitalReading): number {
  const band = (value: number, rules: Array<[number, number]>, otherwise: number) => {
    for (const [upper, points] of rules) if (value <= upper) return points;
    return otherwise;
  };
  return band(v.respiratoryRate, [[8, 3], [11, 1], [20, 0], [24, 2]], 3)
    + band(v.spo2, [[91, 3], [93, 2], [95, 1]], 0)
    + band(v.systolicBp, [[90, 3], [100, 2], [110, 1], [219, 0]], 3)
    + band(v.heartRate, [[40, 3], [50, 1], [90, 0], [110, 1], [130, 2]], 3)
    + band(v.temperature, [[35, 3], [36, 1], [38, 0], [39, 1]], 2);
}

function trendOf(trajectory: number[]): TrendDirection {
  if (trajectory.length < 3) return 'stable';
  const recent = trajectory.slice(-3);
  const delta = recent[recent.length - 1] - recent[0];
  if (delta >= 4) return 'worsening';
  if (delta <= -4) return 'recovering';
  return 'stable';
}

/** Apply observation events (any order) for known patients; events for unknown patients are ignored. */
export function applyObservations(state: PatientState, events: ObservationEvent[]): PatientState {
  const known = new Set(state.patients.map((patient) => patient.id));
  const relevant = events.filter((event) => known.has(event.patient_id)).sort((a, b) => a.event_id - b.event_id);
  if (relevant.length === 0) return state;
  const latest = { ...state.latest };
  const risks = { ...state.risks };
  const histories = { ...state.histories };
  const touched = new Map<string, string>();
  for (const event of relevant) {
    const reading = readingFromEvent(event);
    const pid = event.patient_id;
    latest[pid] = reading;
    histories[pid] = [...(histories[pid] ?? []), reading].slice(-HISTORY_LIMIT);
    const score = event.prediction.risk_score;
    const previous = risks[pid];
    const trajectory = [...(previous?.trajectory ?? []), score].slice(-TRAJECTORY_LIMIT);
    risks[pid] = {
      patientId: pid, score, level: riskLevelFor(score), probability: event.prediction.model_probability ?? score / 100,
      news2: news2FromVitals(reading), trend: trendOf(trajectory), trajectory,
      trajectoryLabels: trajectory.map((_, index) => (index === trajectory.length - 1 ? 'Live' : `t-${trajectory.length - 1 - index}`)),
      updatedAt: event.created_at,
    };
    touched.set(pid, event.created_at);
  }
  const patients = state.patients.map((patient) => (touched.has(patient.id) ? { ...patient, updatedAt: touched.get(patient.id)! } : patient));
  return { patients, latest, risks, histories };
}

export interface BackendAlertSummary { id: number; patient_id: string; severity: string; status: string; title: string; created_at: string | null }

export function alertFromBackend(alert: BackendAlertSummary, riskAfter?: number): AlertItem {
  const severity: AlertSeverity = alert.severity === 'critical' ? 'critical' : alert.severity === 'high' ? 'high' : 'moderate';
  const status: AlertStatus = alert.status === 'acknowledged' || alert.status === 'resolved' ? alert.status : 'open';
  return {
    id: backendAlertId(alert.id), patientId: alert.patient_id, severity, status, title: alert.title,
    description: 'Backend model risk crossed the alert threshold during the live stream. Review recommended.',
    contributors: ['backend risk model', 'live vital-sign stream'], createdAt: alert.created_at ?? new Date().toISOString(),
    riskAfter,
  };
}

export const backendAlertId = (id: number) => `BE-${id}`;
export const parseBackendAlertId = (id: string) => (id.startsWith('BE-') ? Number(id.slice(3)) || null : null);
