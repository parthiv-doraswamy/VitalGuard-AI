import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, HeartPulse, ShieldCheck, Stethoscope, UserRound, Users } from 'lucide-react';
import { DEMO_PASSWORD, ROLE_SUMMARY, STAFF, SignInError, signIn, type Role } from '../services/auth.ts';

type RoleOption = { id: Role; title: string; username: string; description: string; icon: typeof ShieldCheck };

const ROLES: RoleOption[] = [
  { id: 'admin', title: 'Admin', username: 'admin.demo', description: 'Everything, incl. stream control and model performance', icon: ShieldCheck },
  { id: 'nurse', title: 'Nurse', username: 'nurse.demo', description: 'All wards: monitoring, live stream and alerts', icon: HeartPulse },
  { id: 'doctor', title: 'Doctor', username: 'doctor.demo', description: 'Only assigned patients, with alert notifications', icon: Stethoscope },
];
const DOCTORS = STAFF.filter((member) => member.role === 'doctor');

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedRole, setSelectedRole] = useState<Role>('admin');
  const [username, setUsername] = useState('admin.demo');
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  function chooseRole(role: RoleOption) {
    setSelectedRole(role.id);
    setUsername(role.username);
    setPassword(DEMO_PASSWORD);
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const member = STAFF.find((item) => item.username === username.trim().toLowerCase());
    if (!member || member.role !== selectedRole) {
      setError('Choose a demo role below to fill in the demo credentials.');
      return;
    }
    setBusy(true);
    try {
      await signIn(member.username, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== '/login' ? from : '/dashboard', { replace: true });
    } catch (caught) {
      setError(caught instanceof SignInError ? caught.message : 'Sign-in failed. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f8fb] text-slate-900">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
        <section className="relative hidden overflow-hidden bg-slate-950 px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
          <div className="absolute inset-0 vg-grid-bg opacity-20" aria-hidden />
          <div className="absolute -right-24 top-24 h-96 w-96 rounded-full bg-teal-500/20 blur-3xl" aria-hidden />
          <div className="relative flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-teal-400 text-slate-950"><Activity size={24} /></div>
            <div><p className="font-display text-lg font-extrabold tracking-tight">VitalGuard AI</p><p className="text-xs text-slate-400">Synthetic monitoring workspace</p></div>
          </div>
          <div className="relative max-w-xl py-16">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-400/30 bg-teal-400/10 px-3 py-1.5 text-xs font-semibold text-teal-200"><span className="h-2 w-2 rounded-full bg-teal-300" /> DEMO ENVIRONMENT</p>
            <h1 className="font-display text-5xl font-extrabold leading-[1.08] tracking-tight xl:text-6xl">A clearer view of every signal.</h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-slate-300">Explore simulated patient profiles, risk indicators and review workflows in one focused workspace.</p>
            <div className="mt-10 grid max-w-md grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4"><Users className="mb-3 text-teal-300" size={20} /><p className="text-sm font-semibold">Role-based walkthrough</p><p className="mt-1 text-xs leading-5 text-slate-400">Choose a persona to get started</p></div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4"><Activity className="mb-3 text-teal-300" size={20} /><p className="text-sm font-semibold">Live simulation</p><p className="mt-1 text-xs leading-5 text-slate-400">Synthetic signals and alerts</p></div>
            </div>
          </div>
          <p className="relative text-xs text-slate-500">Demo only · Synthetic data · Not for clinical use</p>
        </section>

        <section className="flex items-center justify-center px-4 py-10 sm:px-8">
          <div className="w-full max-w-xl">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-teal-700 text-white"><Activity size={22} /></div>
              <div><p className="font-display text-lg font-extrabold">VitalGuard AI</p><p className="text-xs text-slate-500">Synthetic monitoring workspace</p></div>
            </div>
            <div className="mb-7">
              <p className="eyebrow clinical-kicker">Welcome to VitalGuard</p>
              <h2 className="mt-2 font-display text-3xl font-extrabold tracking-tight">Enter the demo workspace</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Pick a demo role below. The username and demo password fill in automatically.</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {ROLES.map((role) => {
                const Icon = role.icon;
                const active = selectedRole === role.id;
                return (
                  <button key={role.id} type="button" onClick={() => chooseRole(role)}
                    aria-pressed={active}
                    className={`rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md ${active ? 'border-teal-600 bg-teal-50 ring-2 ring-teal-600/15' : 'border-slate-200 bg-white'}`}>
                    <span className={`mb-3 grid h-10 w-10 place-items-center rounded-xl ${active ? 'bg-teal-700 text-white' : 'bg-slate-100 text-slate-600'}`}><Icon size={20} /></span>
                    <span className="block text-sm font-bold">{role.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">{role.description}</span>
                    <span className={`mt-3 block text-xs font-semibold ${active ? 'text-teal-800' : 'text-slate-400'}`}>{active ? 'Selected' : 'Use this role'} →</span>
                  </button>
                );
              })}
            </div>

            <form className="mt-6 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" onSubmit={submit}>
              <div className="flex items-center justify-between gap-3">
                <div><p className="text-sm font-bold">Demo sign in</p><p className="mt-1 text-xs text-slate-500">Selected persona: <span className="font-semibold capitalize text-teal-800">{selectedRole}</span></p></div>
                <span className="rounded-lg bg-slate-100 p-2 text-slate-600"><UserRound size={18} /></span>
              </div>
              <div>
                <label htmlFor="demo-username" className="mb-1.5 block text-xs font-semibold text-slate-600">Username</label>
                <input id="demo-username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} className="field w-full" />
              </div>
              <div>
                <label htmlFor="demo-password" className="mb-1.5 block text-xs font-semibold text-slate-600">Demo password</label>
                <input id="demo-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} className="field w-full" />
              </div>
              {selectedRole === 'doctor' && (
                <div>
                  <label htmlFor="demo-doctor" className="mb-1.5 block text-xs font-semibold text-slate-600">Doctor account</label>
                  <select id="demo-doctor" value={username} onChange={(event) => setUsername(event.target.value)} className="field w-full">
                    {DOCTORS.map((doctor) => <option key={doctor.username} value={doctor.username}>{doctor.display_name} · {doctor.wards.join(', ')}</option>)}
                  </select>
                </div>
              )}
              <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600" data-testid="role-access">
                <span className="font-semibold capitalize">{selectedRole} access:</span> {ROLE_SUMMARY[selectedRole]}
              </p>
              {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
              <button type="submit" className="btn-primary w-full !py-3" disabled={busy}>Open demo workspace <ArrowRight size={16} /></button>
              <p className="text-center text-[11px] leading-5 text-slate-400">Demo accounts with a shared demo password. The backend checks the role on every protected request.</p>
            </form>
            <p className="mt-5 text-center text-xs leading-5 text-slate-400">Synthetic demonstration data only. Not clinically validated and not for real patient care.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
