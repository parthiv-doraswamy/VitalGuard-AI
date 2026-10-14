import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, Bell, BarChart3, LayoutDashboard, Radio, Settings, ShieldCheck, Users, Menu, X, History } from 'lucide-react';
import { useSimulation } from '../../store/useSimulation.ts';

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/live-demo', label: 'Live demo', icon: Radio },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/history', label: 'History', icon: History },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { alerts } = useSimulation();
  const open = alerts.filter((a) => a.status === 'open').length;
  return (
    <nav className="px-3 py-3 space-y-1" aria-label="Primary">
      {links.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} onClick={onNavigate}
          className={({ isActive }) => `vg-navlink group ${isActive
            ? 'text-white shadow-[0_8px_22px_-8px_rgba(13,148,136,0.7)]'
            : 'text-slate-400 hover:text-slate-100 hover:bg-white/[0.06]'}`}>
          {({ isActive }) => (
            <>
              {isActive && <span className="absolute inset-0 rounded-xl" style={{ background: 'linear-gradient(90deg,#0f766e,#0d9488 55%,#0891b2)' }} aria-hidden />}
              {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-1 rounded-full bg-teal-200" aria-hidden />}
              <span className={`relative grid place-items-center h-8 w-8 rounded-lg transition-all ${isActive ? 'bg-white/15' : 'bg-white/[0.05] group-hover:bg-white/10'}`}>
                <Icon size={17} aria-hidden />
              </span>
              <span className="relative">{label}</span>
              {label === 'Alerts' && open > 0 && (
                <span className={`relative ml-auto min-w-5 h-5 px-1.5 rounded-full grid place-items-center text-[11px] font-bold tabular-nums ${isActive ? 'bg-white text-teal-800' : 'bg-rose-500 text-white'}`}>{open}</span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3 px-5 h-[76px]">
      <span className="relative h-11 w-11 rounded-2xl grid place-items-center text-white shrink-0" style={{ background: 'linear-gradient(135deg,#0f766e,#0d9488 45%,#155e75)', boxShadow: '0 8px 24px -6px rgba(45,212,191,.6)' }} aria-hidden>
        <Activity size={22} strokeWidth={2.5} />
        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-teal-300" />
      </span>
      <div className="min-w-0">
        <p className="font-display font-extrabold tracking-tight leading-none text-[16px] text-white">VitalGuard <span className="bg-gradient-to-r from-teal-300 to-cyan-300 bg-clip-text text-transparent">AI</span></p>
        <p className="text-[11px] text-slate-400 mt-1 leading-tight">Clinical intelligence</p>
      </div>
    </div>
  );
}

function SideFoot() {
  return (
    <div className="mt-auto p-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.04] p-3.5">
        <p className="text-[11px] font-bold flex items-center gap-1.5 text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 pulse-dot" aria-hidden />
          System operational
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400 flex items-start gap-1.5">
          <ShieldCheck size={13} aria-hidden className="mt-0.5 shrink-0" />
          <span>Prototype · synthetic data, not for clinical use.</span>
        </p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="w-[264px] shrink-0 hidden lg:flex flex-col min-h-screen sticky top-0 h-screen text-slate-200" style={{ background: 'linear-gradient(180deg,#0a1128 0%,#0d1630 55%,#0c1a33 100%)' }} aria-label="Desktop navigation">
      <Brand />
      <p className="eyebrow !text-slate-500 px-6 pt-2">Workspace</p>
      <div className="flex-1 overflow-y-auto"><NavItems /></div>
      <SideFoot />
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="lg:hidden flex items-center gap-2 px-4 h-14 border-b border-slate-200/80 bg-white/90 backdrop-blur dark:bg-slate-900/90 dark:border-slate-800 sticky top-0 z-30">
        <button className="icon-btn" aria-label={open ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
        <span className="flex items-center gap-2 font-display font-extrabold text-sm">
          <span className="h-7 w-7 rounded-lg text-white grid place-items-center" style={{ background: 'linear-gradient(135deg,#0f766e,#0891b2)' }}><Activity size={15} /></span>
          VitalGuard AI
        </span>
        <span className="ml-auto text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-md bg-slate-900/[0.04] text-slate-500 dark:bg-white/[0.07]">PROTOTYPE</span>
      </div>
      {open && (
        <div className="lg:hidden fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Site navigation">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute left-0 top-0 bottom-0 w-72 shadow-2xl flex flex-col text-slate-200" style={{ background: 'linear-gradient(180deg,#0a1128,#0d1630)' }}>
            <div className="flex items-center justify-between pr-2"><div className="flex-1"><Brand /></div>
              <button className="touch-target p-2 rounded-xl text-slate-400 hover:bg-white/10" aria-label="Close navigation menu" onClick={() => setOpen(false)}><X size={20} /></button>
            </div>
            <div className="flex-1 overflow-y-auto"><NavItems onNavigate={() => setOpen(false)} /></div>
            <SideFoot />
          </div>
        </div>
      )}
    </>
  );
}
