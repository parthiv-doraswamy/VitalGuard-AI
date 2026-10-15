import { Link } from 'react-router-dom';
import { Radio, RefreshCw, TriangleAlert } from 'lucide-react';
import { DemoPill, RiskBadge, TrendPill } from '../ui/Badges.tsx';
import { useLiveEvents } from '../../services/useLiveEvents.ts';
import type { RiskLevel } from '../../types/index.ts';

const RISK_LEVELS: RiskLevel[] = ['low', 'moderate', 'high', 'critical'];
const VITAL_LABELS: Record<string, string> = {
  heart_rate: 'HR', spo2: 'SpO₂', systolic_bp: 'SBP', diastolic_bp: 'DBP', respiratory_rate: 'RR', temperature: 'Temp',
};

function clock(iso: string | null | undefined) {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function Metric({ label, value, testId, hint }: { label: string; value: string | number; testId: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200/80 dark:border-white/10 px-3 py-2 min-w-0" title={hint}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</p>
      <p className="text-sm font-bold tabular-nums truncate" data-testid={testId}>{value}</p>
    </div>
  );
}

/**
 * Receiver view of the synchronized backend stream. It renders exactly what the
 * backend committed and broadcast (or what catch-up recovered); it never computes a score.
 */
export function LiveStatusPanel({ compact = false }: { compact?: boolean }) {
  const { status, session, latest, eventCount, recoveredCount, alertsReceived, latency, clock: clockSample, errors, producer } = useLiveEvents();
  const connected = status === 'connected';
  const event = latest?.event;
  const level = RISK_LEVELS.includes(event?.prediction.risk_level as RiskLevel) ? event?.prediction.risk_level as RiskLevel : null;
  const ownStream = producer?.ownsSession(session?.session_id) ?? false;
  const sessionLabel = !session ? 'No backend stream yet' : session.status === 'stopped'
    ? `Stopped${session.stop_reason ? ` (${session.stop_reason.replace(/_/g, ' ')})` : ''}`
    : session.status === 'paused' ? 'Paused by producer' : 'Streaming';

  return (
    <section className="card p-5 min-w-0" aria-label="Synchronized backend stream" data-testid="live-status-panel">
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid place-items-center h-10 w-10 rounded-xl bg-teal-50 border border-teal-100 dark:bg-teal-950/40 dark:border-teal-900 shrink-0" aria-hidden>
          <Radio size={18} className="text-teal-700 dark:text-teal-300" />
        </span>
        <div className="min-w-0">
          <p className="eyebrow">Synchronized backend stream</p>
          <h3 className="font-display font-bold text-[16px] tracking-tight flex flex-wrap items-center gap-2">
            <span data-testid="live-session-status">{sessionLabel}</span>
            {session && session.scenario !== 'mixed' && <TrendPill trend={session.scenario} />}
            <DemoPill label="SYNTHETIC · FICTIONAL" />
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {ownStream ? 'This device is the producer.' : 'Receiver mode — updates arrive from the backend; nothing is started here.'}
            {session && <> · {session.mode === 'cohort' ? <span className="font-semibold">all {session.patient_count ?? ''} cohort patients</span> : <>patient <span className="font-semibold">{session.patient_id}</span></>} · session <code data-testid="live-session-id">{session.session_id.slice(0, 8)}</code></>}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold border ${connected ? 'border-teal-200 bg-teal-50 text-teal-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
            <span className={`h-2 w-2 rounded-full ${connected ? 'bg-teal-500 pulse-dot' : 'bg-amber-500'}`} aria-hidden />
            <span data-testid="live-connection-status">{status}</span>
          </span>
          {compact && <Link to="/live-demo" className="btn-ghost !py-1.5 !text-[13px]">Live demo</Link>}
        </div>
      </div>

      <div className={`mt-4 grid gap-3 ${compact ? 'lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]' : 'md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]'}`}>
        <div className="rounded-xl border border-slate-200/80 dark:border-white/10 p-3 min-w-0" aria-live="polite">
          {event ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs text-slate-500">Latest event</p>
                <span className="text-sm font-extrabold tabular-nums" data-testid="live-latest-event-id">#{event.event_id}</span>
                {event.sequence !== null && <span className="text-xs text-slate-500 tabular-nums">seq {event.sequence}</span>}
                {latest?.origin === 'recovered' && <span className="text-[10px] font-bold uppercase text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5">recovered</span>}
                <span className="ml-auto">{level && <RiskBadge level={level} score={event.prediction.risk_score} />}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                <span data-testid="live-latest-patient">{event.patient_id}</span> · committed <time dateTime={event.timestamp} data-testid="live-latest-timestamp">{clock(event.timestamp)}</time>
                {' '}· model <span data-testid="live-latest-model">{event.model_version}</span>
                {' '}· score <span className="font-bold" data-testid="live-latest-score">{event.prediction.risk_score}</span>
              </p>
              <dl className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {Object.entries(VITAL_LABELS).map(([key, label]) => (
                  <div key={key} className="flex gap-1"><dt className="text-slate-400">{label}</dt><dd className="font-semibold tabular-nums">{event.observation[key] ?? '—'}</dd></div>
                ))}
              </dl>
              {event.alert && (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-rose-50 border border-rose-200 px-2 py-1 text-xs font-semibold text-rose-700" data-testid="live-latest-alert">
                  <TriangleAlert size={13} aria-hidden /> Alert #{event.alert.id} · {event.alert.title}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">Waiting for the first committed event. Start a stream from the Live demo page on the producing device.</p>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 content-start">
          <Metric label="Events received" value={eventCount} testId="live-events-received" />
          <Metric label="Recovered" value={recoveredCount} testId="live-events-recovered" hint="Events fetched from the REST catch-up endpoint after a reconnect" />
          <Metric label="Alerts" value={alertsReceived} testId="live-alerts-received" />
          <Metric label="Delivery latency" value={latency.lastMs !== null ? `≈${latency.lastMs} ms` : '—'} testId="live-latency-last"
            hint="Backend receipt → delivered here, corrected for clock offset (± half the ping round trip)" />
          <Metric label="Avg latency" value={latency.averageMs !== null ? `≈${latency.averageMs} ms` : '—'} testId="live-latency-average"
            hint={`Average over the last ${latency.samples} live events`} />
          <Metric label="Errors" value={errors.count} testId="live-errors" hint={errors.last ?? 'No errors'} />
        </div>
      </div>
      <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
        <RefreshCw size={12} aria-hidden /> Missed events are recovered from backend history after reconnecting.
        {clockSample && <span>Clock offset {Math.round(clockSample.offsetMs)} ms (±{Math.round(clockSample.rttMs / 2)} ms).</span>}
        {errors.last && <span className="text-amber-700" data-testid="live-last-error">Last error: {errors.last}</span>}
      </p>
    </section>
  );
}
