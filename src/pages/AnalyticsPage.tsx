import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { DemoPill } from '../components/ui/Badges.tsx';
import { RiskDonut } from '../components/charts/Donut.tsx';
import { MiniBars } from '../components/charts/Vitals.tsx';
import { RiskTrajectoryChart } from '../components/charts/Trajectory.tsx';
import { Sparkline } from '../components/ui/premium.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { useScope } from '../store/useScope.ts';
export function AnalyticsPage() {
  const { risks } = useSimulation();
  const { patients, alerts } = useScope();
  const vals = patients.map((p) => risks[p.id]).filter(Boolean);
  const dist = [
    { name: 'Critical', value: vals.filter((r) => r.level === 'critical').length },
    { name: 'High', value: vals.filter((r) => r.level === 'high').length },
    { name: 'Moderate', value: vals.filter((r) => r.level === 'moderate').length },
    { name: 'Low', value: vals.filter((r) => r.level === 'low').length },
  ];
  const avg = Math.round(vals.reduce((s, r) => s + r.score, 0) / Math.max(1, vals.length));
  const wors = patients.filter((p) => risks[p.id].trend === 'worsening').length;
  const stab = patients.filter((p) => risks[p.id].trend === 'stable').length;
  const rec = patients.filter((p) => risks[p.id].trend === 'recovering').length;
  const scen = [
    { name: 'Stable', value: patients.filter((p) => p.scenario === 'stable').length },
    { name: 'Worsening', value: patients.filter((p) => p.scenario === 'worsening').length },
    { name: 'Recovering', value: patients.filter((p) => p.scenario === 'recovering').length },
  ];
  const vol = [
    { name: 'Open', value: alerts.filter((a) => a.status === 'open').length },
    { name: 'Ack', value: alerts.filter((a) => a.status === 'acknowledged').length },
    { name: 'Resolved', value: alerts.filter((a) => a.status === 'resolved').length },
  ];
  const hero = risks['P-SIM-003'];
  const hero2 = risks['P-SIM-006'];
  const rec1 = risks['P-SIM-004'];
  const open = alerts.filter((a) => a.status === 'open').length;
  const trendRows = Object.values(risks).slice(0, 8).flatMap((r) => r.trajectory).slice(-18);
  return (
    <Shell title="Analytics" subtitle="Cohort intelligence workspace">
      <PageHeader eyebrow="Cohort intelligence" title="Analytics"
        subtitle="Risk distribution, trajectory comparison and signal activity across the monitored cohort."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Analytics' }]}
        actions={<DemoPill label="DEMO ANALYTICS" />} />
      <div className="mt-4 grid grid-cols-2 xl:grid-cols-4 gap-3 md:gap-4 stagger">
        {[
          { l: 'Patients', val: String(patients.length), h: 'Monitored cohort', spark: trendRows, color: '#0d9488' },
          { l: 'Average risk score', val: String(avg), h: 'Mean cohort signal', spark: trendRows, color: '#0891b2' },
          { l: 'Open alerts', val: String(open), h: 'Requires review', spark: [1, 2, 1, 3, 2, open, open], color: '#ea580c' },
          { l: 'Worsening trajectories', val: String(wors), h: `${stab} stable · ${rec} recovering`, spark: trendRows, color: '#e11d48' },
        ].map(({ l, val, h, spark, color }) => (
          <div key={l} className="card card-hover p-4 sm:p-5 relative overflow-hidden">
            <div className="absolute inset-x-0 top-0 h-[3px] opacity-70" style={{ background: `linear-gradient(90deg, ${color}, transparent)` }} aria-hidden />
            <p className="eyebrow">{l}</p>
            <div className="flex items-end justify-between gap-2 mt-2">
              <div><p className="metric text-3xl">{val}</p><p className="text-[11px] text-slate-400 mt-0.5">{h}</p></div>
              <div className="w-20 opacity-90"><Sparkline data={spark} color={color} height={32} /></div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid lg:grid-cols-5 gap-4 items-start">
        <div className="lg:col-span-3">
          <SectionCard eyebrow="Distribution" title="Risk distribution" hint="Cohort severity" label="Risk distribution">
            <RiskDonut items={dist} />
          </SectionCard>
        </div>
        <div className="lg:col-span-2 space-y-4">
          <SectionCard eyebrow="Mix" title="Patient trajectory" hint="Cohort trajectory mix" label="Scenario mix">
            <MiniBars data={scen} />
          </SectionCard>
          <SectionCard eyebrow="Signals" title="Alert activity" hint="Signals by status" label="Alerts by status">
            <MiniBars data={vol} colors={['#e11d48', '#d97706', '#0d9488']} />
          </SectionCard>
        </div>
      </div>
      <div className="mt-4">
        <SectionCard eyebrow="Comparison" title="Trajectory comparison" hint="Worsening vs recovering signals" label="Trajectory comparison">
          {hero && <RiskTrajectoryChart data={hero.trajectory} labels={hero.trajectoryLabels} height={190} id="vg-analytics-hero" />}
          <ul className="mt-3 space-y-1.5 text-xs">
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-teal-600" aria-hidden /><strong>P-SIM-003</strong><span className="text-slate-400">worsening · {hero?.trajectory.join(' → ')}</span></li>
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-orange-500" aria-hidden /><strong>P-SIM-006</strong><span className="text-slate-400">worsening · {hero2?.trajectory.join(' → ')}</span></li>
            <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-cyan-500" aria-hidden /><strong>P-SIM-004</strong><span className="text-slate-400">recovering · {rec1?.trajectory.join(' → ')}</span></li>
          </ul>
        </SectionCard>
      </div>
    </Shell>
  );
}
