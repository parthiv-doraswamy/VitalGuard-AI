import { AlertTriangle, Inbox, Play, WifiOff } from 'lucide-react';

export function LoadingState({ label = 'Loading data…' }: { label?: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="space-y-3 page-enter">
      <div className="relative overflow-hidden rounded-[24px] p-6" style={{ background: 'linear-gradient(120deg,#0a1128,#0c3f4a)' }} aria-hidden>
        <div className="skel h-6 w-1/3 !bg-white/10" /><div className="skel h-10 w-2/3 mt-3 !bg-white/10" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="skel h-4 w-1/2" /><div className="skel h-8 w-2/3" /><div className="skel h-3 w-full" />
          </div>
        ))}
      </div>
      <div className="card p-5 space-y-2">
        <div className="skel h-5 w-1/3" /><div className="skel h-10 w-full" /><div className="skel h-10 w-full" /><div className="skel h-10 w-5/6" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function EmptyState({ icon, title, hint, action }: {
  icon?: 'inbox' | 'alert'; title: string; hint?: string; action?: React.ReactNode;
}) {
  const Icon = icon === 'alert' ? AlertTriangle : Inbox;
  return (
    <div className="card p-10 text-center page-enter relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-24 opacity-60" style={{ background: 'radial-gradient(400px 100px at 50% 0%, rgba(13,148,136,.12), transparent)' }} aria-hidden />
      <span className="relative mx-auto grid place-items-center h-12 w-12 rounded-2xl text-teal-700 bg-teal-50 border border-teal-200/60 dark:bg-teal-950/50 dark:text-teal-300 dark:border-teal-900/60">
        <Icon className="h-6 w-6" aria-hidden />
      </span>
      <p className="relative mt-3 font-display font-bold text-[16px]">{title}</p>
      {hint && <p className="relative text-sm text-slate-500 mt-1 max-w-md mx-auto">{hint}</p>}
      {action && <div className="relative mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({ title, hint, onRetry }: { title: string; hint?: string; onRetry?: () => void }) {
  return (
    <div className="card p-10 text-center" role="alert">
      <span className="mx-auto grid place-items-center h-12 w-12 rounded-2xl bg-amber-50 text-amber-500 border border-amber-200/60 dark:bg-amber-950/50">
        <AlertTriangle className="h-6 w-6" aria-hidden />
      </span>
      <p className="mt-3 font-display font-bold text-[16px]">{title}</p>
      {hint && <p className="text-sm text-slate-500 mt-1">{hint}</p>}
      {onRetry && <button onClick={onRetry} className="btn-primary mt-4">Retry</button>}
    </div>
  );
}

export function BackendOffline({ onUseDemo }: { onUseDemo?: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs px-3.5 py-3 rounded-2xl bg-amber-50 border border-amber-200/70 text-amber-800 dark:bg-amber-950/40 dark:border-amber-900/60 dark:text-amber-200">
      <WifiOff size={14} aria-hidden />
      <span><strong>Backend unavailable.</strong> Continuing with the local synthetic dataset.</span>
      {onUseDemo && <button onClick={onUseDemo} className="btn-secondary !py-1 !px-2.5 !text-xs ml-auto"><Play size={12} /> Use local data</button>}
    </div>
  );
}
