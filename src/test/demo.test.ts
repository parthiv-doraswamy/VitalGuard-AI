import { describe, it, expect } from 'vitest';
import { demoDataService } from '../services/demoDataService.ts';
import { nextReading, nextRisk, riskLevelFor } from '../services/simulation.ts';
import { resolveDataSource } from '../services/dataProvider.ts';

describe('demo mode works without backend', () => {
  it('resolves to demo by default', () => { expect(resolveDataSource()).toBe('demo'); });
  it('patient list renders (40 synthetic patients, each assigned to a doctor)', () => {
    const ps = demoDataService.listPatients();
    expect(ps).toHaveLength(40);
    expect(ps.map((p) => p.id)).toContain('P-SIM-003');
    expect(ps.every((p) => p.name && p.assignedDoctor)).toBe(true);
  });
  it('hero patient has worsening trajectory', () => {
    const r = demoDataService.risk('P-SIM-003');
    expect(r?.trajectory).toEqual([32, 41, 55, 70, 82, 87]);
    expect(r?.news2).toBe(7);
  });
  it('vitals render for detail', () => {
    // Recovering patients start from abnormal shared-cohort baselines.
    const v = demoDataService.latestVitals('P-SIM-004');
    expect(v?.heartRate).toBeGreaterThan(95);
    expect(demoDataService.vitalsHistory('P-SIM-003').length).toBeGreaterThan(3);
  });
  it('risk panel + factors render', () => {
    expect(demoDataService.risk('P-SIM-003')?.score).toBe(87);
    expect(demoDataService.factors('P-SIM-003').length).toBe(5);
  });
  it('alerts + acknowledgement data', () => {
    expect(demoDataService.alerts().length).toBeGreaterThan(0);
  });
});

describe('simulation engine', () => {
  it('worsening increases risk, recovering decreases, stable stays bounded', () => {
    const w = nextRisk(50, 'worsening', 3, 1, 1);
    const r = nextRisk(50, 'recovering', 3, 1, 1);
    expect(w).toBeGreaterThan(50);
    expect(r).toBeLessThan(50);
  });
  it('worsening vitals drift (HR up, SpO2 down)', () => {
    const base = demoDataService.latestVitals('P-SIM-001')!;
    const n = nextReading(base, 'worsening', 5, 2, 1);
    expect(n.heartRate).toBeGreaterThan(base.heartRate - 1);
    expect(riskLevelFor(90)).toBe('critical');
    expect(riskLevelFor(70)).toBe('high');
  });
  it('simulation updates stay in safe bounds', () => {
    const base = demoDataService.latestVitals('P-SIM-003')!;
    for (let t = 1; t <= 20; t++) {
      const n = nextReading(base, 'worsening', t, 1, 2);
      expect(n.spo2).toBeGreaterThanOrEqual(80);
      expect(n.heartRate).toBeLessThanOrEqual(180);
    }
  });
});
