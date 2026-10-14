import type { Patient } from '../types/index.ts';
function ts(m: number): string { return new Date(Date.now() - m * 60_000).toISOString(); }
export function tsAgo(m: number): string { return ts(m); }
export const DEMO_PATIENTS: Patient[] = [
  { id: 'P-SIM-001', age: 64, sex: 'M', ward: 'General Ward', bed: 'A-12', scenario: 'stable', updatedAt: ts(4) },
  { id: 'P-SIM-002', age: 58, sex: 'F', ward: 'Cardiology', bed: 'C-07', scenario: 'stable', updatedAt: ts(6) },
  { id: 'P-SIM-003', age: 71, sex: 'M', ward: 'ICU', bed: 'B-14', scenario: 'worsening', updatedAt: ts(2) },
  { id: 'P-SIM-004', age: 45, sex: 'F', ward: 'Emergency', bed: 'E-03', scenario: 'recovering', updatedAt: ts(8) },
  { id: 'P-SIM-005', age: 52, sex: 'M', ward: 'General Ward', bed: 'A-21', scenario: 'stable', updatedAt: ts(11) },
  { id: 'P-SIM-006', age: 67, sex: 'F', ward: 'ICU', bed: 'B-09', scenario: 'worsening', updatedAt: ts(3) },
  { id: 'P-SIM-007', age: 39, sex: 'M', ward: 'Cardiology', bed: 'C-11', scenario: 'stable', updatedAt: ts(14) },
  { id: 'P-SIM-008', age: 75, sex: 'F', ward: 'Emergency', bed: 'E-08', scenario: 'recovering', updatedAt: ts(9) },
];
