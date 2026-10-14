import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartTooltip } from './Tooltips.tsx';
const grid = { stroke: '#e2e8f0', strokeOpacity: 0.6, vertical: false } as const;
export function VitalLine({ data, lines, height = 170, unit }: {
  data: Record<string, unknown>[]; lines: { key: string; color: string; name: string }[]; height?: number; unit?: string;
}) {
  return (
    <div style={{ height, minWidth: 0, width: '100%' }} className="overflow-hidden" role="img" aria-label={`${lines.map((l) => l.name).join(' and ')} trend chart`}>
      <ResponsiveContainer width="99%" height="100%" minWidth={0}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -10 }}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="t" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} minTickGap={30} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} domain={['auto', 'auto']} width={38} />
          <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ stroke: '#14b8a6', strokeDasharray: '4 4' }} />
          {lines.map((l) => <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2.5} dot={false} activeDot={{ r: 4, strokeWidth: 2 }} />)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function VitalSpark({ data, color, height = 36 }: { data: number[]; color: string; height?: number }) {
  const rows = data.map((v, i) => ({ i, v }));
  return (
    <div style={{ height, minWidth: 0, width: '100%' }} className="overflow-hidden" aria-hidden>
      <ResponsiveContainer width="99%" height="100%" minWidth={0}>
        <LineChart data={rows} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.75} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function MiniBars({ data, colors }: { data: { name: string; value: number }[]; colors?: string[] }) {
  const palette = colors ?? ['#0d9488', '#0891b2', '#14b8a6', '#2dd4bf'];
  return (
    <div style={{ height: 210, minWidth: 0, width: '100%' }} className="overflow-hidden" role="img" aria-label="Bar chart">
      <ResponsiveContainer width="99%" height="100%" minWidth={0}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(13,148,136,0.08)' }} />
          <Bar dataKey="value" radius={[8, 8, 3, 3]} maxBarSize={46}>
            {data.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
