import { demoDataService } from '../services/demoDataService.ts';
import type { Patient, RiskSignal, VitalReading } from '../types/index.ts';

export function freshSnapshot(): { patients: Patient[]; latest: Record<string, VitalReading>; risks: Record<string, RiskSignal>; histories: Record<string, VitalReading[]> } {
  const patients = demoDataService.listPatients();
  const latest: Record<string, VitalReading> = {};
  const risks: Record<string, RiskSignal> = {};
  const histories: Record<string, VitalReading[]> = {};
  patients.forEach((p) => {
    histories[p.id] = demoDataService.vitalsHistory(p.id);
    const l = demoDataService.latestVitals(p.id);
    if (l) latest[p.id] = l;
    const r = demoDataService.risk(p.id);
    if (r) risks[p.id] = r;
  });
  return { patients, latest, risks, histories };
}
