import { useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';

export interface FilterState { q: string; ward: string; level: string; sort: string; }

export function FilterBar({ value, onChange, resultCount }: {
  value: FilterState; onChange: (v: FilterState) => void; resultCount: number;
}) {
  const active = (value.ward !== 'All' ? 1 : 0) + (value.level !== 'All' ? 1 : 0) + (value.sort !== 'risk' ? 1 : 0);
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });
  return (
    <div className="card p-3.5 flex flex-wrap gap-2 items-center" role="search" aria-label="Patient search and filters">
      <div className="relative flex-1 min-w-[200px]">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          aria-label="Search patient ID" value={value.q} onChange={(e) => set({ q: e.target.value })}
          placeholder="Search patients… (e.g. P-SIM-003)" className="field w-full !pl-9 !rounded-xl !bg-slate-50/70 dark:!bg-white/[0.04]" />
        {value.q && (
          <button aria-label="Clear search" onClick={() => set({ q: '' })} className="icon-btn !p-1 absolute right-2 top-1/2 -translate-y-1/2">
            <X size={14} />
          </button>
        )}
      </div>
      <select aria-label="Ward filter" value={value.ward} onChange={(e) => set({ ward: e.target.value })} className="field">
        {['All', 'ICU', 'Emergency', 'General Ward', 'Cardiology'].map((w) => <option key={w} value={w}>{w === 'All' ? 'All wards' : w}</option>)}
      </select>
      <select aria-label="Risk filter" value={value.level} onChange={(e) => set({ level: e.target.value })} className="field">
        {['All', 'Critical', 'High', 'Moderate', 'Low'].map((w) => <option key={w} value={w}>{w === 'All' ? 'All risk levels' : w}</option>)}
      </select>
      <select aria-label="Sort patients" value={value.sort} onChange={(e) => set({ sort: e.target.value })} className="field">
        <option value="risk">Sort: Risk</option>
        <option value="hr">Sort: Heart rate</option>
        <option value="spo2">Sort: SpO₂</option>
        <option value="updated">Sort: Last updated</option>
      </select>
      {active > 0 && (
        <button onClick={() => onChange({ ...value, ward: 'All', level: 'All', sort: 'risk' })} className="btn-ghost !text-xs">
          Clear ({active})
        </button>
      )}
      <span className="text-xs text-slate-400 tabular-nums ml-auto inline-flex items-center gap-1.5" aria-live="polite"><span className="h-1.5 w-1.5 rounded-full bg-teal-500" aria-hidden />{resultCount} result{resultCount === 1 ? '' : 's'}</span>
    </div>
  );
}

export function useFilterState(initialSort = 'risk'): [FilterState, (v: FilterState) => void] {
  const [v, setV] = useState<FilterState>({ q: '', ward: 'All', level: 'All', sort: initialSort });
  return useMemo(() => [v, setV], [v]);
}
