import { CloudOff, Download, RefreshCw, WifiOff, X } from 'lucide-react';
import { applyUpdate, dismissOfflineReady, dismissUpdate, useOnlineStatus, usePwaState } from '../../services/pwa.ts';
import type { LiveStatus } from '../../services/liveEvents.ts';

function clock(value: number | null) {
  if (value === null) return null;
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/**
 * Honest connectivity banner: offline means no live data; disconnected means what is
 * shown from the backend may be stale. Local synthetic simulation keeps working offline.
 */
export function ConnectionBanner({ liveStatus, lastLiveEventAt }: { liveStatus: LiveStatus; lastLiveEventAt: number | null }) {
  const online = useOnlineStatus();
  const last = clock(lastLiveEventAt);
  if (!online) {
    return (
      <div role="alert" data-testid="offline-banner" className="flex flex-wrap items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
        <WifiOff size={14} aria-hidden />
        <strong>You are offline.</strong>
        <span>The app shell and the local synthetic simulation still work. Backend data (history, alerts, predictions, live stream) is unavailable and is not served from cache.</span>
        <span className="font-semibold" data-testid="stale-since">{last ? `Backend values on screen are from ${last} or earlier and may be out of date.` : 'No live backend data has been received in this session.'}</span>
      </div>
    );
  }
  if (liveStatus !== 'connected') {
    return (
      <div role="status" data-testid="stale-banner" className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        <CloudOff size={14} aria-hidden />
        <strong>{liveStatus === 'offline' ? 'Backend unreachable.' : 'Reconnecting to the backend…'}</strong>
        <span>{last ? `Live values may be stale (last live event ${last}).` : 'Live values are not available yet.'} Missed events are recovered after reconnecting.</span>
      </div>
    );
  }
  return null;
}

/** Asks before switching to a new version; never reloads on its own. */
export function UpdatePrompt() {
  const { needRefresh, offlineReady } = usePwaState();
  if (!needRefresh && !offlineReady) return null;
  return (
    <div role="status" aria-live="polite" data-testid={needRefresh ? 'update-prompt' : 'offline-ready'}
      className="fixed z-30 left-4 right-4 sm:right-auto sm:left-6 bottom-[max(1rem,env(safe-area-inset-bottom))] sm:w-[380px] rounded-2xl border border-teal-200 bg-white p-4 shadow-xl dark:bg-slate-900 dark:border-teal-900">
      {needRefresh ? (
        <>
          <p className="text-sm font-bold flex items-center gap-2"><Download size={16} aria-hidden /> A new version is available</p>
          <p className="mt-1 text-xs text-slate-500">Updating reloads the page. Unsaved form input is lost; an active live-demo stream resumes after the reload.</p>
          <div className="mt-3 flex gap-2">
            <button type="button" className="btn-primary !py-2" onClick={() => void applyUpdate()}><RefreshCw size={14} aria-hidden /> Update now</button>
            <button type="button" className="btn-secondary !py-2" onClick={dismissUpdate}>Later</button>
          </div>
        </>
      ) : (
        <div className="flex items-start gap-2">
          <p className="text-xs text-slate-600 dark:text-slate-300 flex-1">
            <strong>Installed for offline use.</strong> The app shell opens without a connection; patient data and predictions still need the backend.
          </p>
          <button type="button" className="icon-btn" aria-label="Dismiss" onClick={dismissOfflineReady}><X size={16} /></button>
        </div>
      )}
    </div>
  );
}
