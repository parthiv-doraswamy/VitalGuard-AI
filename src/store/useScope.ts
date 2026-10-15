import { useMemo } from 'react';
import { useSimulation } from './useSimulation.ts';
import { useSession } from '../services/useSession.ts';
import type { AlertItem, Patient } from '../types/index.ts';

export interface Scope {
  patients: Patient[];
  alerts: AlertItem[];
  /** "assigned" for doctors (their patients only), otherwise "all". */
  scope: 'assigned' | 'all';
  canSee: (patientId: string) => boolean;
}

/** Patients and alerts the signed-in role may see. Doctors get only their assigned patients. */
export function useScope(): Scope {
  const { patients, alerts } = useSimulation();
  const session = useSession();
  return useMemo(() => {
    if (session?.role !== 'doctor') {
      return { patients, alerts, scope: 'all' as const, canSee: () => true };
    }
    const mine = patients.filter((patient) => patient.assignedDoctor === session.username);
    const ids = new Set(mine.map((patient) => patient.id));
    return { patients: mine, alerts: alerts.filter((alert) => ids.has(alert.patientId)), scope: 'assigned' as const,
      canSee: (patientId: string) => ids.has(patientId) };
  }, [patients, alerts, session]);
}
