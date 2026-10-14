import type { AlertItem } from '../types/index.ts';
import { tsAgo } from './demoPatients.ts';
export const DEMO_ALERTS: AlertItem[] = [
  { id: 'AL-1003', patientId: 'P-SIM-003', severity: 'high', title: 'High-risk signal', description: 'Simulated risk signal increased and review is recommended.', contributors: ['SpO2 downward trend', 'heart-rate upward trend', 'systolic BP downward trend'], status: 'open', createdAt: tsAgo(25), riskBefore: 64, riskAfter: 82 },
  { id: 'AL-1006', patientId: 'P-SIM-006', severity: 'high', title: 'High-risk signal', description: 'Simulated risk signal increased and review is recommended.', contributors: ['heart-rate upward trend', 'respiratory-rate upward trend'], status: 'open', createdAt: tsAgo(40), riskBefore: 55, riskAfter: 71 },
  { id: 'AL-1004', patientId: 'P-SIM-004', severity: 'info', title: 'Recovering trajectory', description: 'Simulated risk signal is decreasing. Continued monitoring suggested.', contributors: ['heart-rate downward trend', 'SpO2 upward trend'], status: 'acknowledged', createdAt: tsAgo(90), riskBefore: 52, riskAfter: 38 },
  { id: 'AL-1001', patientId: 'P-SIM-001', severity: 'info', title: 'Routine observation', description: 'Simulated signal remains low. Routine monitoring.', contributors: ['stable vitals in simulated window'], status: 'resolved', createdAt: tsAgo(180), riskBefore: 12, riskAfter: 12 },
];
