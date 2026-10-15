import { createContext } from 'react';
import type { Patient, RiskSignal, VitalReading, AlertItem } from '../types/index.ts';
import type { ObservationEvent } from '../services/api.ts';
import type { BackendAlertSummary } from './liveIngest.ts';

export type ToastSeverity = 'high' | 'critical' | 'info' | 'ok';
export interface ToastMsg { id: number; title: string; message: string; severity: ToastSeverity; at: string; patientId?: string; }
export interface SimValue {
  patients: Patient[];
  latest: Record<string, VitalReading>;
  risks: Record<string, RiskSignal>;
  histories: Record<string, VitalReading[]>;
  alerts: AlertItem[];
  toasts: ToastMsg[];
  running: boolean;
  tick: number;
  speed: 'slow' | 'normal' | 'fast';
  multiplier: 1 | 2;
  lastRefresh: string;
  start: () => void;
  pause: () => void;
  reset: () => void;
  refresh: () => void;
  dismissToast: (id: number) => void;
  setSpeed: (s: 'slow' | 'normal' | 'fast') => void;
  setMultiplier: (m: 1 | 2) => void;
  acknowledge: (id: string) => void;
  undoAcknowledge: (id: string) => void;
  dataSource: 'demo' | 'api';
  setDataSource: (d: 'demo' | 'api') => void;
  theme: 'light' | 'dark';
  setTheme: (t: 'light' | 'dark') => void;
  /** Apply committed backend stream observations to the cohort (batched into one render). */
  ingestObservations: (events: ObservationEvent[]) => void;
  /** Add or update a backend alert; `announce` shows a toast (and a system notification for the assigned doctor). */
  ingestAlert: (alert: BackendAlertSummary, options?: { announce?: boolean; riskAfter?: number }) => void;
  /** Sequence number of the latest applied backend stream tick (null before any). */
  streamTick: number | null;
  /** Message from the most recent failed alert action, if any. */
  alertActionError: string | null;
}
export const SimCtx = createContext<SimValue | null>(null);

