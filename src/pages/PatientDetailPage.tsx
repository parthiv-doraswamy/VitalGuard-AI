import { Link, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { RiskBadge } from '../components/ui/Badges.tsx';
import { EmptyState } from '../components/ui/States.tsx';
import { VitalCard } from '../components/patients/VitalCard.tsx';
import { DetailHeader, riskDelta, vitalCards } from '../components/patients/DetailModels.tsx';
import { RiskPanel, News2Panel } from '../components/risk/RiskPanels.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { TrajCard } from './TrajCard.tsx';
import { ExplainCard, VitalCharts, AlertList } from './DetailSections.tsx';
import { BackendPatientTimeline } from '../components/patients/BackendPatientTimeline.tsx';
export function fmtAgo(iso: string): string {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m} min ago`;
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}
export function PatientDetailPage() {
  const { patientId = '' } = useParams();
  const { patients, latest, risks, histories } = useSimulation();
  const patient = patients.find((p) => p.id === patientId);
  if (!patient) {
    return (
      <Shell title="Patient not found" subtitle="Directory">
        <EmptyState title={`No patient ${patientId} found.`}
          action={<Link to="/patients" className="btn-primary">Back to directory</Link>} />
      </Shell>
    );
  }
  const v = latest[patient.id];
  const r = risks[patient.id];
  const h = histories[patient.id] ?? [];
  if (!v || !r) return <Shell title="Loading" subtitle="…"><EmptyState title="Loading vitals…" /></Shell>;
  const cards = vitalCards(v, h[0], h);
  const delta = riskDelta(r);
  return (
    <Shell title={`Patient ${patient.id}`} subtitle={`${patient.ward} · Bed ${patient.bed}`}>
      <section className="relative overflow-hidden rounded-[24px] text-white p-6 sm:p-7" style={{ background: 'linear-gradient(115deg,#0a1128 0%,#12294d 45%,#0c3f4a 80%,#0f766e 125%)' }} aria-label="Patient summary">
        <div className="absolute inset-0 vg-grid-bg opacity-40" aria-hidden />
        <DetailHeader id={patient.id} ward={patient.ward} bed={patient.bed} age={patient.age} sex={patient.sex} scenario={patient.scenario} updated={patient.updatedAt} />
        <div className="relative mt-4 flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-300"><MapPin size={13} aria-hidden className="text-teal-300" />{patient.ward} · Bed {patient.bed}</span>
          <RiskBadge level={r.level} score={r.score} />
          <span className="text-[11px] text-slate-400 ml-auto tabular-nums">NEWS2 {r.news2} · {r.trend}</span>
        </div>
      </section>
      <section aria-label="Current vital signs" className="mt-4 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 stagger">
        {cards.map((c) => <VitalCard key={c.label} card={c} />)}
      </section>
      <div className="mt-4 grid lg:grid-cols-[1.15fr_0.85fr] gap-4 items-start">
        <div className="card p-5 sm:p-6"><RiskPanel risk={r} delta={delta} /></div>
        <div className="card p-5 sm:p-6"><News2Panel score={r.news2} /></div>
      </div>
      <TrajCard patientId={patient.id} />
      <ExplainCard patientId={patient.id} />
      <VitalCharts patientId={patient.id} />
      <AlertList patientId={patient.id} />
      <BackendPatientTimeline patientId={patient.id} />
    </Shell>
  );
}
