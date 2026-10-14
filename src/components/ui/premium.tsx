import type { ReactNode } from 'react';

export function Sparkline({ data, color, height = 36, width = 120, id }: { data: number[]; color: string; height?: number; width?: number; id?: string }) {
  if (data.length === 0) return <div style={{ height }} aria-hidden />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = Math.max(1e-6, max - min);
  const pts = data.map((v, i) => {
    const x = data.length === 1 ? width / 2 : (i / (data.length - 1)) * width;
    const y = height - 4 - ((v - min) / span) * (height - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const gid = id ?? `vg-${Math.round(min * 7)}-${data.length}`;
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden className="block w-full overflow-visible">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.32} />
          <stop offset="100%" stopColor={color} stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${pts} ${width},${height}`} fill={`url(#${gid})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={data.length === 1 ? width / 2 : width} cy={Number(pts.split(' ').pop()!.split(',')[1])} r={3} fill={color} stroke="#fff" strokeWidth={1.5} />
    </svg>
  );
}

export function RingScore({ value, size = 120, stroke = 11, color, trackClass = 'stroke-slate-100 dark:stroke-slate-800', label }: { value: number; size?: number; stroke?: number; color: string; trackClass?: string; label?: string }) {
  const r = 60;
  const C = 2 * Math.PI * r;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label ?? `Score ${value} of 100`}>
      <svg viewBox="0 0 140 140" width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx="70" cy="70" r={r} fill="none" className={trackClass} strokeWidth={stroke} />
        <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${(Math.max(0, Math.min(100, value)) / 100) * C} ${C}`} style={{ transition: 'stroke-dasharray .7s cubic-bezier(.22,.68,.32,1)' }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="metric leading-none" style={{ fontSize: size * 0.3 }}>{value}</p>
          <p className="text-[10px] text-slate-400 font-bold mt-0.5">/ 100</p>
        </div>
      </div>
    </div>
  );
}

export function StatusDot({ tone = 'emerald', pulse }: { tone?: 'emerald' | 'rose' | 'amber' | 'slate'; pulse?: boolean }) {
  const c = tone === 'emerald' ? 'bg-emerald-500' : tone === 'rose' ? 'bg-rose-500' : tone === 'amber' ? 'bg-amber-400' : 'bg-slate-300';
  return <span className={`h-2 w-2 rounded-full shrink-0 ${c} ${pulse ? 'pulse-dot' : ''}`} aria-hidden />;
}

export function SectionHeader({ eyebrow, title, hint, action }: { eyebrow?: string; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 min-w-0">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h3 className="font-display font-bold text-[16px] tracking-tight mt-0.5">{title}</h3>
        {hint && <p className="text-xs text-slate-500 mt-0.5">{hint}</p>}
      </div>
      {action && <div className="ml-auto shrink-0">{action}</div>}
    </div>
  );
}

export function LiveEcg({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 600 120" className={className} aria-hidden preserveAspectRatio="none">
      <path d="M0 62 H150 L168 62 L178 62 L186 30 L196 92 L204 48 L212 62 H280 L296 62 L304 24 L316 96 L324 44 L332 62 H420 L436 62 L444 36 L454 88 L462 52 L470 62 H600"
        fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        strokeDasharray="120 60" className="animate-vg-ecg" opacity={0.9} />
      <path d="M0 62 H150 L168 62 L178 62 L186 30 L196 92 L204 48 L212 62 H280 L296 62 L304 24 L316 96 L324 44 L332 62 H420 L436 62 L444 36 L454 88 L462 52 L470 62 H600"
        fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" opacity={0.12} />
    </svg>
  );
}
