import type { Patient } from '../types/index.ts';
function ts(m: number): string { return new Date(Date.now() - m * 60_000).toISOString(); }
export function tsAgo(m: number): string { return ts(m); }

// Fictional records only. Stable, worsening and recovering scenarios exercise the demo UI.
export const DEMO_PATIENTS: Patient[] = [
  { id: 'P-SIM-001', age: 64, sex: 'M', ward: 'General Ward', bed: 'A-12', scenario: 'stable', updatedAt: ts(4) },
  { id: 'P-SIM-002', age: 58, sex: 'F', ward: 'Cardiology', bed: 'C-07', scenario: 'stable', updatedAt: ts(6) },
  { id: 'P-SIM-003', age: 71, sex: 'M', ward: 'ICU', bed: 'B-14', scenario: 'worsening', updatedAt: ts(2) },
  { id: 'P-SIM-004', age: 45, sex: 'F', ward: 'Emergency', bed: 'E-03', scenario: 'recovering', updatedAt: ts(8) },
  { id: 'P-SIM-005', age: 52, sex: 'M', ward: 'General Ward', bed: 'A-21', scenario: 'stable', updatedAt: ts(11) },
  { id: 'P-SIM-006', age: 67, sex: 'F', ward: 'ICU', bed: 'B-09', scenario: 'worsening', updatedAt: ts(3) },
  { id: 'P-SIM-007', age: 39, sex: 'M', ward: 'Cardiology', bed: 'C-11', scenario: 'stable', updatedAt: ts(14) },
  { id: 'P-SIM-008', age: 75, sex: 'F', ward: 'Emergency', bed: 'E-08', scenario: 'recovering', updatedAt: ts(9) },
  { id: 'P-SIM-009', age: 61, sex: 'F', ward: 'General Ward', bed: 'A-08', scenario: 'stable', updatedAt: ts(3) },
  { id: 'P-SIM-010', age: 78, sex: 'M', ward: 'ICU', bed: 'B-03', scenario: 'worsening', updatedAt: ts(1) },
  { id: 'P-SIM-011', age: 49, sex: 'F', ward: 'Cardiology', bed: 'C-15', scenario: 'stable', updatedAt: ts(7) },
  { id: 'P-SIM-012', age: 56, sex: 'M', ward: 'Emergency', bed: 'E-11', scenario: 'recovering', updatedAt: ts(5) },
  { id: 'P-SIM-013', age: 83, sex: 'F', ward: 'General Ward', bed: 'A-17', scenario: 'stable', updatedAt: ts(12) },
  { id: 'P-SIM-014', age: 69, sex: 'M', ward: 'ICU', bed: 'B-18', scenario: 'worsening', updatedAt: ts(2) },
  { id: 'P-SIM-015', age: 42, sex: 'F', ward: 'Cardiology', bed: 'C-02', scenario: 'stable', updatedAt: ts(10) },
  { id: 'P-SIM-016', age: 73, sex: 'M', ward: 'Emergency', bed: 'E-06', scenario: 'worsening', updatedAt: ts(1) },
  { id: 'P-SIM-017', age: 60, sex: 'F', ward: 'General Ward', bed: 'A-25', scenario: 'recovering', updatedAt: ts(6) },
  { id: 'P-SIM-018', age: 51, sex: 'M', ward: 'Cardiology', bed: 'C-09', scenario: 'stable', updatedAt: ts(13) },
  { id: 'P-SIM-019', age: 66, sex: 'F', ward: 'ICU', bed: 'B-21', scenario: 'stable', updatedAt: ts(4) },
  { id: 'P-SIM-020', age: 47, sex: 'M', ward: 'Emergency', bed: 'E-14', scenario: 'recovering', updatedAt: ts(8) },
];
