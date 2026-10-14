import { DEMO_PATIENTS } from '../data/demoPatients.ts';
import { DEMO_VITALS_HISTORY } from '../data/demoVitals.ts';
import { DEMO_RISK, defaultFactors } from '../data/demoRisk.ts';
import { DEMO_ALERTS } from '../data/demoAlerts.ts';
import type { Patient, VitalReading, RiskSignal, RiskFactor, AlertItem } from '../types/index.ts';

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

export const demoDataService = {
  listPatients(): Patient[] { return clone(DEMO_PATIENTS); },
  getPatient(id: string): Patient | undefined { return clone(DEMO_PATIENTS.find((p) => p.id === id)); },
  vitalsHistory(id: string): VitalReading[] { return clone(DEMO_VITALS_HISTORY[id] ?? []); },
  latestVitals(id: string): VitalReading | undefined {
    const h = DEMO_VITALS_HISTORY[id]; return h ? clone(h[h.length - 1]) : undefined;
  },
  risk(id: string): RiskSignal | undefined { return clone(DEMO_RISK[id]); },
  allRisk(): RiskSignal[] { return clone(Object.values(DEMO_RISK)); },
  factors(id: string): RiskFactor[] { return clone(defaultFactors(id)); },
  alerts(): AlertItem[] { return clone(DEMO_ALERTS); },
};
