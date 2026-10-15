import type { ReactNode } from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { can, ROLE_SUMMARY, type Permission } from '../services/auth.ts';
import { useSession } from '../services/useSession.ts';

export function ProtectedRoute() {
  const session = useSession();
  const location = useLocation();
  return session ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
}

/** Renders the page only for roles that hold `permission`; others get an explanation, not a blank screen. */
export function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const session = useSession();
  if (can(session, permission)) return <>{children}</>;
  return (
    <main className="min-h-screen grid place-items-center bg-[#f5f8fb] px-4 dark:bg-slate-950" role="alert">
      <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-amber-50 text-amber-600 dark:bg-amber-950/50"><ShieldAlert size={22} aria-hidden /></span>
        <h1 className="mt-3 font-display text-xl font-extrabold">Not available for your role</h1>
        <p className="mt-2 text-sm text-slate-500">
          You are signed in as <strong className="capitalize">{session?.role}</strong>. {session ? ROLE_SUMMARY[session.role] : ''}
        </p>
        <Link to="/dashboard" className="btn-primary mt-4 inline-flex">Back to dashboard</Link>
      </div>
    </main>
  );
}
