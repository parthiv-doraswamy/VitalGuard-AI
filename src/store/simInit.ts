import { createContext } from 'react';
import type { Patient, RiskSignal, VitalReading, AlertItem } from '../types/index.ts';

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
}
export const SimCtx = createContext<SimValue | null>(null);

