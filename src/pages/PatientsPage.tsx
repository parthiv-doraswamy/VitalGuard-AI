import { useMemo, useState } from 'react';


import { Shell } from '../components/layout/Shell.tsx';

import { LayoutGrid, Table2 } from 'lucide-react';
import { PageHeader } from '../components/ui/Primitives.tsx';
import { EmptyState } from '../components/ui/States.tsx';
import { FilterBar, useFilterState } from '../components/patients/FilterBar.tsx';
import { PatientRows, PatientCards } from '../components/patients/Directory.tsx';
import { useSimulation } from '../store/useSimulation.ts';

const PAGE = 6;
export function PatientsPage() {
  const { patients, risks, latest } = useSimulation();
  const [filters, setFilters] = useFilterState();
  const [view, setView] = useState<'table' | 'cards'>('table');
  const [page, setPage] = useState(0);
  const rows = useMemo(() => {
    const out = patients
      .filter((p) => !filters.q || p.id.toLowerCase().includes(filters.q.toLowerCase()))
      .filter((p) => filters.ward === 'All' || p.ward === filters.ward)
      .filter((p) => filters.level === 'All' || risks[p.id]?.level === filters.level.toLowerCase());
    out.sort((a, b) => {
      if (filters.sort === 'spo2') return (latest[a.id]?.spo2 ?? 0) - (latest[b.id]?.spo2 ?? 0);
      if (filters.sort === 'hr') return (latest[b.id]?.heartRate ?? 0) - (latest[a.id]?.heartRate ?? 0);
      if (filters.sort === 'updated') return +new Date(b.updatedAt) - +new Date(a.updatedAt);
      return (risks[b.id]?.score ?? 0) - (risks[a.id]?.score ?? 0);
    });
    return out;
  }, [patients, risks, latest, filters]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const safePage = Math.min(page, pages - 1);
  const slice = rows.slice(safePage * PAGE, safePage * PAGE + PAGE);
  const onFilter = (v: typeof filters) => { setFilters(v); setPage(0); };
  return (
    <Shell title="Patients" subtitle="Monitored patient directory">
      <PageHeader eyebrow={`Census · ${patients.length} patients`} title="Patients"
        subtitle="Monitor patient state, vital trends, and risk signals across wards."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Patients' }]}
        actions={(
          <div className="inline-flex rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden bg-white dark:bg-slate-900" role="group" aria-label="View mode">
            <button onClick={() => setView('table')} aria-pressed={view === 'table'} aria-label="Table view" className={`p-2 transition-all ${view === 'table' ? 'text-white' : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}`} style={view === 'table' ? { background: 'linear-gradient(135deg,#0f766e,#0891b2)' } : undefined}><Table2 size={16} /></button>
            <button onClick={() => setView('cards')} aria-pressed={view === 'cards'} aria-label="Card view" className={`p-2 transition-all ${view === 'cards' ? 'text-white' : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}`} style={view === 'cards' ? { background: 'linear-gradient(135deg,#0f766e,#0891b2)' } : undefined}><LayoutGrid size={16} /></button>
          </div>
        )} />
      <div className="mt-4"><FilterBar value={filters} onChange={onFilter} resultCount={rows.length} /></div>
      {slice.length === 0 ? (
        <div className="mt-4"><EmptyState title="No patients match these filters." hint="Adjust search or clear filters." /></div>
      ) : view === 'table' ? (
        <div className="card overflow-hidden mt-4 !p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[920px]">
              <thead className="table-head sticky top-0">
                <tr>
                  <th scope="col" className="!pl-5">Patient</th><th scope="col">Age / Sex</th><th scope="col">Ward / Bed</th>
                  <th scope="col">Risk</th><th scope="col" className="text-right">NEWS2</th><th scope="col" className="text-right">SpO₂</th>
                  <th scope="col" className="text-right">HR</th><th scope="col">Trend</th><th scope="col">Updated</th>
                  <th scope="col"><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <PatientRows slice={slice} risks={risks} latest={latest} />
            </table>
          </div>
        </div>
      ) : <PatientCards slice={slice} risks={risks} latest={latest} />}
      <div className="mt-4 flex items-center gap-2 text-sm">
        <button disabled={safePage === 0} onClick={() => setPage((p) => Math.max(0, p - 1))} className="btn-secondary !py-1.5">Prev</button>
        <span aria-live="polite" className="text-xs text-slate-500 tabular-nums">Page {safePage + 1} of {pages}</span>
        <button disabled={safePage + 1 >= pages} onClick={() => setPage((p) => p + 1)} className="btn-secondary !py-1.5">Next</button>
      </div>
    </Shell>
  );
}
