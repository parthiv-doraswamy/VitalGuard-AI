import { ArrowLeft, Heart, Droplets, Gauge, Thermometer, Wind } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { VitalReading, RiskSignal } from '../../types/index.ts';
import { CHART_COLORS } from '../../theme/tokens.ts';
import { formatTimeAgo } from '../../utils/format.ts';
import type { VitalCardModel } from './VitalCard.tsx';

export function vitalCards(v: VitalReading, first: VitalReading | undefined, history: VitalReading[]): VitalCardModel[] {
  const sparkOf = (pick: (x: VitalReading) => number) => history.map(pick).slice(-14);
  const mk = (a: number, b: number, u: string, badWhenUp: boolean) => {
    const d = Math.round((b - a) * 10) / 10;
    const rising = d > 0;
    const bad = d !== 0 && (badWhenUp ? rising : !rising);
    return { text: `${rising ? '+' : ''}${d} ${u} · window`, up: d === 0 ? null : rising, bad };
  };

  const f = first ?? v;
  const hr = mk(f.heartRate, v.heartRate, 'bpm', true);
  const spo2 = mk(f.spo2, v.spo2, 'pts', false);
  const sys = mk(f.systolicBp, v.systolicBp, 'mmHg', false);
  const dia = mk(f.diastolicBp, v.diastolicBp, 'mmHg', false);
  const temp = mk(f.temperature, v.temperature, '°C', true);
  const rr = mk(f.respiratoryRate, v.respiratoryRate, '/min', true);
  const upd = formatTimeAgo(v.timestamp);
  return [
    { icon: Heart, label: 'Heart rate', value: `${Math.round(v.heartRate)} bpm`, delta: hr.text, up: hr.bad ? true : hr.up, spark: sparkOf((x) => x.heartRate), color: CHART_COLORS.heartRate, iconCls: 'text-rose-500 bg-rose-50 dark:bg-rose-950/60', updated: upd, range: '60–100' },
    { icon: Droplets, label: 'SpO₂', value: `${Math.round(v.spo2)}%`, delta: spo2.text, up: spo2.bad ? true : spo2.up, spark: sparkOf((x) => x.spo2), color: CHART_COLORS.spo2, iconCls: 'text-cyan-600 bg-cyan-50 dark:bg-cyan-950/60', updated: upd, range: '95–100%' },
    { icon: Gauge, label: 'Systolic BP', value: `${v.systolicBp} mmHg`, delta: sys.text, up: sys.bad ? true : sys.up, spark: sparkOf((x) => x.systolicBp), color: CHART_COLORS.systolic, iconCls: 'text-violet-500 bg-violet-50 dark:bg-violet-950/60', updated: upd, range: '90–120' },
    { icon: Gauge, label: 'Diastolic BP', value: `${v.diastolicBp} mmHg`, delta: dia.text, up: dia.bad ? true : dia.up, spark: sparkOf((x) => x.diastolicBp), color: CHART_COLORS.diastolic, iconCls: 'text-teal-600 bg-teal-50 dark:bg-teal-950/60', updated: upd, range: '60–80' },
    { icon: Thermometer, label: 'Temperature', value: `${v.temperature.toFixed(1)} °C`, delta: temp.text, up: temp.bad ? true : temp.up, spark: sparkOf((x) => x.temperature), color: CHART_COLORS.temperature, iconCls: 'text-orange-500 bg-orange-50 dark:bg-orange-950/60', updated: upd, range: '36.1–37.2°' },
    { icon: Wind, label: 'Respiratory rate', value: `${Math.round(v.respiratoryRate)} /min`, delta: rr.text, up: rr.bad ? true : rr.up, spark: sparkOf((x) => x.respiratoryRate), color: CHART_COLORS.respiratoryRate, iconCls: 'text-cyan-600 bg-cyan-50 dark:bg-cyan-950/60', updated: upd, range: '12–20' },
  ];
}

export function DetailHeader({ id, ward, bed, age, sex, scenario, updated }: {
  id: string; ward: string; bed: string; age: number; sex: string; scenario: string; updated: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <Link to="/patients" className="btn-secondary !py-1.5 !text-[13px]"><ArrowLeft size={14} aria-hidden /> Back</Link>
      <h2 className="font-display text-[22px] font-extrabold tracking-tight ml-1">Patient {id}</h2>
      <span className="text-sm text-slate-500">{ward} · Bed {bed} · Age {age} · {sex}</span>
      <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-teal-50 text-teal-700 border border-teal-200/70 dark:bg-teal-950/50 dark:text-teal-200 dark:border-teal-900/60 capitalize">Trajectory: {scenario}</span>
      <span className="text-[11px] text-slate-400 tabular-nums ml-auto">Updated {formatTimeAgo(updated)}</span>
    </div>
  );
}

export function riskDelta(r: RiskSignal): number {
  return r.trajectory[r.trajectory.length - 1] - r.trajectory[0];
}
