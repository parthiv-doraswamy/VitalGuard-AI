import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { ChartTooltip } from './Tooltips.tsx';
import { RISK_STYLES } from '../../theme/tokens.ts';
const DONUT = [RISK_STYLES.critical.hex, RISK_STYLES.high.hex, RISK_STYLES.moderate.hex, RISK_STYLES.low.hex];
export function RiskDonut({ items }: { items: { name: string; value: number }[] }) {
  const total = items.reduce((s, i) => s + i.value, 0);
  return (
    <div className="min-w-0">
      <div className="flex justify-center">
        <div style={{ height: 196, width: 196, minWidth: 196 }} className="shrink-0 relative overflow-hidden" role="img" aria-label={`Risk distribution across ${total} patients`}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={items} dataKey="value" nameKey="name" innerRadius={62} outerRadius={84} paddingAngle={3} strokeWidth={0}>
                {items.map((_, i) => <Cell key={i} fill={DONUT[i % DONUT.length]} />)}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 grid place-items-center text-center pointer-events-none">
            <div><p className="metric text-[30px] leading-none">{total}</p><p className="text-[10px] uppercase tracking-[0.12em] text-slate-400 font-bold mt-1">Patients</p></div>
          </div>
        </div>
      </div>
      <ul className="mt-5 space-y-2 min-w-0">
        {items.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2.5 text-sm min-w-0 rounded-xl px-2.5 py-1.5 hover:bg-slate-50 dark:hover:bg-white/[0.04] transition-colors">
            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: DONUT[i % DONUT.length], boxShadow: `0 0 8px ${DONUT[i % DONUT.length]}55` }} aria-hidden />
            <span className="text-slate-600 dark:text-slate-300 truncate font-medium">{d.name}</span>
            <span className="ml-auto font-bold tabular-nums shrink-0">{d.value}</span>
            <span className="text-xs text-slate-400 tabular-nums w-10 text-right shrink-0">{total ? Math.round((d.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
