import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Pause, Play, RotateCcw, Square, TriangleAlert } from 'lucide-react';
import { Shell } from '../components/layout/Shell.tsx';
import { PageHeader, SectionCard } from '../components/ui/Primitives.tsx';
import { LiveStatusPanel } from '../components/live/LiveStatusPanel.tsx';
import { LiveEventLog } from '../components/live/LiveEventLog.tsx';
import { liveDemoApi, type LiveDemoConfig, type StreamScenario } from '../services/api.ts';
import { useLiveEvents } from '../services/useLiveEvents.ts';
import { useOnlineStatus } from '../services/pwa.ts';
import type { StreamProducer } from '../services/streamProducer.ts';

const SCENARIOS: { value: StreamScenario; label: string }[] = [
  { value: 'stable', label: 'Stable' },
  { value: 'worsening', label: 'Worsening' },
  { value: 'recovering', label: 'Recovering' },
];
const INTERVALS = [1000, 2000, 3000, 5000];

function ProducerControls({ producer }: { producer: StreamProducer }) {
  const { state } = producer;
  const online = useOnlineStatus();
  const [scenario, setScenario] = useState<StreamScenario>('worsening');
  const [intervalMs, setIntervalMs] = useState(2000);
  const [producerKey, setProducerKey] = useState('');
  const [config, setConfig] = useState<LiveDemoConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    liveDemoApi.config().then(setConfig).catch((error: Error) => setConfigError(error.message));
  }, []);

  const busy = state.phase === 'starting';
  const active = state.phase === 'running' || state.phase === 'paused';
  const ack = state.lastAck;
  const begin = (takeover = false) => producer.start({ scenario, intervalMs, producerKey: producerKey || undefined, takeover });

  return (
    <SectionCard eyebrow="Laptop A" title="Producer controls" label="Producer controls"
      hint="The backend generates, scores and stores each fictional observation; this browser only requests the next one.">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 flex flex-col gap-1">
          Scenario
          <select aria-label="Stream scenario" value={scenario} disabled={active || busy} onChange={(event) => setScenario(event.target.value as StreamScenario)}
            className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] normal-case font-semibold text-slate-700">
            {SCENARIOS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 flex flex-col gap-1">
          Interval
          <select aria-label="Stream interval" value={intervalMs} disabled={active || busy} onChange={(event) => setIntervalMs(Number(event.target.value))}
            className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] normal-case font-semibold text-slate-700">
            {INTERVALS.map((value) => <option key={value} value={value}>{value / 1000}s</option>)}
          </select>
        </label>
        {config?.producer_key_required && (
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 flex flex-col gap-1">
            Producer key
            <input type="password" aria-label="Producer key" value={producerKey} onChange={(event) => setProducerKey(event.target.value)}
              autoComplete="off" className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] normal-case" />
          </label>
        )}
        <div className="flex flex-wrap gap-2">
          {!active && <button type="button" className="btn-primary !py-1.5" disabled={busy || !online} onClick={() => { void begin(); }}><Play size={15} aria-hidden /> Start stream</button>}
          {state.phase === 'running' && <button type="button" className="btn-secondary !py-1.5" onClick={() => { void producer.pause(); }}><Pause size={15} aria-hidden /> Pause</button>}
          {state.phase === 'paused' && <button type="button" className="btn-primary !py-1.5" onClick={() => { void producer.resume(); }}><Play size={15} aria-hidden /> Resume</button>}
          {active && <button type="button" className="btn-secondary !py-1.5" onClick={() => { void producer.stop(); }}><Square size={14} aria-hidden /> Stop stream</button>}
          {state.phase === 'error' && <button type="button" className="btn-secondary !py-1.5" onClick={() => { void producer.retry(); }}><RotateCcw size={14} aria-hidden /> Retry</button>}
          {(state.phase === 'stopped' || state.phase === 'error' || state.phase === 'conflict') && (
            <button type="button" className="btn-ghost !py-1.5" onClick={producer.reset}>New stream</button>
          )}
        </div>
      </div>

      {state.phase === 'conflict' && (
        <div role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p className="font-semibold flex items-center gap-1.5"><TriangleAlert size={14} aria-hidden /> Another producer is already streaming.</p>
          <p className="text-xs mt-0.5">
            Session {state.conflict?.session_id.slice(0, 8)} ({state.conflict?.scenario}, {state.conflict?.status}). Starting here will stop it for every viewer.
          </p>
          <button type="button" className="btn-secondary !py-1 mt-2" onClick={() => { void begin(true); }}>Take over and start</button>
        </div>
      )}
      {state.error && state.phase !== 'conflict' && (
        <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="producer-error">{state.error}</p>
      )}
      {configError && <p className="mt-3 text-xs text-amber-700">Backend unavailable: {configError}</p>}

      <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <div className="rounded-xl border border-slate-200/80 px-3 py-2"><dt className="text-slate-400 uppercase text-[10px] font-bold">State</dt><dd className="font-bold" data-testid="producer-phase">{state.phase}</dd></div>
        <div className="rounded-xl border border-slate-200/80 px-3 py-2"><dt className="text-slate-400 uppercase text-[10px] font-bold">Next sequence</dt><dd className="font-bold tabular-nums">{state.nextSequence}</dd></div>
        <div className="rounded-xl border border-slate-200/80 px-3 py-2"><dt className="text-slate-400 uppercase text-[10px] font-bold">Last acknowledged</dt><dd className="font-bold tabular-nums" data-testid="producer-last-event-id">{ack ? `#${ack.event.event_id}` : '—'}</dd></div>
        <div className="rounded-xl border border-slate-200/80 px-3 py-2"><dt className="text-slate-400 uppercase text-[10px] font-bold">Request round trip</dt><dd className="font-bold tabular-nums">{ack ? `${ack.roundTripMs} ms${ack.duplicate ? ' (retry)' : ''}` : '—'}</dd></div>
      </dl>
    </SectionCard>
  );
}

