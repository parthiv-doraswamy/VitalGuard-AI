import { useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CHART_COLORS } from '../../theme/tokens.ts';
import { RiskTooltip } from './Tooltips.tsx';
export function RiskTrajectoryChart({ data, labels, height = 240, id = 'vg-risk-fill' }: { data: number[]; labels: string[]; height?: number; id?: string }) {
  const rows = useMemo(() => data.map((v, i) => ({ name: labels[i] ?? `t${i}`, risk: v })), [data, labels]);
  return (
    <div style={{ height, minWidth: 0, width: '100%' }} className="overflow-hidden" role="img" aria-label={`Risk trajectory, latest ${data[data.length - 1]} of 100`}>
      <ResponsiveContainer width="99%" height="100%" minWidth={0}>
        <AreaChart data={rows} margin={{ top: 12, right: 14, bottom: 4, left: -14 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.risk} stopOpacity={0.34} />
              <stop offset="100%" stopColor={CHART_COLORS.risk} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e2e8f0" strokeOpacity={0.6} vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} minTickGap={28} interval="preserveStartEnd" />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={34} />
          <Tooltip content={<RiskTooltip />} cursor={{ stroke: '#14b8a6', strokeDasharray: '4 4' }} />
          <ReferenceLine y={65} stroke="#ea580c" strokeDasharray="6 4" strokeOpacity={0.7} />
          <ReferenceLine y={85} stroke="#e11d48" strokeDasharray="6 4" strokeOpacity={0.7} />
          <Area type="monotone" dataKey="risk" stroke="none" fill={`url(#${id})`} />
          <Line type="monotone" dataKey="risk" stroke={CHART_COLORS.risk} strokeWidth={3} dot={{ r: 3.5, fill: '#fff', strokeWidth: 2.5, stroke: CHART_COLORS.risk }} activeDot={{ r: 5.5, strokeWidth: 2 }} name="Risk signal" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
