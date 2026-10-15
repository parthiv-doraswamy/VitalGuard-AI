import { Stethoscope } from 'lucide-react';
import { SectionCard } from '../ui/Primitives.tsx';
import { STAFF } from '../../services/auth.ts';
import { useSimulation } from '../../store/useSimulation.ts';

/** Demo staff accounts and each doctor's assigned patients (admin only). Source: backend/app/data/cohort.json. */
export function StaffDirectory() {
  const { patients } = useSimulation();
  return (
    <SectionCard eyebrow="Access" title="Staff and patient assignments" hint="Alerts are pushed only to the assigned doctor" label="Staff directory">
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="table-head"><tr><th scope="col" className="!pl-3">Account</th><th scope="col">Role</th><th scope="col">Wards</th><th scope="col">Assigned patients</th></tr></thead>
          <tbody>
            {STAFF.map((member) => {
              const assigned = patients.filter((patient) => patient.assignedDoctor === member.username);
              return (
                <tr key={member.username} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="!pl-3 py-2"><p className="font-semibold flex items-center gap-1.5">{member.role === 'doctor' && <Stethoscope size={13} aria-hidden className="text-teal-600" />}{member.display_name}</p><p className="text-[11px] text-slate-500 font-mono">{member.username}</p></td>
                  <td className="capitalize">{member.role}</td>
                  <td className="text-xs text-slate-500">{member.wards.join(', ')}</td>
                  <td className="text-xs tabular-nums">{member.role === 'doctor' ? `${assigned.length} · ${assigned.slice(0, 4).map((p) => p.id).join(', ')}${assigned.length > 4 ? '…' : ''}` : 'All patients'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-slate-400">Fictional demo accounts sharing the demo password. Assignments come from the shared cohort file used by the backend.</p>
    </SectionCard>
  );
}
