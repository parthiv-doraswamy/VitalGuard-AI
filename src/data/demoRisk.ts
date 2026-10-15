import type { RiskFactor } from '../types/index.ts';
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
