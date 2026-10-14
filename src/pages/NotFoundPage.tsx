import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader } from '../components/ui/Primitives.tsx';
export function NotFoundPage() {
  return (
    <Shell title="Not found" subtitle="Unknown route">
      <PageHeader eyebrow="Error · 404" title="Page not found" subtitle="This page does not exist."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: '404' }]} />
      <div className="card p-10 text-center mt-4 relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-28 opacity-60" style={{ background: 'radial-gradient(500px 120px at 50% 0%, rgba(13,148,136,.14), transparent)' }} aria-hidden />
        <p className="relative metric text-6xl bg-gradient-to-br from-slate-900 to-teal-700 dark:from-white dark:to-teal-300 bg-clip-text text-transparent">404</p>
        <p className="relative mt-2 text-sm text-slate-500">Check the address or return to the command center.</p>
        <Link to="/dashboard" className="btn-primary mt-5 relative inline-flex"><Compass size={15} aria-hidden />Back to Dashboard</Link>
      </div>
    </Shell>
  );
}
