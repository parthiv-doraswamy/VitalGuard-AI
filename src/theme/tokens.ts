import type { RiskLevel } from '../types/index.ts';

// Centralized risk semantics — single source of truth for labels/colors/thresholds.
// Bands are categories only, not clinically validated.
export const RISK_BANDS = [
  { level: 'critical' as RiskLevel, min: 85, max: 100, label: 'Critical', hint: 'Score ≥ 85' },
  { level: 'high' as RiskLevel, min: 65, max: 84, label: 'High', hint: 'Score 65–84' },
  { level: 'moderate' as RiskLevel, min: 30, max: 64, label: 'Moderate', hint: 'Score 30–64' },
  { level: 'low' as RiskLevel, min: 0, max: 29, label: 'Low', hint: 'Score < 30' },
] as const;

export const ALERT_THRESHOLD = 65;

export const RISK_STYLES: Record<RiskLevel, { text: string; ring: string; badge: string; dot: string; soft: string; hex: string }> = {
  critical: {
    text: 'text-rose-600 dark:text-rose-400',
    ring: 'stroke-rose-500',
    badge: 'bg-rose-50/80 text-rose-700 border-rose-200/70 dark:bg-rose-950/50 dark:text-rose-200 dark:border-rose-900/60',
    dot: 'bg-rose-500',
    soft: 'bg-rose-50 dark:bg-rose-950/40',
    hex: '#e11d48',
  },
  high: {
    text: 'text-orange-600 dark:text-orange-400',
    ring: 'stroke-orange-500',
    badge: 'bg-orange-50/80 text-orange-700 border-orange-200/70 dark:bg-orange-950/50 dark:text-orange-200 dark:border-orange-900/60',
    dot: 'bg-orange-500',
    soft: 'bg-orange-50 dark:bg-orange-950/40',
    hex: '#ea580c',
  },
  moderate: {
    text: 'text-amber-600 dark:text-amber-400',
    ring: 'stroke-amber-400',
    badge: 'bg-amber-50/80 text-amber-700 border-amber-200/70 dark:bg-amber-950/50 dark:text-amber-200 dark:border-amber-900/60',
    dot: 'bg-amber-400',
    soft: 'bg-amber-50 dark:bg-amber-950/40',
    hex: '#d97706',
  },
  low: {
    text: 'text-teal-700 dark:text-teal-300',
    ring: 'stroke-teal-500',
    badge: 'bg-teal-50/80 text-teal-700 border-teal-200/70 dark:bg-teal-950/50 dark:text-teal-200 dark:border-teal-900/60',
    dot: 'bg-teal-500',
    soft: 'bg-teal-50 dark:bg-teal-950/40',
    hex: '#0d9488',
  },
};

// Consistent chart color mapping across the entire application.
export const CHART_COLORS = {
  risk: '#0d9488',
  heartRate: '#e11d48',
  spo2: '#2563eb',
  systolic: '#7c3aed',
  diastolic: '#0d9488',
  temperature: '#ea580c',
  respiratoryRate: '#0891b2',
  primary: '#0d9488',
  grid: '#e2e8f0',
  gridDark: '#1e293b',
} as const;

export const TREND_META = {
  worsening: { label: 'Worsening', arrow: '↗', cls: 'text-red-600 dark:text-red-400' },
  stable: { label: 'Stable', arrow: '→', cls: 'text-slate-500' },
  recovering: { label: 'Recovering', arrow: '↘', cls: 'text-emerald-600 dark:text-emerald-400' },
} as const;