export function LiveDemoPage() {
  const [params, setParams] = useSearchParams();
  const role = params.get('role') === 'receiver' ? 'receiver' : 'producer';
  const { producer } = useLiveEvents();

  return (
    <Shell title="Live Streaming Demo" subtitle="Two-device synchronized backend stream · fictional data">
      <PageHeader eyebrow="Synchronized demo" title="Live Streaming Demo"
        subtitle="Laptop A produces a backend stream; Laptop B watches it arrive on the normal dashboard. Every value is fictional."
        crumbs={[{ label: 'Dashboard', to: '/dashboard' }, { label: 'Live demo' }]}
        actions={(
          <div className="inline-flex rounded-xl border border-slate-200 overflow-hidden bg-slate-50" role="group" aria-label="Device role">
            {(['producer', 'receiver'] as const).map((value) => (
              <button key={value} type="button" aria-pressed={role === value} onClick={() => setParams({ role: value })}
                className={`px-3 py-1.5 text-[13px] font-bold capitalize ${role === value ? 'bg-teal-700 text-white' : 'text-slate-600 hover:bg-white'}`}>
                {value}
              </button>
            ))}
          </div>
        )} />
      <div className="mt-5 grid gap-4">
        {role === 'producer' && producer && <ProducerControls producer={producer} />}
        {role === 'receiver' && (
          <p className="text-sm text-slate-500">
            Receiver mode only listens. You can also use the normal <Link to="/dashboard" className="font-semibold text-teal-700 hover:underline">dashboard</Link>, which shows the same stream.
          </p>
        )}
        <LiveStatusPanel />
        <SectionCard eyebrow="Event log" title="Committed backend events" hint="Unique by event ID · identical on every connected device" label="Live event log">
          <LiveEventLog />
        </SectionCard>
        <p className="text-[11px] text-slate-400">
          The Start simulation bar above is a separate local simulation that runs only in this browser and is not shared with other devices.
        </p>
      </div>
    </Shell>
  );
}
