export type RiskLevel = 'critical' | 'high' | 'moderate' | 'low';
export type TrendDirection = 'worsening' | 'stable' | 'recovering';
export type Scenario = 'stable' | 'worsening' | 'recovering';
export type Ward = 'ICU' | 'Emergency' | 'General Ward' | 'Cardiology';

export interface Patient {
  id: string;
  /** Fictional display name. */
  name: string;
  /** Username of the doctor this patient is assigned to. */
  assignedDoctor: string;
  age: number;
  sex: 'M' | 'F';
  ward: Ward;
  bed: string;
  scenario: Scenario;
  updatedAt: string;
}

export interface VitalReading {
  patientId: string;
  timestamp: string;
  heartRate: number;
  spo2: number;
  systolicBp: number;
  diastolicBp: number;
  temperature: number;
  respiratoryRate: number;
}

export interface RiskSignal {
  patientId: string;
  score: number;
  level: RiskLevel;
  probability: number;
  news2: number;
  trend: TrendDirection;
  trajectory: number[];
  trajectoryLabels: string[];
  updatedAt: string;
}

export interface RiskFactor {
  patientId: string;
  name: string;
  contribution: number;
  direction: 'increases-risk' | 'decreases-risk';
  currentValue: string;
  trend: string;
  description: string;
}

export type AlertSeverity = 'critical' | 'high' | 'moderate' | 'info';
export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export interface AlertItem {
  id: string;
  patientId: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  contributors: string[];
  status: AlertStatus;
  createdAt: string;
  riskBefore?: number;
  riskAfter?: number;
}

export interface SimulationState {
  running: boolean;
  tick: number;
  speed: 'slow' | 'normal' | 'fast';
  multiplier: 1 | 2;
}

export const DEMO_DISCLAIMER = 'All patient data shown in Demo Mode is synthetic and intended only for software demonstration.';
