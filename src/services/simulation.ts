import type { RiskLevel, VitalReading } from '../types/index.ts';
export function riskLevelFor(score: number): RiskLevel {
  if (score >= 85) return 'critical';
  if (score >= 65) return 'high';
  if (score >= 30) return 'moderate';
  return 'low';
}
export function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}
// Deterministic pseudo-noise so reset() reproduces the same trajectory.
export function wobble(tick: number, seed: number): number {
  return Math.sin(tick * 0.9 + seed) * 0.6 + Math.sin(tick * 0.37 + seed * 2) * 0.4;
}
export interface SimTargets { hr: number; spo2: number; sys: number; dia: number; temp: number; rr: number; risk: number; news2: number; }
export function nextReading(prev: VitalReading, scenario: string, tick: number, seed: number, speed: number): VitalReading {
  const d = speed;
  const w = wobble(tick, seed);
  let hr = prev.heartRate, spo2 = prev.spo2, sys = prev.systolicBp, dia = prev.diastolicBp, temp = prev.temperature, rr = prev.respiratoryRate;
  if (scenario === 'worsening') { hr += 1.6*d + w*0.4; spo2 -= 0.35*d + w*0.08; sys -= 0.9*d + w*0.25; dia -= 0.5*d + w*0.15; temp += 0.06*d + w*0.012; rr += 0.5*d + w*0.12; }
  else if (scenario === 'recovering') { hr -= 1.1*d + w*0.35; spo2 += 0.25*d - w*0.06; sys += 0.6*d - w*0.2; dia += 0.4*d - w*0.12; temp -= 0.05*d - w*0.01; rr -= 0.4*d - w*0.1; }
  else { hr += w*0.35; spo2 += w*0.05; sys += w*0.25; dia += w*0.15; temp += w*0.008; rr += w*0.1; }
  return { ...prev, timestamp: new Date().toISOString(), heartRate: clamp(Math.round(hr*10)/10, 40, 180), spo2: clamp(Math.round(spo2*10)/10, 80, 100), systolicBp: clamp(Math.round(sys), 70, 220), diastolicBp: clamp(Math.round(dia), 35, 130), temperature: clamp(Math.round(temp*10)/10, 34, 42), respiratoryRate: clamp(Math.round(rr*10)/10, 6, 45) };
}
export function nextRisk(prev: number, scenario: string, tick: number, seed: number, speed: number): number {
  const w = wobble(tick, seed + 7);
  let n = prev;
  if (scenario === 'worsening') n += 2.4*speed + w*0.5;
  else if (scenario === 'recovering') n -= 1.8*speed + w*0.4;
  else n += w*0.45;
  return clamp(Math.round(n), 2, 97);
}
export function news2For(risk: number, base: number): number {
  const adj = Math.round((risk - 40) / 22);
  return clamp(base + adj, 0, 12);
}
