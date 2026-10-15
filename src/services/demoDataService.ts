import { COHORT, DEMO_PATIENTS } from '../data/demoPatients.ts';
import { DEMO_RISK, defaultFactors } from '../data/demoRisk.ts';
import { DEMO_ALERTS } from '../data/demoAlerts.ts';
import type { Patient, VitalReading, RiskSignal, RiskFactor, AlertItem } from '../types/index.ts';

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

function generatedHistory(patient: Patient): VitalReading[] {
  // Starts from the patient's shared cohort baseline (the backend stream starts from the same values).
  const cohort = COHORT.find((item) => item.id === patient.id);
  const b = cohort?.baseline ?? { heart_rate: 76, spo2: 97, systolic_bp: 120, diastolic_bp: 78, temperature: 36.9, respiratory_rate: 15 };
  return Array.from({ length: 6 }, (_, i) => {
    const wobble = Math.sin(i * 1.7 + patient.id.length);
    return {
      patientId: patient.id,
      timestamp: new Date(Date.now() - (5 - i) * 30_000).toISOString(),
      heartRate: Math.round(b.heart_rate + wobble * 2),
      spo2: Math.min(100, Math.round(b.spo2 + wobble * 0.4)),
      systolicBp: Math.round(b.systolic_bp + wobble * 2),
      diastolicBp: Math.round(b.diastolic_bp + wobble),
      temperature: Math.round((b.temperature + wobble * 0.05) * 10) / 10,
      respiratoryRate: Math.round(b.respiratory_rate + wobble * 0.5),
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
    return patient ? generatedHistory(patient) : [];
  },
  latestVitals(id: string): VitalReading | undefined {
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
