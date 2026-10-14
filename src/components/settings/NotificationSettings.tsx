import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, BellOff, Send } from 'lucide-react';
import {
  disablePush, enablePush, getPushStatus, reconcilePush, sendTestPush, setMinSeverity,
  type PushDelivery, type PushState, type Severity,
} from '../../services/notifications.ts';

const UNAVAILABLE_TEXT: Record<string, string> = {
  unsupported: 'This browser does not support Web Push.',
  'needs-install': 'On iPhone and iPad, add VitalGuard to the Home Screen (Share → Add to Home Screen), open it from there, then enable notifications.',
  'insecure-context': 'Notifications need a secure (HTTPS) connection.',
  'server-not-configured': 'Push notifications are not configured on this server.',
};

function deliveryText(delivery: PushDelivery) {
  if (delivery.clicked_at) return 'opened on this device';
  if (delivery.displayed_at) return 'shown on this device';
  if (delivery.status === 'accepted') return 'accepted by the push service (not yet confirmed on the device)';
  if (delivery.status === 'retrying') return `push service error ${delivery.last_status_code ?? ''} — retrying`;
  return delivery.status;
}

/** Explicit, device-level opt-in. Push is optional: the alert center always works. */
export function NotificationSettings() {
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [deliveries, setDeliveries] = useState<PushDelivery[]>([]);

  const refreshStatus = useCallback(async () => {
    const status = await getPushStatus().catch(() => null);
    setDeliveries(status?.deliveries.slice(0, 5) ?? []);
  }, []);

  useEffect(() => {
    reconcilePush().then(setState).catch(() => setState({ kind: 'off' }));
  }, []);
  useEffect(() => { if (state?.kind === 'on') void refreshStatus(); }, [state, refreshStatus]);

  const run = async (action: () => Promise<PushState | void>) => {
    setBusy(true);
    setError('');
    try {
      const next = await action();
      if (next) setState(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card p-4 sm:p-5" aria-labelledby="notifications-heading" data-testid="notification-settings">
      <p className="eyebrow flex items-center gap-1.5"><Bell size={13} aria-hidden /> This device</p>
      <h2 id="notifications-heading" className="font-display text-xl font-extrabold mt-1">Alert notifications</h2>
      <p className="text-xs text-slate-500 mt-1">
        Get a notification when a new synthetic demo alert is created. Notifications never include patient details;
        open the app to review. Alerts always appear in the <Link to="/alerts" className="font-semibold text-teal-700 hover:underline">alert center</Link>, with or without push.
      </p>

      <div className="mt-4" data-testid="push-state">
        {state === null && <p className="text-sm text-slate-500">Checking notification support…</p>}
        {state?.kind === 'unavailable' && <p className="text-sm text-slate-600">{UNAVAILABLE_TEXT[state.reason]} In-app alerts still work.</p>}
        {state?.kind === 'denied' && (
          <p className="text-sm text-slate-600">Notifications are blocked for this site. To turn them on, allow notifications in your browser&apos;s site settings, then return here. In-app alerts still work.</p>
        )}
        {state?.kind === 'revoked' && (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-amber-800">Notifications were turned off in this browser since you enabled them.</p>
            <button type="button" className="btn-primary !py-1.5" disabled={busy} onClick={() => void run(() => enablePush())}>Turn on again</button>
          </div>
        )}
        {state?.kind === 'off' && (
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void run(() => enablePush())}>
            <Bell size={15} aria-hidden /> Enable notifications on this device
          </button>
        )}
        {state?.kind === 'on' && (
          <div className="space-y-3">
            <p className="text-sm font-semibold text-teal-800">Notifications are on for this device.</p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 flex flex-col gap-1">
                Notify me for
                <select aria-label="Minimum alert severity" value={state.minSeverity} disabled={busy}
                  onChange={(event) => {
                    const minSeverity = event.target.value as Severity;
                    void run(async () => { await setMinSeverity(minSeverity); return { ...state, minSeverity }; });
                  }}
                  className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[13px] normal-case font-semibold text-slate-700">
                  <option value="high">High and critical alerts</option>
                  <option value="critical">Critical alerts only</option>
                </select>
              </label>
              <button type="button" className="btn-secondary" disabled={busy}
                onClick={() => void run(async () => { await sendTestPush(); window.setTimeout(() => void refreshStatus(), 3000); })}>
                <Send size={14} aria-hidden /> Send test notification
              </button>
              <button type="button" className="btn-secondary" disabled={busy} onClick={() => void run(() => disablePush())}>
                <BellOff size={14} aria-hidden /> Turn off
              </button>
            </div>
            {deliveries.length > 0 && (
              <ul className="text-xs text-slate-600 space-y-1" data-testid="push-deliveries" aria-label="Recent notifications">
                {deliveries.map((delivery) => (
                  <li key={delivery.delivery_id}>
                    {delivery.kind === 'test' ? 'Test' : `Alert #${delivery.alert_id}`} · {deliveryText(delivery)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    </section>
  );
}
