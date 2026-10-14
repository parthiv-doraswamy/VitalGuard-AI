import { Link } from 'react-router-dom';
import { SectionCard } from '../components/ui/Primitives.tsx';
import { RiskBadge } from '../components/ui/Badges.tsx';
import { RiskTrajectoryChart } from '../components/charts/Trajectory.tsx';
import { RISK_STYLES } from '../theme/tokens.ts';
import { useSimulation } from '../store/useSimulation.ts';
import { riskDelta } from '../components/patients/DetailModels.tsx';
export function TrajCard({ patientId }: { patientId: string }) {
  const { risks } = useSimulation();
  const r = risks[patientId];
  if (!r) return null;
  const delta = riskDelta(r);
  const s = RISK_STYLES[r.level];
  return (
    <div className="mt-4">
      <SectionCard eyebrow="Trajectory" title="Risk trajectory" hint="Signal over the 2-hour window · thresholds at 65 / 85"
        label="Risk trajectory" action={<RiskBadge level={r.level} score={r.score} />}>
        <div className="grid lg:grid-cols-[minmax(0,1fr)_240px] gap-4 items-stretch">
          <div className="rounded-2xl border border-slate-200/60 dark:border-white/[0.07] bg-slate-50/50 dark:bg-white/[0.02] p-3">
            <RiskTrajectoryChart data={r.trajectory} labels={r.trajectoryLabels} height={260} id={`vg-traj-${patientId}`} />
          </div>
          <div className="rounded-2xl border border-slate-200/60 dark:border-white/[0.07] p-4 bg-white dark:bg-white/[0.02]">
            <p className="eyebrow !text-[10px]">Trajectory summary</p>
            <dl className="mt-2 space-y-2 text-sm">
              <div className="flex justify-between gap-2"><dt className="text-slate-400">Direction</dt><dd className="font-bold capitalize">{r.trend}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-400">Change</dt><dd className="font-bold tabular-nums">{delta > 0 ? '+' : ''}{delta} pts</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-400">Window</dt><dd className="font-bold">2h</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-400">Latest</dt><dd className="font-bold tabular-nums">{r.trajectory[r.trajectory.length - 1]} / 100</dd></div>
            </dl>
            <div className="mt-3 h-2 rounded-full overflow-hidden flex" aria-hidden>
              <span className="h-full" style={{ width: '30%', background: '#0d9488' }} />
              <span className="h-full" style={{ width: '35%', background: '#d97706' }} />
              <span className="h-full" style={{ width: '20%', background: '#ea580c' }} />
              <span className="h-full flex-1" style={{ background: '#e11d48' }} />
            </div>
            <p className={`text-xs mt-3 font-bold ${s.text}`}>Review recommended.</p>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
export { Link };
