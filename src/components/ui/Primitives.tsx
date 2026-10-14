import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export function PageHeader({ eyebrow, title, subtitle, actions, crumbs }: {
  eyebrow: string; title: string; subtitle?: string; actions?: ReactNode;
  crumbs?: { label: string; to?: string }[];
}) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="min-w-0 max-w-2xl">
        {crumbs && crumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-1.5 flex items-center gap-1 text-xs text-slate-400">
            {crumbs.map((c, i) => (
              <span key={c.label} className="flex items-center gap-1">
                {i > 0 && <ChevronRight size={12} aria-hidden />}
                {c.to ? <Link to={c.to} className="hover:text-teal-700 hover:underline font-medium">{c.label}</Link> : <span aria-current="page" className="text-slate-500">{c.label}</span>}
              </span>
            ))}
          </nav>
        )}
        <p className="eyebrow inline-flex items-center gap-2"><span className="h-px w-6 bg-gradient-to-r from-teal-500 to-cyan-400 inline-block" aria-hidden />{eyebrow}</p>
        <h2 className="font-display text-[28px] md:text-[32px] leading-[1.1] font-extrabold tracking-tight mt-1.5">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{subtitle}</p>}
      </div>
      {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionCard({ title, hint, action, children, label, eyebrow }: {
  title: string; hint?: string; action?: ReactNode; children: ReactNode; label?: string; eyebrow?: string;
}) {
  return (
    <section className="card p-5 sm:p-6 min-w-0 relative overflow-hidden" aria-label={label ?? title}>
      <div className="flex items-start gap-3 min-w-0">
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
          <h3 className="font-display font-bold text-[16px] tracking-tight">{title}</h3>
          {hint && <p className="text-xs text-slate-500 mt-0.5">{hint}</p>}
        </div>
        {action && <div className="ml-auto shrink-0">{action}</div>}
      </div>
      <div className="mt-4 min-w-0">{children}</div>
    </section>
  );
}
