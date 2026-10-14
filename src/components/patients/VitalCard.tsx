import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import type { ComponentType } from 'react';
import { VitalSpark } from '../charts/Vitals.tsx';

export interface VitalCardModel {
  icon: ComponentType<{ size?: number | string; className?: string }>;
  label: string;
  value: string;
  delta: string;
  up: boolean | null;
  spark: number[];
  color: string;
  iconCls: string;
  updated: string;
  range?: string;
}

export function VitalCard({ card }: { card: VitalCardModel }) {
  const { icon: Icon, label, value, delta, up, spark, color, iconCls, updated, range } = card;
  const DeltaIcon = up === null ? Minus : up ? ArrowUp : ArrowDown;
  const deltaCls = up === null ? 'text-slate-400' : up ? 'text-rose-500' : 'text-teal-600 dark:text-teal-400';
  return (
    <div className="card card-hover p-4 flex flex-col min-h-[168px] relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: `linear-gradient(90deg, ${color}, transparent)` }} aria-hidden />
      <div className="flex items-center gap-2">
        <span className={`h-8 w-8 rounded-xl grid place-items-center shrink-0 ${iconCls}`}><Icon size={15} aria-hidden /></span>
        <div className="min-w-0">
          <p className="eyebrow leading-tight">{label}</p>
          {range && <p className="text-[10px] text-slate-400 tabular-nums">Range {range}</p>}
        </div>
      </div>
      <p className="metric text-[27px] leading-none mt-2.5">{value}</p>
      <p className={`text-[11px] font-bold mt-1 inline-flex items-center gap-1 tabular-nums ${deltaCls}`}>
        <DeltaIcon size={12} aria-hidden /> {delta}
      </p>
      <div className="mt-auto pt-2">
        <VitalSpark data={spark} color={color} />
        <p className="text-[10px] text-slate-400 mt-1">Updated {updated}</p>
      </div>
    </div>
  );
}
