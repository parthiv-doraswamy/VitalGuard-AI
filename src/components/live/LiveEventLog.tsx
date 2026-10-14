import { useLiveEvents } from '../../services/useLiveEvents.ts';

function clock(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** Newest-first log of committed backend events, unique by event_id. */
export function LiveEventLog({ limit = 25 }: { limit?: number }) {
  const { log } = useLiveEvents();
  const rows = log.slice(0, limit);
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No committed events received in this view yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs" aria-label="Live event log">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-slate-400">
            <th className="py-1.5 pr-3">Event</th><th className="pr-3">Seq</th><th className="pr-3">Committed</th>
            <th className="pr-3">Patient</th><th className="pr-3">Score</th><th className="pr-3">Alert</th>
            <th className="pr-3">Delivery</th><th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ event, origin, latencyMs, localLatencyMs }) => (
            <tr key={event.event_id} className="border-t border-slate-100 dark:border-white/5" data-testid="live-log-row" data-event-id={event.event_id}>
              <td className="py-1.5 pr-3 font-bold tabular-nums">#{event.event_id}</td>
              <td className="pr-3 tabular-nums">{event.sequence ?? '—'}</td>
              <td className="pr-3 tabular-nums">{clock(event.timestamp)}</td>
              <td className="pr-3">{event.patient_id}</td>
              <td className="pr-3 tabular-nums">{event.prediction.risk_score} <span className="text-slate-400">{event.prediction.risk_level}</span></td>
              <td className="pr-3">{event.alert ? `#${event.alert.id}` : '—'}</td>
              <td className="pr-3 tabular-nums">
                {localLatencyMs !== null ? `${localLatencyMs} ms submit→here` : latencyMs !== null ? `≈${latencyMs} ms` : '—'}
              </td>
              <td>{origin === 'recovered' ? <span className="text-amber-700 font-semibold">recovered</span> : 'live'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
