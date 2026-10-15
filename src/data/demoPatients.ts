import cohortData from '../../backend/app/data/cohort.json';
import type { Patient, Scenario, Ward } from '../types/index.ts';
function ts(m: number): string { return new Date(Date.now() - m * 60_000).toISOString(); }
export function tsAgo(m: number): string { return ts(m); }

export interface CohortPatient {
  id: string; name: string; age: number; sex: 'M' | 'F'; ward: Ward; bed: string; scenario: Scenario;
  assigned_doctor: string; onset_step: number;
  baseline: { heart_rate: number; spo2: number; systolic_bp: number; diastolic_bp: number; temperature: number; respiratory_rate: number };
}

// Fictional records only, shared with the backend (backend/app/data/cohort.json).
export const COHORT = cohortData.patients as CohortPatient[];

export const DEMO_PATIENTS: Patient[] = COHORT.map((p, index) => ({
  id: p.id, name: p.name, assignedDoctor: p.assigned_doctor, age: p.age, sex: p.sex, ward: p.ward, bed: p.bed,
  scenario: p.scenario, updatedAt: ts(1 + (index * 7) % 14),
}));
