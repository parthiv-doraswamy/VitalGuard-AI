import { DEMO_PATIENTS } from '../data/demoPatients.ts';
import { DEMO_VITALS_HISTORY } from '../data/demoVitals.ts';
import { DEMO_RISK, defaultFactors } from '../data/demoRisk.ts';
import { DEMO_ALERTS } from '../data/demoAlerts.ts';
import type { Patient, VitalReading, RiskSignal, RiskFactor, AlertItem } from '../types/index.ts';

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

function generatedHistory(patient: Patient): VitalReading[] {
  const seed = Number(patient.id.slice(-3)) || 1;
  const base = patient.scenario === 'worsening'
    ? { hr: 88 + seed % 12, spo2: 96 - seed % 2, sys: 124 - seed % 8, dia: 80, temp: 37.2, rr: 18 + seed % 3 }
    : patient.scenario === 'recovering'
      ? { hr: 102, spo2: 93, sys: 110, dia: 70, temp: 38.0, rr: 22 }
      : { hr: 68 + seed % 12, spo2: 96 + seed % 3, sys: 116 + seed % 12, dia: 74 + seed % 8, temp: 36.7 + (seed % 4) / 10, rr: 14 + seed % 4 };
  return Array.from({ length: 6 }, (_, i) => {
    const progress = (i + 1) / 6;
    const sign = patient.scenario === 'worsening' ? 1 : patient.scenario === 'recovering' ? -1 : 0;
    return {
      patientId: patient.id,
      timestamp: new Date(Date.now() - (5 - i) * 30_000).toISOString(),
      heartRate: Math.round(base.hr + sign * progress * 10),
      spo2: Math.min(100, Math.round(base.spo2 - sign * progress * 2)),
      systolicBp: Math.round(base.sys - sign * progress * 8),
      diastolicBp: Math.round(base.dia - sign * progress * 4),
      temperature: Math.round((base.temp + sign * progress * 0.4) * 10) / 10,
      respiratoryRate: Math.round(base.rr + sign * progress * 3),
    };
  });
}

function generatedRisk(patient: Patient): RiskSignal {
  const score = patient.scenario === 'worsening' ? 68 + (Number(patient.id.slice(-3)) % 20)
    : patient.scenario === 'recovering' ? 25 + (Number(patient.id.slice(-3)) % 15)
      : 8 + (Number(patient.id.slice(-3)) % 20);
  return {
    patientId: patient.id, score, level: score >= 85 ? 'critical' : score >= 65 ? 'high' : score >= 30 ? 'moderate' : 'low',
    probability: score / 100, news2: patient.scenario === 'worsening' ? 5 : patient.scenario === 'recovering' ? 3 : 1,
    trend: patient.scenario, trajectory: [score - 8, score - 5, score - 3, score - 2, score - 1, score],
    trajectoryLabels: ['2h ago', '1.5h ago', '1h ago', '30m ago', 'Now', 'Live'], updatedAt: patient.updatedAt,
  };
}

export const demoDataService = {
  listPatients(): Patient[] { return clone(DEMO_PATIENTS); },
  getPatient(id: string): Patient | undefined { return clone(DEMO_PATIENTS.find((p) => p.id === id)); },
  vitalsHistory(id: string): VitalReading[] {
    const patient = DEMO_PATIENTS.find((p) => p.id === id);
    return clone(DEMO_VITALS_HISTORY[id] ?? (patient ? generatedHistory(patient) : []));
  },
  latestVitals(id: string): VitalReading | undefined {
    const h = DEMO_VITALS_HISTORY[id];
    if (h) return clone(h[h.length - 1]);
    const patient = DEMO_PATIENTS.find((p) => p.id === id);
    const generated = patient ? generatedHistory(patient) : [];
    return generated.length ? clone(generated[generated.length - 1]) : undefined;
  },
  risk(id: string): RiskSignal | undefined {
    const known = DEMO_RISK[id];
    if (known) return clone(known);
    const patient = DEMO_PATIENTS.find((p) => p.id === id);
    return patient ? generatedRisk(patient) : undefined;
  },
  allRisk(): RiskSignal[] { return clone(DEMO_PATIENTS.map((p) => DEMO_RISK[p.id] ?? generatedRisk(p))); },
  factors(id: string): RiskFactor[] { return clone(defaultFactors(id)); },
  alerts(): AlertItem[] { return clone(DEMO_ALERTS); },
};
