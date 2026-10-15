import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, ShieldCheck, Waves } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { EmptyState } from '../components/ui/States.tsx';
import { SummaryCards } from '../components/dashboard/SummaryCards.tsx';
import { PriorityTable, TriageMatrix } from '../components/dashboard/Tables.tsx';
import { RiskDonut } from '../components/charts/Donut.tsx';
import { FilterBar, useFilterState } from '../components/patients/FilterBar.tsx';
import { HeroPatient, RecentAlerts, filterCohort } from '../components/dashboard/Hero.tsx';
import { LiveEcg } from '../components/ui/premium.tsx';
import { RISK_BANDS } from '../theme/tokens.ts';
import { useSimulation } from '../store/useSimulation.ts';
import { useScope } from '../store/useScope.ts';

export function DashboardPage() {
  const { risks, latest, tick, running } = useSimulation();
  const { patients, alerts, scope } = useScope();
  const [filters, setFilters] = useFilterState();
  const filtered = useMemo(() => filterCohort(patients, risks, filters), [patients, risks, filters]);
  const dist = useMemo(() => {
    const v = patients.map((p) => risks[p.id]).filter(Boolean);
    return [
      { name: 'Critical', value: v.filter((r) => r.level === 'critical').length },
      { name: 'High', value: v.filter((r) => r.level === 'high').length },
      { name: 'Moderate', value: v.filter((r) => r.level === 'moderate').length },
      { name: 'Low', value: v.filter((r) => r.level === 'low').length },
    ];
  }, [patients, risks]);
  const openAlerts = alerts.filter((a) => a.status === 'open').length;
  // The highest-risk patient this user can see is the one to review first.
  const heroPatient = patients.reduce<typeof patients[number] | undefined>(
    (best, p) => (!best || (risks[p.id]?.score ?? 0) > (risks[best.id]?.score ?? 0) ? p : best), undefined);
  const hero = heroPatient ? risks[heroPatient.id] : undefined;
  const heroVitals = heroPatient ? latest[heroPatient.id] : undefined;
  return (
    <Shell title="Command Center" subtitle="Real-time clinical intelligence overview">
      <section className="clinical-panel relative overflow-hidden rounded-[24px] p-6 sm:p-8 lg:p-9" aria-label="Clinical intelligence overview">
        <div className="absolute inset-0 vg-grid-bg opacity-35" aria-hidden />
        <div className="absolute -top-24 right-[8%] h-72 w-72 rounded-full blur-3xl opacity-40 animate-vg-drift" style={{ background: 'radial-gradient(circle,rgba(94,234,212,.65),transparent 70%)' }} aria-hidden />
        <div className="absolute right-0 top-0 h-full w-[48%] opacity-[0.28] hidden lg:block" aria-hidden>
          <LiveEcg className="h-full w-full text-teal-700 dark:text-teal-300" />
        </div>
        <div className="relative max-w-2xl">
          <p className="eyebrow clinical-kicker inline-flex items-center gap-2">
            <span className={`h-1.5 w-1.5 rounded-full ${running ? 'bg-emerald-500 pulse-dot' : 'bg-slate-300'}`} aria-hidden />
            SIMULATED CLINICAL WORKSPACE · t+{tick}
          </p>
          <h2 className="font-display text-[32px] sm:text-[40px] leading-[1.06] font-extrabold tracking-tight mt-2 text-slate-900 dark:text-slate-50">See the signals.<br className="hidden sm:block" /> Prioritise the review.</h2>
          <p className="text-sm sm:text-[15px] clinical-muted mt-3 leading-relaxed max-w-xl">A unified view of {patients.length} {scope === 'assigned' ? 'assigned ' : ''}synthetic patient profiles, changing vital-sign scenarios, risk signals and review priorities. For demonstration and evaluation only.</p>
          <div className="mt-5 flex flex-wrap items-center gap-2.5">
            <Link to={`/patients/${heroPatient?.id ?? ''}`} className="btn-primary">Review priority patient <ArrowUpRight size={15} aria-hidden /></Link>
            <Link to="/alerts" className="btn-secondary">Open alert center <span className="inline-grid min-w-5 h-5 px-1 place-items-center rounded-md bg-slate-100 text-slate-700 text-[11px]">{openAlerts}</span></Link>
          </div>
        </div>
      </section>
      <div className="mt-6">
        <PageHeader eyebrow="Patient monitoring" title="Patient Monitoring Overview"
          subtitle="Live patient state, risk signals and review priorities in one place."
          crumbs={[{ label: 'Dashboard' }]} />
      </div>
      <div className="mt-5"><SummaryCards patients={patients} risks={risks} openAlerts={openAlerts} /></div>
      {hero && heroVitals && heroPatient && <HeroPatient hero={hero} vitals={heroVitals} patient={heroPatient} />}
      <div className="mt-4"><FilterBar value={filters} onChange={setFilters} resultCount={filtered.length} /></div>
      <div className="mt-4 grid xl:grid-cols-[minmax(0,1fr)_370px] gap-4 items-start">
        <SectionCard eyebrow="Triage" title="Patient priority queue" hint="Sorted by risk signal · select a row to open the patient"
          label="Prioritized patient list"
          action={<Link to="/patients" className="btn-secondary !py-1.5 !text-[13px]">View all <ArrowRight size={14} aria-hidden /></Link>}>
          {filtered.length === 0
            ? <EmptyState title="No patients match these filters." hint="Adjust search or clear filters." />
            : <PriorityTable patients={filtered} risks={risks} latest={latest} compact />}
        </SectionCard>
        <SectionCard eyebrow="Distribution" title="Risk overview" hint="Cohort severity at a glance" label="Risk distribution">
          <RiskDonut items={dist} />
          <div className="mt-4 space-y-1.5">
            {RISK_BANDS.map((b) => (
              <div key={b.level} className="flex items-center gap-2 text-[11px] text-slate-500">
                <span className="w-16 font-bold capitalize">{b.label}</span>
                <span className="tabular-nums">{b.hint}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 flex items-start gap-1.5 text-[11px] text-slate-400"><ShieldCheck size={13} aria-hidden className="mt-0.5 shrink-0" />Bands guide review order only.</p>
        </SectionCard>
      </div>
      <div className="mt-4 grid xl:grid-cols-2 gap-4 items-start">
        <SectionCard eyebrow="Triage map" title="Prioritization matrix" hint="Risk signal vs trend" label="Triage matrix">
          <TriageMatrix patients={patients} risks={risks} />
        </SectionCard>
        <SectionCard eyebrow="Signals" title="Recent alerts" hint="Latest review signals" label="Recent alerts"
          action={<Link to="/alerts" className="btn-ghost !py-1.5 !text-[13px]">Alert center <ArrowRight size={14} aria-hidden /></Link>}>
          <RecentAlerts alerts={alerts} />
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-400"><Waves size={13} aria-hidden />Streaming updates while monitoring is live.</p>
        </SectionCard>
      </div>
    </Shell>
  );
}
