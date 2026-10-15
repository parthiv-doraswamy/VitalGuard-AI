import { Pause, Play, RotateCcw, Square, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useSimulation } from '../../store/useSimulation.ts';
import { useMonitoring } from '../../store/useMonitoring.ts';
import { useScope } from '../../store/useScope.ts';

export function SimBar() {
  const { speed, setSpeed, multiplier, setMultiplier, risks, reset } = useSimulation();
  const { patients } = useScope();
  const monitoring = useMonitoring();
  const { running, tick } = monitoring;
  const atRisk = patients.filter((p) => (risks[p.id]?.score ?? 0) >= 65).length;
  return (
    <div className="px-4 md:px-8 pt-4">
      <div className="relative overflow-hidden rounded-2xl border border-teal-100 bg-white px-4 sm:px-5 py-3.5 flex flex-wrap items-center gap-x-4 gap-y-3 shadow-[0_2px_10px_rgba(15,35,65,0.025)] dark:bg-slate-900 dark:border-slate-800" role="region" aria-label="Demo simulation controls">
        <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-teal-400 to-cyan-500" aria-hidden />
        <div className="relative flex items-center gap-3 min-w-0">
          <span className="relative grid place-items-center h-10 w-10 rounded-xl bg-teal-50 border border-teal-100 shrink-0 dark:bg-teal-950/40 dark:border-teal-900" aria-hidden>
            <Activity size={18} className="text-teal-700 dark:text-teal-300" />
            {running && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 pulse-dot" />}
          </span>
          <div className="min-w-0">
            <p className="text-[13px] font-bold flex items-center gap-2 tracking-tight text-slate-800 dark:text-slate-100">
              <span className={`h-2 w-2 rounded-full shrink-0 ${running ? 'bg-emerald-500 pulse-dot' : 'bg-slate-300'}`} aria-hidden />
              LIVE MONITORING
              <span className="font-semibold text-slate-400 tabular-nums">· t+{tick}</span>
              {running && <span className="text-[10px] font-bold tracking-[0.1em] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-md px-1.5 py-0.5" data-testid="monitoring-running">RUNNING</span>}
            </p>
            <p className="text-[11px] text-slate-500 truncate mt-0.5" data-testid="monitoring-source">
              {monitoring.sourceLabel} · <Link to="/patients" className="font-bold text-teal-700 hover:underline">{patients.length} patients</Link>
              {atRisk > 0 && <> · <span className="font-bold text-rose-600">{atRisk} high risk</span></>}
            </p>
            {monitoring.error && <p className="text-[11px] text-rose-600 mt-0.5" role="alert">{monitoring.error}</p>}
          </div>
        </div>
        {monitoring.canControl ? (
          <div className="relative ml-auto flex flex-wrap items-center gap-2">
            {!running && !monitoring.pausedHere && (
              <button onClick={monitoring.start} disabled={monitoring.busy} className="btn-primary !py-1.5 !shadow-none"><Play size={15} aria-hidden /> Start simulation</button>
            )}
            {monitoring.pausedHere && !running && (
              <button onClick={monitoring.resume} className="btn-primary !py-1.5 !shadow-none"><Play size={15} aria-hidden /> Resume</button>
            )}
            {running && monitoring.canPause && (
              <button onClick={monitoring.pause} className="btn !py-1.5 border border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100 font-bold"><Pause size={15} aria-hidden /> Pause</button>
            )}
            {(running || monitoring.pausedHere) && monitoring.source !== 'remote' && (
              <button onClick={monitoring.stop} className="btn-secondary !py-1.5"><Square size={13} aria-hidden /> Stop</button>
            )}
            {!running && !monitoring.pausedHere && <button onClick={reset} className="btn-secondary !py-1.5"><RotateCcw size={14} aria-hidden /> Reset</button>}
            <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
              Speed
              <select aria-label="Simulation speed" value={speed} disabled={running} onChange={(e) => setSpeed(e.target.value as 'slow' | 'normal' | 'fast')} className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] normal-case font-semibold text-slate-700 outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100">
                <option value="slow">Slow</option><option value="normal">Normal</option><option value="fast">Fast</option>
              </select>
            </label>
            <div className="inline-flex rounded-xl border border-slate-200 overflow-hidden bg-slate-50" role="group" aria-label="Speed multiplier">
              {([1, 2] as const).map((m) => (
                <button key={m} onClick={() => setMultiplier(m)} aria-pressed={multiplier === m} disabled={running}
                  className={`touch-target px-3 py-1.5 text-[13px] font-bold tabular-nums transition-all ${multiplier === m ? 'bg-teal-700 text-white' : 'text-slate-600 hover:bg-white'}`}>
                  {m}×
                </button>
              ))}
            </div>
          </div>
        ) : (
          <p className="relative ml-auto text-[11px] text-slate-500 max-w-xs">An admin or nurse starts the stream; your patients' vitals and alerts update here automatically.</p>
        )}
      </div>
    </div>
  );
}
