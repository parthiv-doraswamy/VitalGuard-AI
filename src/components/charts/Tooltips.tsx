import type { TooltipProps } from 'recharts';
import { formatClock } from '../../utils/format.ts';

function Shell({ title, rows }: { title: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-lg text-xs dark:bg-slate-900 dark:border-slate-700 min-w-[150px]">
      <p className="font-bold text-slate-400 text-[10px] uppercase tracking-wider">{title}</p>
      <div className="mt-1.5 space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <span className="text-slate-500 inline-flex items-center gap-1.5">
              {r.color && <span className="h-2 w-2 rounded-full" style={{ background: r.color }} aria-hidden />}
              {r.label}
            </span>
            <span className="font-bold tabular-nums">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartTooltip({ active, payload, label, unit }: TooltipProps<number, string> & { unit?: string }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <Shell
      title={String(label ?? formatClock(new Date().toISOString()))}
      rows={payload.map((p) => ({
        label: String(p.name ?? p.dataKey),
        value: `${p.value}${unit ? ` ${unit}` : ''}`,
        color: typeof p.color === 'string' ? p.color : typeof p.payload === 'object' && p.payload !== null ? undefined : undefined,
      }))}
    />
  );
}

export function RiskTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const v = payload[0]?.value;
  return <Shell title={`Window · ${String(label ?? '')}`} rows={[{ label: 'Risk signal', value: `${v} / 100`, color: '#0d9488' }]} />;
}
