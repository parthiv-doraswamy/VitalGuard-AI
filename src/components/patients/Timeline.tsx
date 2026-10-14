import { formatClock, formatTimeAgo } from '../../utils/format.ts';
import type { VitalReading } from '../../types/index.ts';

export interface DemoEvent { at: string; title: string; detail?: string; kind: 'vital' | 'risk' | 'trend' | 'alert' | 'review'; }

export function buildTimeline(history: VitalReading[], riskTrajectory: number[]): DemoEvent[] {
  if (history.length === 0) return [];
  const n = history.length;
  const pick = (i: number) => history[Math.min(n - 1, Math.max(0, i))];
  const first = history[0];
  const last = history[n - 1];
  const mid = pick(Math.floor(n / 2));
  const r0 = riskTrajectory[0] ?? 0;
  const rMid = riskTrajectory[Math.floor(riskTrajectory.length / 2)] ?? r0;
  const rLast = riskTrajectory[riskTrajectory.length - 1] ?? rMid;
  const worsening = rLast >= rMid;
  const events: DemoEvent[] = [
    { at: first.timestamp, title: 'Vital update received', detail: `HR ${Math.round(first.heartRate)} bpm · SpO₂ ${Math.round(first.spo2)}%`, kind: 'vital' },
    { at: mid.timestamp, title: 'Simulated risk updated', detail: `${r0} → ${rMid} (demo signal)`, kind: 'risk' },
    { at: mid.timestamp, title: worsening ? 'Trend classified as worsening' : 'Trend classified as stable', detail: 'Demo trend classifier', kind: 'trend' },
  ];
  if (rLast >= 65 && rMid < 65) {
    events.push({ at: last.timestamp, title: 'Risk signal crossed demo alert level', detail: `${rMid} → ${rLast} · threshold 65`, kind: 'alert' });
  } else {
    events.push({ at: last.timestamp, title: 'Simulated risk updated', detail: `${rMid} → ${rLast} (demo signal)`, kind: 'risk' });
  }
  events.push({ at: last.timestamp, title: 'Review recommended', detail: 'Demo event timeline — not a clinical audit record', kind: 'review' });
  return events;
}

const DOT: Record<DemoEvent['kind'], string> = {
  vital: 'bg-blue-500',
  risk: 'bg-violet-500',
  trend: 'bg-amber-400',
  alert: 'bg-red-500',
  review: 'bg-emerald-500',
};

export function EventTimeline({ events }: { events: DemoEvent[] }) {
  return (
    <ol className="relative ml-1.5 border-l border-slate-200 dark:border-slate-800 space-y-5" aria-label="Demo event timeline">
      {events.map((e, i) => (
        <li key={`${e.at}-${i}`} className="pl-5 relative">
          <span className={`absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full ring-4 ring-white dark:ring-slate-900 ${DOT[e.kind]}`} aria-hidden />
          <p className="text-[11px] font-bold tabular-nums text-slate-400 uppercase tracking-wide">{formatClock(e.at)} · {formatTimeAgo(e.at)}</p>
          <p className="text-sm font-bold mt-0.5">{e.title}</p>
          {e.detail && <p className="text-xs text-slate-500 mt-0.5 tabular-nums">{e.detail}</p>}
        </li>
      ))}
    </ol>
  );
}
