import { Moon, Sun, Gauge, Database, Info, MonitorPlay, Palette } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { BackendOffline } from '../components/ui/States.tsx';
import { useSimulation } from '../store/useSimulation.ts';
import { APP_CONFIG } from '../services/config.ts';
import { RiskEnginePanel } from '../components/settings/RiskEnginePanel.tsx';
import { ModelEvaluationPanel } from '../components/settings/ModelEvaluationPanel.tsx';
import { ExplainabilityWorkbench } from '../components/settings/ExplainabilityWorkbench.tsx';
import { News2DemoCalculator } from '../components/settings/News2DemoCalculator.tsx';
function Seg<T extends string | number>({ options, value, onPick, label }: { options: readonly T[]; value: T; onPick: (v: T) => void; label: string }) {
  const labelOf = (o: T): string => {
    if (typeof o === 'number') return `${o}×`;
    if (o === 'api') return 'Backend API';
    if (o === 'demo') return 'Demo data';
    return o;
  };
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o)} onClick={() => onPick(o)} aria-pressed={value === o}
          className={`tab-btn capitalize ${value === o ? 'tab-on' : 'tab-off'}`}>{labelOf(o)}</button>
      ))}
    </div>
  );
}
export function SettingsPage() {
  const { speed, setSpeed, multiplier, setMultiplier, dataSource, setDataSource, theme, setTheme, running } = useSimulation();
  return (
    <Shell title="Settings" subtitle="Workspace configuration">
      <PageHeader eyebrow="Configuration" title="Settings"
        subtitle="Monitoring, appearance, data source and system information."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Settings' }]} />
      <div className="mt-4"><RiskEnginePanel /></div>
      <div className="mt-4"><ModelEvaluationPanel /></div>
      <div className="mt-4"><ExplainabilityWorkbench /></div>
      <div className="mt-4"><News2DemoCalculator /></div>
      <div className="mt-4 grid lg:grid-cols-2 gap-4 items-start">
        <SectionCard eyebrow="Data" title="Data source" hint="Where patient data comes from" label="Environment">
          <Seg options={['demo', 'api'] as const} value={dataSource} onPick={setDataSource} label="Data source" />
          <p className="text-xs text-slate-500 mt-3 flex items-start gap-1.5"><Database size={13} aria-hidden className="mt-0.5 shrink-0" />Local synthetic set or backend API with automatic fallback. API base: <span className="font-mono">{APP_CONFIG.apiBaseUrl}</span></p>
          {dataSource === 'demo' && <div className="mt-3"><BackendOffline onUseDemo={() => setDataSource('demo')} /></div>}
        </SectionCard>
        <SectionCard eyebrow="Playback" title="Monitoring" hint="Live signal playback" label="Simulation">
          <p className="eyebrow flex items-center gap-1.5"><MonitorPlay size={13} aria-hidden />Signal speed</p>
          <div className="mt-2"><Seg options={['slow', 'normal', 'fast'] as const} value={speed} onPick={setSpeed} label="Simulation speed" /></div>
          <p className="eyebrow mt-4 flex items-center gap-1.5"><Gauge size={13} aria-hidden />Multiplier</p>
          <div className="mt-2"><Seg options={[1, 2] as const} value={multiplier} onPick={setMultiplier} label="Speed multiplier" /></div>
          <p className="text-xs text-slate-500 mt-3">Currently <strong>{running ? 'streaming' : 'paused'}</strong> · affects vitals, risk, charts and alerts.</p>
        </SectionCard>
        <SectionCard eyebrow="Theme" title="Appearance" hint="Light or dark clinical theme" label="Appearance">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Theme">
            {(['light', 'dark'] as const).map((t) => (
              <button key={t} onClick={() => setTheme(t)} aria-pressed={theme === t} className={`tab-btn capitalize inline-flex items-center gap-1.5 ${theme === t ? 'tab-on' : 'tab-off'}`}>
                {t === 'light' ? <Sun size={14} aria-hidden /> : <Moon size={14} aria-hidden />}{t}
              </button>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded-2xl border border-slate-200 bg-[#eef2f7] p-3 dark:border-white/10">
              <p className="text-[11px] font-bold text-slate-500 flex items-center gap-1"><Palette size={12} aria-hidden />Light</p>
              <div className="mt-2 h-10 rounded-xl bg-white border border-slate-200" aria-hidden />
            </div>
            <div className="rounded-2xl border border-slate-700 p-3" style={{ background: '#0a1128' }}>
              <p className="text-[11px] font-bold text-slate-400">Dark</p>
              <div className="mt-2 h-10 rounded-xl border border-white/10 bg-white/[0.06]" aria-hidden />
            </div>
          </div>
        </SectionCard>
        <SectionCard eyebrow="Build" title="System information" hint="Build and connection state" label="System information">
          <dl className="grid sm:grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/50 dark:border-white/[0.06] p-3"><dt className="eyebrow">Frontend version</dt><dd className="font-bold mt-1">{APP_CONFIG.version}</dd></div>
            <div className="rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/50 dark:border-white/[0.06] p-3"><dt className="eyebrow">API mode</dt><dd className="font-bold mt-1">{dataSource === 'demo' ? 'Local dataset' : 'Backend API + fallback'}</dd></div>
            <div className="rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/50 dark:border-white/[0.06] p-3"><dt className="eyebrow">Environment</dt><dd className="font-bold mt-1 tabular-nums">{APP_CONFIG.env}</dd></div>
            <div className="rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/50 dark:border-white/[0.06] p-3"><dt className="eyebrow">Endpoints</dt><dd className="font-mono text-[11px] mt-1">/api/v1/model/evaluation · /api/v1/risk/explain</dd></div>
          </dl>
        </SectionCard>
        <div className="lg:col-span-2">
          <SectionCard eyebrow="Safety" title="Prototype notice" hint="Product boundaries" label="Demo notice">
            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed flex items-start gap-2"><Info size={15} aria-hidden className="mt-0.5 shrink-0 text-teal-600" />All patient data is <strong>synthetic</strong>. VitalGuard AI is a <strong>decision-support prototype</strong> — review recommended, no diagnosis, no treatment advice, no validated performance claims.</p>
          </SectionCard>
        </div>
      </div>
    </Shell>
  );
}
