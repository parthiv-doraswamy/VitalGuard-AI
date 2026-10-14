import type { RiskSignal, RiskFactor } from '../types/index.ts';
import { tsAgo } from './demoPatients.ts';
export const DEMO_RISK: Record<string, RiskSignal> = {
  'P-SIM-001': { patientId: 'P-SIM-001', score: 12, level: 'low', probability: 0.12, news2: 1, trend: 'stable', trajectory: [10,11,12,11,12,12], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(4) },
  'P-SIM-002': { patientId: 'P-SIM-002', score: 22, level: 'low', probability: 0.22, news2: 2, trend: 'stable', trajectory: [20,21,22,21,22,22], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(6) },
  'P-SIM-003': { patientId: 'P-SIM-003', score: 87, level: 'high', probability: 0.87, news2: 7, trend: 'worsening', trajectory: [32,41,55,70,82,87], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(2) },
  'P-SIM-004': { patientId: 'P-SIM-004', score: 34, level: 'moderate', probability: 0.34, news2: 3, trend: 'recovering', trajectory: [68,60,52,44,38,34], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(8) },
  'P-SIM-005': { patientId: 'P-SIM-005', score: 9, level: 'low', probability: 0.09, news2: 0, trend: 'stable', trajectory: [9,9,10,9,9,9], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(11) },
  'P-SIM-006': { patientId: 'P-SIM-006', score: 76, level: 'high', probability: 0.76, news2: 6, trend: 'worsening', trajectory: [30,42,54,63,71,76], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(3) },
  'P-SIM-007': { patientId: 'P-SIM-007', score: 6, level: 'low', probability: 0.06, news2: 0, trend: 'stable', trajectory: [6,6,6,7,6,6], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(14) },
  'P-SIM-008': { patientId: 'P-SIM-008', score: 28, level: 'moderate', probability: 0.28, news2: 2, trend: 'recovering', trajectory: [62,55,47,39,32,28], trajectoryLabels: ['2h ago','1.5h ago','1h ago','30m ago','Now','Live'], updatedAt: tsAgo(9) },
};
export const DEMO_FACTORS: Record<string, RiskFactor[]> = {
  'P-SIM-003': [
    { patientId: 'P-SIM-003', name: 'SpO2 decline', contribution: 0.32, direction: 'increases-risk', currentValue: '92%', trend: '98% to 92% in simulated window', description: 'Sustained downward SpO2 trend in demo data.' },
    { patientId: 'P-SIM-003', name: 'Heart rate increase', contribution: 0.26, direction: 'increases-risk', currentValue: '111 bpm', trend: '82 to 111 bpm in simulated window', description: 'Upward heart-rate trend in demo data.' },
    { patientId: 'P-SIM-003', name: 'Systolic BP decline', contribution: 0.18, direction: 'increases-risk', currentValue: '106 mmHg', trend: '122 to 106 mmHg in simulated window', description: 'Downward systolic trend in demo data.' },
    { patientId: 'P-SIM-003', name: 'Temperature increase', contribution: 0.13, direction: 'increases-risk', currentValue: '38.3 C', trend: '37.1 to 38.3 C in simulated window', description: 'Upward temperature trend in demo data.' },
    { patientId: 'P-SIM-003', name: 'Respiratory rate increase', contribution: 0.11, direction: 'increases-risk', currentValue: '25 /min', trend: '16 to 25 /min in simulated window', description: 'Upward respiratory-rate trend in demo data.' },
  ],
  'P-SIM-006': [
    { patientId: 'P-SIM-006', name: 'Heart rate increase', contribution: 0.3, direction: 'increases-risk', currentValue: '105 bpm', trend: '86 to 105 bpm', description: 'Upward trend.' },
    { patientId: 'P-SIM-006', name: 'SpO2 decline', contribution: 0.27, direction: 'increases-risk', currentValue: '93%', trend: '97% to 93%', description: 'Downward trend.' },
    { patientId: 'P-SIM-006', name: 'Respiratory rate increase', contribution: 0.22, direction: 'increases-risk', currentValue: '24 /min', trend: '17 to 24 /min', description: 'Upward trend.' },
    { patientId: 'P-SIM-006', name: 'Temperature increase', contribution: 0.12, direction: 'increases-risk', currentValue: '38.1 C', trend: '37.2 to 38.1 C', description: 'Upward trend.' },
    { patientId: 'P-SIM-006', name: 'Systolic BP decline', contribution: 0.09, direction: 'increases-risk', currentValue: '111 mmHg', trend: '124 to 111 mmHg', description: 'Downward trend.' },
  ],
};
export function defaultFactors(pid: string): RiskFactor[] {
  if (DEMO_FACTORS[pid]) return DEMO_FACTORS[pid];
  return [
    { patientId: pid, name: 'Heart rate stability', contribution: 0.3, direction: 'decreases-risk', currentValue: 'stable', trend: 'stable in simulated window', description: 'No concerning demo trend.' },
    { patientId: pid, name: 'SpO2 stability', contribution: 0.28, direction: 'decreases-risk', currentValue: 'stable', trend: 'stable in simulated window', description: 'No concerning demo trend.' },
    { patientId: pid, name: 'Blood pressure stability', contribution: 0.2, direction: 'decreases-risk', currentValue: 'stable', trend: 'stable in simulated window', description: 'No concerning demo trend.' },
    { patientId: pid, name: 'Temperature stability', contribution: 0.12, direction: 'decreases-risk', currentValue: 'stable', trend: 'stable in simulated window', description: 'No concerning demo trend.' },
    { patientId: pid, name: 'Respiratory rate stability', contribution: 0.1, direction: 'decreases-risk', currentValue: 'stable', trend: 'stable in simulated window', description: 'No concerning demo trend.' },
  ];
}
